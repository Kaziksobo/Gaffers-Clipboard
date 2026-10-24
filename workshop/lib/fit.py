"""Pure, pooled fitting of the six position weight/means-std sets.

This is the single implementation of what the six ``*_weights_calculations`` notebooks
do (CB, CDM, CM, Fullback, ST, Winger). It reads no files that it does not name, writes
none, and takes the data it should fit on as an argument, so the same function produces
the live config's regression check, a hold-out fold, and the final pooled fit.

Reproduction guarantee: ``fit_positions`` on Valencia matches 1-155 regenerates the live
``config/performance_weights.json`` and ``performance_means_stds.json`` sections for all
eight positions bit-for-bit (``tests/data/test_workshop_fit.py``).

Pipeline per position (unchanged from the notebooks):

1. Keep single-position performances of the position, 10+ minutes.
2. Soften volume stats by team possession, then normalise to a 10-minute half.
3. Bayesian-smooth to per-90 (rare stats shrink to 0, volume stats to the fitting
   data's own average) and add the xT bonus.
4. z-score against the anchored means/stds (external, from the calibration repo) or, for
   goals and assists, against ``team_xg * position share``; mask low-volume percentages.
5. Robust PCA (``MinCovDet``), loadings weighted by sqrt of eigenvalue, then the
   post-hoc ``philosophy`` correction and normalisation to sum to 1.

Note: the notebooks describe the PCA as fitted on philosophy-scaled z-scores, but
``scaled_pca_df`` is an unscaled copy; the philosophy acts only in the post-hoc division.
This is reproduced as written, not changed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.covariance import MinCovDet

from workshop.lib import datasets

INPUTS_DIR = datasets.PROJECT_ROOT / "workshop" / "ratings_creation"
LIVE_CONFIG_DIR = datasets.PROJECT_ROOT / "config"
WEIGHTS_FILE = "performance_weights.json"
MEANS_STDS_FILE = "performance_means_stds.json"
MANIFEST_FILE = "fit_manifest.json"

# Order matters: it is the order of the weight vector the service dots with.
STAT_COLUMNS = [
    "goals_p90", "assists_p90", "non_goal_shots_p90", "shot_accuracy", "passes_p90",
    "pass_accuracy", "dribbles_p90", "dribble_success_rate", "tackles_p90",
    "tackle_success_rate", "offsides_p90", "fouls_committed_p90", "possession_won_p90",
    "possession_lost_p90", "distance_covered_p90", "distance_sprinted_p90", "xt_bonus_p90",
]  # fmt: skip
LOG_COLUMNS = [
    "goals_p90", "assists_p90", "non_goal_shots_p90", "offsides_p90",
    "fouls_committed_p90", "possession_won_p90", "possession_lost_p90",
]  # fmt: skip
NEGATIVE_STATS = ["fouls_committed_p90", "offsides_p90", "possession_lost_p90"]

BLOCKS: dict[str, list[str]] = {
    "Attacking": ["goals_p90_z", "assists_p90_z", "non_goal_shots_p90_z", "shot_accuracy_z"],
    "Passing": ["passes_p90_z", "pass_accuracy_z"],
    "Dribbling": ["dribbles_p90_z", "dribble_success_rate_z"],
    "Safety": ["possession_lost_p90_z"],
    "Defending": ["tackles_p90_z", "tackle_success_rate_z", "possession_won_p90_z"],
    "Workrate_and_Threat": ["distance_covered_p90_z", "distance_sprinted_p90_z", "xt_bonus_p90_z"],
    "Tactical_Discipline": ["offsides_p90_z", "fouls_committed_p90_z"],
}  # fmt: skip

H_BASE = 10.0
MIN_MINUTES = 10
N_COMPONENTS = 9
MCD_RANDOM_STATE = 42
MCD_SUPPORT_FRACTION = 0.98
CUM_COLUMNS = [
    "passes", "dribbles", "tackles", "possession_won", "possession_lost",
    "fouls_committed", "offsides", "distance_covered", "distance_sprinted",
]  # fmt: skip
DUMMY_WEIGHTS = {
    "goals": 45.0, "assists": 45.0, "shots": 45.0,
    "dribbles": 30.0, "tackles": 30.0, "fouls_committed": 30.0, "offsides": 30.0,
    "passes": 15.0, "distance_covered": 15.0, "distance_sprinted": 15.0,
    "possession_won": 15.0, "possession_lost": 15.0,
}  # fmt: skip
RARE_COLUMNS = ["goals", "assists", "shots"]
VOLUME_COLUMNS = CUM_COLUMNS
ATTACK_TAX_COLUMNS = ["passes", "dribbles", "shots", "possession_lost"]
DEFENCE_TAX_COLUMNS = ["tackles", "possession_won", "fouls_committed"]
# z column -> (volume column, threshold, steepness); mirrors the service's masking.
VOLUME_MASK_PARAMS = {
    "pass_accuracy_z": ("passes", 3.0, 1.1),
    "dribble_success_rate_z": ("dribbles", 2.0, 1.5),
    "shot_accuracy_z": ("shots", 1.5, 2.0),
    "tackle_success_rate_z": ("tackles", 1.5, 2.0),
}


# Rare-event stats: a log-space std from few events is unreliable (see RareEventPolicy).
RARE_EVENT_COLUMNS = {
    "goals_p90": "goals",
    "assists_p90": "assists",
    "offsides_p90": "offsides",
}


@dataclass(frozen=True)
class RareEventPolicy:
    """Floor under the std of rare-event stats, relaxing as events accumulate.

    A stat with few events has a tiny, noisy data std, so one event produces an extreme
    z-score. The policy puts a floor under the std that depends on how many rows had at
    least one event (``E``), so the fit moves towards what the data says as it grows:

    - ``E == 0``: unchanged (std 0, so the service uses z = 0: no information, no weight);
    - ``E <= full_until_events``: the full ``floor``;
    - between ``full_until_events`` and ``data_only_from_events``: the floor shrinks
      linearly to zero;
    - ``E >= data_only_from_events``: the data std alone.

    The floor never lowers a std, so stats above it are untouched. The default 0.08 is
    the live config's lowest active goal/assist std (CB goals, 0.0797).
    """

    floor: float = 0.08
    full_until_events: int = 10
    data_only_from_events: int = 50

    def floor_for(self, events: int) -> float:
        """Return the floor that applies when ``events`` rows had an event."""
        if events <= self.full_until_events:
            return self.floor
        if events >= self.data_only_from_events:
            return 0.0
        span = self.data_only_from_events - self.full_until_events
        return self.floor * (self.data_only_from_events - events) / span

    def apply(self, std: float, events: int) -> float:
        """Return ``std`` raised to the floor for this event count (0 events: unchanged)."""
        if events == 0:
            return std
        return max(std, self.floor_for(events))


@dataclass(frozen=True)
class DirectFitPolicy:
    """When a derived position has enough data to be fitted like any other.

    Wing-backs, wide midfielders and CAM start out derived from a proxy position. Once a
    position has ``min_rows`` single-position performances its own fit starts to blend in,
    reaching full weight at ``full_rows``; below ``min_rows`` the derived values are used
    unchanged. The blend is linear in the weights and in each mean and std, so the config
    moves smoothly towards what the data says as rows accumulate.

    The default ``min_rows`` of 85 is five times the 17 fitted stats; ``full_rows`` of 250
    is about fifteen times.
    """

    min_rows: int = 85
    full_rows: int = 250

    def alpha(self, rows: int) -> float:
        """Return the weight (0 to 1) given to the direct fit at ``rows`` rows."""
        if rows <= self.min_rows:
            return 0.0
        if rows >= self.full_rows:
            return 1.0
        return (rows - self.min_rows) / (self.full_rows - self.min_rows)


@dataclass(frozen=True)
class PositionSpec:
    """Everything that differs between the six position notebooks."""

    name: str
    positions: tuple[str, ...]  # single-position performances that feed the fit
    sections: tuple[str, ...]  # config sections the result is written to
    anchored_key: str | None
    shares: Callable[[Mapping[str, Mapping[str, float]]], tuple[float, float]]
    xt_coefficient: float
    philosophy: Mapping[str, float]


def _share(key: str) -> Callable[[Mapping[str, Mapping[str, float]]], tuple[float, float]]:
    return lambda s: (s["pos_goals_p90"][key], s["pos_assists_p90"][key])


def _mean_share(a: str, b: str) -> Callable[[Mapping[str, Mapping[str, float]]], tuple[float, float]]:
    return lambda s: (
        (s["pos_goals_p90"][a] + s["pos_goals_p90"][b]) / 2,
        (s["pos_assists_p90"][a] + s["pos_assists_p90"][b]) / 2,
    )


SPECS: dict[str, PositionSpec] = {
    "CB": PositionSpec(
        "CB", ("CB",), ("CB",), "CB", _share("DC"), 0.10,
        {"Attacking": 1.0, "Dribbling": 0.6, "Passing": 1.4, "Workrate_and_Threat": 0.7,
         "Safety": 1.6, "Defending": 3.0, "Tactical_Discipline": 0.8},
    ),
    "CDM": PositionSpec(
        "CDM", ("CDM",), ("CDM",), "CDM", _share("DM"), 0.10,
        {"Attacking": 1.0, "Passing": 2.7, "Dribbling": 0.6, "Safety": 1.4,
         "Defending": 2.5, "Workrate_and_Threat": 0.8, "Tactical_Discipline": 1.0},
    ),
    "CM": PositionSpec(
        "CM", ("CM",), ("CM",), "CM", _share("MC"), 0.25,
        {"Attacking": 1.0, "Passing": 1.0, "Dribbling": 1.0, "Safety": 1.0,
         "Defending": 1.0, "Workrate_and_Threat": 1.0, "Tactical_Discipline": 0.5},
    ),
    "Fullback": PositionSpec(
        "Fullback", ("RB", "LB"), ("RB", "LB"), "RB", _mean_share("DL", "DR"), 0.25,
        {"Attacking": 0.8, "Passing": 1.5, "Dribbling": 1.7, "Safety": 0.9,
         "Defending": 2.0, "Workrate_and_Threat": 1.5, "Tactical_Discipline": 0.8},
    ),
    "ST": PositionSpec(
        "ST", ("ST",), ("ST",), "ST", _share("ST"), 0.35,
        {"Attacking": 2.5, "Dribbling": 1.2, "Passing": 0.8, "Workrate_and_Threat": 1.0,
         "Safety": 0.3, "Defending": 0.4, "Tactical_Discipline": 0.6},
    ),
    "Winger": PositionSpec(
        "Winger", ("RW", "LW"), ("RW", "LW"), "RW", _mean_share("RW", "LW"), 0.35,
        {"Attacking": 2.1, "Passing": 1.6, "Dribbling": 2.4, "Safety": 0.2,
         "Defending": 0.5, "Workrate_and_Threat": 2.0, "Tactical_Discipline": 0.7},
    ),
}  # fmt: skip


@dataclass(frozen=True)
class DerivedSpec:
    """A position with too little data to fit: its proxy's fit, adjusted by multipliers."""

    name: str
    sections: tuple[str, ...]
    proxy: str  # config section the multipliers are applied to
    weight_multipliers: Mapping[str, float]
    stat_multipliers: Mapping[str, float]
    overrides: Mapping[str, Mapping[str, float]] = field(default_factory=dict)


DERIVED: dict[str, DerivedSpec] = {
    "Wingback": DerivedSpec(
        "Wingback", ("RWB", "LWB"), "RB",
        {"goals_p90": 2.0, "assists_p90": 8.0, "non_goal_shots_p90": 1.5, "shot_accuracy": 1.0,
         "passes_p90": 1.2, "pass_accuracy": 0.9, "dribbles_p90": 1.8, "dribble_success_rate": 1.8,
         "tackles_p90": 0.8, "tackle_success_rate": 0.8, "offsides_p90": 0.6,
         "fouls_committed_p90": 0.7, "possession_won_p90": 0.6, "possession_lost_p90": 0.6,
         "distance_covered_p90": 1.7, "distance_sprinted_p90": 1.7, "xt_bonus_p90": 2.0},
        {"goals_p90": 2.0, "assists_p90": 2.4, "non_goal_shots_p90": 1.5, "shot_accuracy": 1.0,
         "dribbles_p90": 1.4, "dribble_success_rate": 0.8, "tackles_p90": 0.6,
         "tackle_success_rate": 0.9, "offsides_p90": 2.0, "possession_won_p90": 0.7,
         "possession_lost_p90": 2.0, "distance_covered_p90": 1.15, "distance_sprinted_p90": 1.3,
         "xt_bonus_p90": 1.5},
        # Hand-set: the Fullback proxy has no goals, and a crushed shot-accuracy variance.
        {"goals_p90": {"mean": 0.08, "std": 0.15}, "shot_accuracy": {"std": 18.5}},
    ),
    "WideMidfielder": DerivedSpec(
        "WideMidfielder", ("RM", "LM"), "RW",
        {"goals_p90": 0.8, "assists_p90": 1.2, "non_goal_shots_p90": 0.6, "shot_accuracy": 0.6,
         "passes_p90": 2.0, "pass_accuracy": 2.5, "dribbles_p90": 0.9, "dribble_success_rate": 1.2,
         "tackles_p90": 3.0, "tackle_success_rate": 3.0, "offsides_p90": 1.0,
         "fouls_committed_p90": 1.0, "possession_won_p90": 3.0, "possession_lost_p90": 2.5,
         "distance_covered_p90": 1.1, "distance_sprinted_p90": 1.1, "xt_bonus_p90": 1.1},
        {"goals_p90": 0.5, "assists_p90": 1.3, "non_goal_shots_p90": 0.5, "passes_p90": 1.4,
         "pass_accuracy": 1.06, "dribbles_p90": 0.8, "tackles_p90": 2.5,
         "tackle_success_rate": 1.5, "offsides_p90": 0.8, "fouls_committed_p90": 1.2,
         "possession_won_p90": 2.0, "possession_lost_p90": 0.7, "distance_covered_p90": 1.1,
         "distance_sprinted_p90": 1.1, "xt_bonus_p90": 1.3},
    ),
    "CAM": DerivedSpec(
        "CAM", ("CAM",), "CM",
        {"goals_p90": 2.0, "assists_p90": 2.5, "non_goal_shots_p90": 1.5, "shot_accuracy": 1.5,
         "passes_p90": 1.5, "pass_accuracy": 1.2, "dribbles_p90": 1.5, "dribble_success_rate": 1.2,
         "tackles_p90": 0.2, "tackle_success_rate": 0.2, "offsides_p90": 1.0,
         "fouls_committed_p90": 1.0, "possession_won_p90": 0.3, "possession_lost_p90": 0.5,
         "distance_covered_p90": 0.8, "distance_sprinted_p90": 0.8, "xt_bonus_p90": 2.0},
        {"goals_p90": 1.5, "assists_p90": 2.0, "non_goal_shots_p90": 1.5, "passes_p90": 1.2,
         "pass_accuracy": 0.95, "dribbles_p90": 1.2, "dribble_success_rate": 0.95,
         "tackles_p90": 0.2, "offsides_p90": 1.2, "possession_won_p90": 0.3,
         "possession_lost_p90": 1.3, "distance_covered_p90": 0.85,
         "distance_sprinted_p90": 0.85, "xt_bonus_p90": 1.3},
    ),
}  # fmt: skip


# How to fit the derived positions directly once they have data. These have no real-world
# anchors, so every non-goal/assist stat is z-scored against the position's own data. The
# philosophies are the owner's role definitions (WM, CAM, wing-back). They only matter once a
# position passes DirectFitPolicy.min_rows (wing-backs have no data yet, so theirs was checked
# on Fullback rows). The xT coefficients must equal the service's XT_POSITION_SCALARS for the
# position (a test checks it).
DIRECT_SPECS: dict[str, PositionSpec] = {
    "WideMidfielder": PositionSpec(
        "WideMidfielder", ("RM", "LM"), ("RM", "LM"), None, _mean_share("ML", "MR"), 0.25,
        {"Attacking": 1.8, "Passing": 1.8, "Dribbling": 1.6, "Safety": 0.5,
         "Defending": 1.2, "Workrate_and_Threat": 1.6, "Tactical_Discipline": 0.5},
    ),
    "CAM": PositionSpec(
        "CAM", ("CAM",), ("CAM",), None, _share("AM"), 0.35,
        {"Attacking": 1.9, "Passing": 1.6, "Dribbling": 1.2, "Safety": 0.5,
         "Defending": 0.4, "Workrate_and_Threat": 1.0, "Tactical_Discipline": 0.5},
    ),
    "Wingback": PositionSpec(
        "Wingback", ("RWB", "LWB"), ("RWB", "LWB"), None, _mean_share("DL", "DR"), 0.25,
        {"Attacking": 2.0, "Passing": 1.4, "Dribbling": 2.0, "Safety": 0.7,
         "Defending": 1.2, "Workrate_and_Threat": 1.6, "Tactical_Discipline": 0.6},
    ),
}  # fmt: skip


def _blend_weights(
    derived: Mapping[str, float], direct: Mapping[str, float], alpha: float
) -> dict[str, float]:
    """Convex combination of two weight vectors (sums to 1 when both do)."""
    return {k: alpha * direct[k] + (1.0 - alpha) * derived[k] for k in derived}


def _blend_means(
    derived: Mapping[str, Mapping[str, float]],
    direct: Mapping[str, Mapping[str, float]],
    alpha: float,
) -> dict[str, dict[str, float]]:
    """Linear blend of two means/stds tables, stat by stat."""
    return {
        stat: {
            key: alpha * direct[stat][key] + (1.0 - alpha) * derived[stat][key]
            for key in ("mean", "std")
        }
        for stat in derived
    }


def derive_sections(
    weights: Mapping[str, Mapping[str, float]],
    means_stds: Mapping[str, Mapping[str, Mapping[str, float]]],
    specs: Mapping[str, DerivedSpec] = DERIVED,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Derive the wing-back, wide-midfielder and CAM sections from their proxies.

    Weights: the proxy's weights times the hand-set multipliers, renormalised to sum to 1.
    Means/stds: proxy mean times the stat multiplier, std times its square root (variance
    scaling with the mean), then any hand-set overrides.

    Returns:
        ``(weights, means_stds, proxies)`` keyed by derived section; ``proxies`` maps each
        derived section to the section it was derived from.

    Raises:
        KeyError: If a proxy section is missing from the inputs.
    """
    new_weights: dict[str, Any] = {}
    new_means: dict[str, Any] = {}
    proxies: dict[str, str] = {}
    for spec in specs.values():
        proxy_weights = {col: weights[spec.proxy][col] for col in STAT_COLUMNS}
        raw: dict[str, float] = {}
        total = 0
        for stat, base in proxy_weights.items():
            value = base * spec.weight_multipliers.get(stat, 1.0)
            raw[stat] = value
            total += value
        normalised = {k: v / total for k, v in raw.items()}

        derived_means: dict[str, dict[str, float]] = {}
        for stat, stats in means_stds[spec.proxy].items():
            multiplier = spec.stat_multipliers.get(stat, 1.0)
            derived_means[stat] = {
                "mean": stats["mean"] * multiplier,
                "std": stats["std"] * float(np.sqrt(multiplier)),
            }
            for key, value in spec.overrides.get(stat, {}).items():
                derived_means[stat][key] = value
        for section in spec.sections:
            new_weights[section] = dict(normalised)
            new_means[section] = copy_nested(derived_means)
            proxies[section] = spec.proxy
    return new_weights, new_means, proxies


def copy_nested(obj: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float]]:
    """Return an independent two-level copy of a nested mapping."""
    return {k: dict(v) for k, v in obj.items()}


@dataclass(frozen=True)
class FitSource:
    """One career's matches (already filtered to the ones that may be fitted on)."""

    career: str
    club: str
    matches: list[dict[str, Any]]

    @property
    def match_ids(self) -> tuple[int, int]:
        """First and last match id included."""
        ids = [m["id"] for m in self.matches]
        return min(ids), max(ids)


def load_sources(ranges: Mapping[str, tuple[int, int] | None]) -> list[FitSource]:
    """Load careers, keeping only matches whose id is inside the given inclusive range.

    Args:
        ranges: ``{career: (first_id, last_id)}``; ``None`` keeps every match. The dict
            order is the order rows are pooled in (it affects ``MinCovDet`` reproducibly).
    """
    sources = []
    for name, id_range in ranges.items():
        career = datasets.load_career(name)
        matches = [
            m
            for m in career.matches
            if id_range is None or id_range[0] <= m["id"] <= id_range[1]
        ]
        sources.append(FitSource(name, career.club, matches))
    return sources


def load_inputs(inputs_dir: Path = INPUTS_DIR) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the external calibration inputs: anchored means/stds and position shares."""
    anchored = json.loads((inputs_dir / "anchored_means_stds.json").read_text("utf-8"))
    shares = json.loads((inputs_dir / "pos_shares.json").read_text("utf-8"))
    return anchored, shares


GK_VOLUME_COLUMNS = [
    "shots_against", "shots_on_target", "saves", "goals_conceded", "team_xg", "xg_against",
]  # fmt: skip


def fit_gk(sources: Sequence[FitSource]) -> dict[str, float]:
    """Mean and std of the goalkeeper heuristic over every goalkeeper performance.

    The service's goalkeeper rating z-scores ``xgp * 1.5 + ln(saves + 1) * save% / 100``
    (``xgp`` = xG against minus goals conceded, volume stats normalised to a 10-minute
    half) against this mean and std; everything else about goalkeeper ratings (floors,
    bonuses, clean-sheet tiers, supremacy) is hand-set in the service.

    Returns:
        ``{"mean": ..., "std": ...}`` over all goalkeeper rows of all sources.
    """
    records = [
        {"id": m["id"], "club": s.club, "data": m["data"],
         "player_performances": m["player_performances"]}
        for s in sources
        for m in s.matches
    ]  # fmt: skip
    frame = pd.json_normalize(
        records,
        record_path="player_performances",
        meta=[
            "id",
            "club",
            ["data", "half_length"],
            ["data", "home_team_name"],
            ["data", "home_stats", "xg"],
            ["data", "away_stats", "xg"],
            ["data", "home_score"],
            ["data", "away_score"],
        ],
    )
    home = frame["data.home_team_name"] == frame["club"]
    frame["team_xg"] = np.where(home, frame["data.home_stats.xg"], frame["data.away_stats.xg"])
    frame["xg_against"] = np.where(home, frame["data.away_stats.xg"], frame["data.home_stats.xg"])
    frame["goals_conceded"] = np.where(home, frame["data.away_score"], frame["data.home_score"])
    frame = frame.rename(columns={"data.half_length": "half_length"})
    gk = frame[frame["performance_type"] == "GK"].dropna(axis=1, how="all").copy()
    numeric = [
        c for c in gk.columns
        if c not in ("player_id", "id", "club", "performance_type") and not c.startswith("data.")
    ]  # fmt: skip
    gk[numeric] = gk[numeric].apply(pd.to_numeric, errors="coerce").fillna(0)
    for col in GK_VOLUME_COLUMNS:
        gk[col] = gk[col].astype(float) * (H_BASE / gk["half_length"])
    xgp = gk["xg_against"] - gk["goals_conceded"]
    heuristic = xgp * 1.5 + np.log(gk["saves"] + 1.0) * (gk["save_success_rate"] / 100.0)
    return {"mean": float(heuristic.mean()), "std": float(heuristic.std())}


def _performance_frame(sources: Sequence[FitSource]) -> pd.DataFrame:
    """Flatten every performance with its match context, pooling the sources."""
    records = [
        {
            "id": m["id"],
            "club": src.club,
            "data": m["data"],
            "player_performances": m["player_performances"],
        }
        for src in sources
        for m in src.matches
    ]
    frame = pd.json_normalize(
        records,
        record_path="player_performances",
        meta=[
            "id",
            "club",
            ["data", "half_length"],
            ["data", "home_team_name"],
            ["data", "away_team_name"],
            ["data", "home_stats", "possession"],
            ["data", "away_stats", "possession"],
            ["data", "home_stats", "xg"],
            ["data", "away_stats", "xg"],
        ],
    )
    is_home = frame["data.home_team_name"] == frame["club"]
    frame["team_possession"] = np.where(
        is_home, frame["data.home_stats.possession"], frame["data.away_stats.possession"]
    ).astype(float)
    frame["team_xg"] = np.where(
        is_home, frame["data.home_stats.xg"], frame["data.away_stats.xg"]
    ).astype(float)
    frame = frame.drop(
        columns=[
            "club",
            "data.home_team_name",
            "data.away_team_name",
            "data.home_stats.possession",
            "data.away_stats.possession",
            "data.home_stats.xg",
            "data.away_stats.xg",
        ]
    )
    frame = frame.rename(columns={"data.half_length": "half_length", "id": "match_id"})
    frame = frame[frame["performance_type"] != "GK"]
    return frame.dropna(axis=1, how="all")


def _position_frame(frame: pd.DataFrame, spec: PositionSpec) -> pd.DataFrame:
    """Single-position, 10+ minute performances of one position, all numeric."""
    wanted = [[p] for p in spec.positions]
    pos_df = frame[frame["positions_played"].apply(lambda x: x in wanted)]
    if pos_df.empty:  # a position with no data yet (e.g. wing-backs)
        return pos_df.copy()
    pos_df = pos_df.dropna(axis=1, how="all")
    pos_df = pos_df.drop(columns=["performance_type", "positions_played"]).copy()
    to_convert = pos_df.columns.drop(["match_id", "player_id"])
    pos_df[to_convert] = pos_df[to_convert].apply(pd.to_numeric, errors="coerce")
    pos_df[to_convert] = pos_df[to_convert].fillna(0)
    return pos_df[pos_df["minutes_played"] >= MIN_MINUTES].copy()


@dataclass(frozen=True)
class PositionFit:
    """Result of fitting one position."""

    weights: dict[str, float]
    means_stds: dict[str, dict[str, float]]
    n_rows: int
    rare_events: dict[str, int] = field(default_factory=dict)


def fit_position(
    frame: pd.DataFrame,
    spec: PositionSpec,
    anchored_all: Mapping[str, Any],
    shares_all: Mapping[str, Mapping[str, float]],
    std_overrides: Mapping[str, float] | None = None,
    rare_event_policy: RareEventPolicy | None = None,
) -> PositionFit:
    """Fit one position from a pooled performance frame (see ``_performance_frame``).

    Args:
        frame: Pooled frame from ``_performance_frame``.
        spec: The position to fit.
        anchored_all: Anchored means/stds from the calibration repo.
        shares_all: Goal and assist shares by position.
        std_overrides: Optional ``{stat column: std}`` replacing the data-derived std
            for those stats, both in the z-scores the PCA sees and in the stored
            means/stds. ``0.0`` makes the stat's z-score zero (as the service does for
            a zero std). ``None`` (the default) reproduces the live config.
        rare_event_policy: Optional floor under the std of rare-event stats (goals,
            assists, offsides) when their std is data-derived. ``None`` leaves them
            alone. ``std_overrides`` takes precedence.
    """
    overrides = dict(std_overrides or {})
    pos_df = _position_frame(frame, spec)
    rare_events = {
        col: int((pos_df[raw] > 0).sum()) for col, raw in RARE_EVENT_COLUMNS.items()
    }
    rare_std: dict[str, float] = {}
    anchored = anchored_all[spec.anchored_key] if spec.anchored_key else {}
    goal_share, assist_share = spec.shares(shares_all)

    # Possession adjustment (sqrt-softened) then 10-minute-half normalisation
    for col in ATTACK_TAX_COLUMNS:
        pos_df[col] = pos_df[col] * np.sqrt(50.0 / pos_df["team_possession"])
    for col in DEFENCE_TAX_COLUMNS:
        pos_df[col] = pos_df[col] * np.sqrt(50.0 / (100.0 - pos_df["team_possession"]))
    for col in CUM_COLUMNS:
        pos_df[col] = pos_df[col] * (H_BASE / pos_df["half_length"])

    # Bayesian-smoothed per-90 scaling
    for col in RARE_COLUMNS:
        d = DUMMY_WEIGHTS[col]
        pos_df[f"{col}_p90"] = (pos_df[col] / (pos_df["minutes_played"] + d)) * 90.0
    for col in VOLUME_COLUMNS:
        d = DUMMY_WEIGHTS[col]
        league_avg_p90 = (pos_df[col].sum() / pos_df["minutes_played"].sum()) * 90.0
        dummy_stat = league_avg_p90 * (d / 90.0)
        pos_df[f"{col}_p90"] = ((pos_df[col] + dummy_stat) / (pos_df["minutes_played"] + d)) * 90.0

    control_ratio = (
        (pos_df["possession_won_p90"] + 1.0) / (pos_df["possession_lost_p90"] + 1.0)
    ).clip(upper=2.5)
    pos_df["xt_bonus_p90"] = (
        spec.xt_coefficient
        * control_ratio
        * (pos_df["distance_sprinted_p90"] / pos_df["distance_covered_p90"])
        * np.log(pos_df["pass_accuracy"] * pos_df["passes_p90"] + 1)
    )

    # z-scores on a log-transformed copy
    pca_df = pos_df.copy()
    pca_df["non_goal_shots_p90"] = (pca_df["shots_p90"] - pca_df["goals_p90"]).clip(lower=0.0)
    pca_df[LOG_COLUMNS] = np.log(pca_df[LOG_COLUMNS] + 1)
    for col in STAT_COLUMNS:
        if col == "goals_p90":
            mean = np.log(pos_df["team_xg"] * goal_share + 1)
            std = pca_df[col].std()
        elif col == "assists_p90":
            mean = np.log(pos_df["team_xg"] * assist_share + 1)
            std = pca_df[col].std()
        elif col in anchored:
            mean = anchored[col]["mean"]
            std = anchored[col]["std"]
        else:
            mean = pca_df[col].mean()
            std = pca_df[col].std()
        data_derived = col in ("goals_p90", "assists_p90") or col not in anchored
        if rare_event_policy is not None and col in rare_events and data_derived:
            std = rare_event_policy.apply(float(std), rare_events[col])
            rare_std[col] = std
        if col in overrides:
            std = overrides[col]
        if std == 0:
            pca_df[f"{col}_z"] = 0
        elif col in NEGATIVE_STATS:
            pca_df[f"{col}_z"] = (mean - pca_df[col]) / std
        else:
            pca_df[f"{col}_z"] = (pca_df[col] - mean) / std
    for z_col, (vol_col, threshold, lam) in VOLUME_MASK_PARAMS.items():
        w_mask = 1.0 / (1.0 + np.exp(-lam * (pca_df[vol_col] - threshold)))
        pca_df[z_col] = pca_df[z_col] * w_mask
    z_matrix = pca_df[[f"{col}_z" for col in STAT_COLUMNS]]

    # Robust PCA -> weights
    mcd = MinCovDet(
        random_state=MCD_RANDOM_STATE, support_fraction=MCD_SUPPORT_FRACTION
    ).fit(z_matrix)
    eigenvalues, eigenvectors = np.linalg.eigh(mcd.covariance_)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
    k = N_COMPONENTS
    loadings = np.abs(eigenvectors[:, :k]) * np.sqrt(eigenvalues[:k])
    raw_weights = np.sum(loadings, axis=1)

    # Post-hoc philosophy correction
    col_order = z_matrix.columns.tolist()
    scale_factors = np.ones(len(col_order))
    for block, block_stats in BLOCKS.items():
        sf = np.sqrt(len(block_stats)) / spec.philosophy[block]
        for stat in block_stats:
            scale_factors[col_order.index(stat)] = sf
    corrected = raw_weights / scale_factors
    final_weights = corrected / corrected.sum()

    means_stds: dict[str, dict[str, float]] = {}
    for col in STAT_COLUMNS:
        if col in anchored:
            mean, std = anchored[col]["mean"], anchored[col]["std"]
        elif col in LOG_COLUMNS:
            mean, std = pca_df[col].mean(), pca_df[col].std()
        else:
            mean, std = pos_df[col].mean(), pos_df[col].std()
        if col in rare_std:
            std = rare_std[col]
        if col in overrides:
            std = overrides[col]
        means_stds[col] = {"mean": float(mean), "std": float(std)}
    weights = {col: float(w) for col, w in zip(STAT_COLUMNS, final_weights, strict=True)}
    return PositionFit(weights, means_stds, len(pos_df), rare_events)


@dataclass(frozen=True)
class FitResult:
    """Fits for every position, keyed by config section (RB and LB share one fit)."""

    weights: dict[str, dict[str, float]]
    means_stds: dict[str, dict[str, dict[str, float]]]
    rows: dict[str, int]
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    rare_events: dict[str, dict[str, int]] = field(default_factory=dict)
    policy: dict[str, Any] | None = None
    derived: dict[str, str] = field(default_factory=dict)
    direct: dict[str, dict[str, Any]] = field(default_factory=dict)
    direct_policy: dict[str, Any] | None = None


def fit_positions(
    sources: Sequence[FitSource],
    inputs_dir: Path = INPUTS_DIR,
    positions: Sequence[str] | None = None,
    std_overrides: Mapping[str, Mapping[str, float]] | None = None,
    rare_event_policy: RareEventPolicy | None = None,
    derive_unknown: bool = False,
    include_gk: bool = False,
    direct_fit_policy: DirectFitPolicy | None = None,
) -> FitResult:
    """Fit every (or the named) position on the pooled sources.

    Args:
        sources: Careers and match ranges to fit on, in pooling order.
        inputs_dir: Folder with ``anchored_means_stds.json`` and ``pos_shares.json``.
        positions: Subset of ``SPECS`` keys (default: all six).
        std_overrides: Optional ``{position name: {stat column: std}}`` (see
            ``fit_position``); positions not listed keep their data-derived stds.
        rare_event_policy: Optional ``RareEventPolicy`` applied to every position.
        derive_unknown: Also derive the wing-back, wide-midfielder and CAM sections
            from their fitted proxies (needs the RB, RW and CM fits).
        include_gk: Also fit the goalkeeper means/stds (``fit_gk``) into ``GK``.
        direct_fit_policy: With ``derive_unknown``, blend each derived position's own
            fit in as its row count passes ``DirectFitPolicy.min_rows`` (``None`` keeps
            every derived position purely derived).
    """
    anchored, shares = load_inputs(inputs_dir)
    frame = _performance_frame(sources)
    weights: dict[str, dict[str, float]] = {}
    means_stds: dict[str, dict[str, dict[str, float]]] = {}
    rows: dict[str, int] = {}
    events: dict[str, dict[str, int]] = {}
    for name in positions or SPECS:
        spec = SPECS[name]
        fit = fit_position(
            frame,
            spec,
            anchored,
            shares,
            (std_overrides or {}).get(name),
            rare_event_policy,
        )
        rows[name] = fit.n_rows
        for section in spec.sections:
            events[section] = fit.rare_events
            weights[section] = fit.weights
            means_stds[section] = fit.means_stds
    provenance = {
        s.career: {"match_ids": list(s.match_ids), "n_matches": len(s.matches)}
        for s in sources
    }
    policy = asdict(rare_event_policy) if rare_event_policy is not None else None
    proxies: dict[str, str] = {}
    direct_info: dict[str, dict[str, Any]] = {}
    if derive_unknown:
        d_weights, d_means, proxies = derive_sections(weights, means_stds)
        if direct_fit_policy is not None:
            for dspec in DERIVED.values():
                spec = DIRECT_SPECS[dspec.name]
                rows_available = len(_position_frame(frame, spec))
                alpha = direct_fit_policy.alpha(rows_available)
                info = {"rows": rows_available, "weight": alpha}
                if alpha > 0:
                    try:
                        direct = fit_position(
                            frame, spec, anchored, shares, None, rare_event_policy
                        )
                    except (ValueError, np.linalg.LinAlgError) as exc:
                        info = {"rows": rows_available, "weight": 0.0, "note": f"direct fit failed: {exc}"}
                        alpha = 0.0
                for section in dspec.sections:
                    direct_info[section] = dict(info)
                    if alpha > 0:
                        d_weights[section] = _blend_weights(d_weights[section], direct.weights, alpha)
                        d_means[section] = _blend_means(d_means[section], direct.means_stds, alpha)
                        events[section] = direct.rare_events
        weights.update(d_weights)
        means_stds.update(d_means)
    if include_gk:
        means_stds["GK"] = fit_gk(sources)
    return FitResult(
        weights,
        means_stds,
        rows,
        provenance,
        events,
        policy,
        proxies,
        direct_info,
        asdict(direct_fit_policy) if direct_fit_policy is not None else None,
    )


def config_hash(config_dir: Path = LIVE_CONFIG_DIR) -> str:
    """SHA-256 over the weights and means/stds files (the pair the service loads)."""
    digest = hashlib.sha256()
    for name in (WEIGHTS_FILE, MEANS_STDS_FILE):
        digest.update((config_dir / name).read_bytes())
    return digest.hexdigest()


def build_candidate(
    fit: FitResult, base_dir: Path = LIVE_CONFIG_DIR
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge a fit into a copy of the base config; unfitted sections are kept as they are."""
    weights = json.loads((base_dir / WEIGHTS_FILE).read_text("utf-8"))
    means_stds = json.loads((base_dir / MEANS_STDS_FILE).read_text("utf-8"))
    weights.update(fit.weights)
    means_stds.update(fit.means_stds)
    return weights, means_stds


MANIFEST_DESCRIPTION = (
    "Provenance of a rating config. Validation notebooks read this to label career data as "
    "in-sample (inside a fitted range) or out-of-sample. tests/data/test_workshop_fit.py "
    "checks that the hash matches the files and that re-fitting the recorded sources "
    "(with the recorded rare-event policy) reproduces every fitted and derived section "
    "exactly."
)


def write_candidate(
    directory: Path,
    fit: FitResult,
    base_dir: Path = LIVE_CONFIG_DIR,
    note: str = "",
) -> dict[str, Any]:
    """Write a config directory (weights, means/stds and ``fit_manifest.json``).

    Sections the fit did not produce are carried over unchanged from ``base_dir`` and
    listed as legacy in the manifest.

    Returns:
        The manifest that was written.
    """
    weights, means_stds = build_candidate(fit, base_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / WEIGHTS_FILE).write_text(json.dumps(weights, indent=4), "utf-8")
    (directory / MEANS_STDS_FILE).write_text(json.dumps(means_stds, indent=4), "utf-8")
    fitted = sorted(set(fit.weights) - set(fit.derived))
    covered = set(fit.weights) | set(fit.means_stds)
    legacy = {
        WEIGHTS_FILE: sorted(set(weights) - covered),
        MEANS_STDS_FILE: sorted(set(means_stds) - covered),
    }
    manifest = {
        "description": MANIFEST_DESCRIPTION,
        "config_hash": config_hash(directory),
        "hashed_files": [WEIGHTS_FILE, MEANS_STDS_FILE],
        "manifest_written": date.today().isoformat(),
        "note": note,
        "fitted_sections": {
            **{
                section: {
                    "method": "workshop/lib/fit.py",
                    "sources": fit.sources,
                    "rare_event_counts": fit.rare_events.get(section, {}),
                }
                for section in fitted
            },
            **(
                {
                    "GK": {
                        "method": "workshop/lib/fit.py:fit_gk",
                        "sources": fit.sources,
                        "rare_event_counts": {},
                    }
                }
                if "GK" in fit.means_stds
                else {}
            ),
        },
        "derived_sections": {
            section: {
                "method": "workshop/lib/fit.py:derive_sections",
                "proxy": proxy,
                **({"direct_fit": fit.direct[section]} if section in fit.direct else {}),
            }
            for section, proxy in sorted(fit.derived.items())
        },
        "direct_fit_policy": fit.direct_policy,
        "legacy_sections": {
            "note": (
                f"carried over unchanged from {base_dir.name}; not reproduced by "
                "workshop/lib/fit.py"
            ),
            **legacy,
        },
        "rare_event_policy": fit.policy,
        "rows_per_position": fit.rows,
    }
    (directory / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    return manifest
