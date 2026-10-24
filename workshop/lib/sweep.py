"""One-at-a-time parameter sweeps over MatchRatingsService class constants.

A *variant* is a subclass of ``MatchRatingsService`` that overrides class-level
constants (``GOAL_BONUS_CAP``, ``CS_RATIOS``, ...). Nothing in ``src/`` is touched and
no method is overridden, so variants keep working when the service's internals change.
Constants hard-coded inside method bodies cannot be swept this way.

The workflow is a tornado analysis: scale each constant down and up by a relative step,
re-rate the whole pool, and measure how far ratings move from the baseline.

Example:
    >>> from workshop.lib import sweep
    >>> pool = sweep.load_pool("pool")
    >>> result = sweep.tornado(pool)
    >>> sweep.summarise(result).head(10)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from src.services.analytics.match_ratings_service import MatchRatingsService
from workshop.lib import datasets, rating

# Structural, not tunable: the volume-normalisation base and a non-numeric tuple.
EXCLUDED = frozenset({"H_BASE", "MIRROR_PAIRS"})

DEFAULT_STEP = 0.2
# Relative step per constant where +/-20% is not a plausible range. These are
# judgement calls: edit freely.
STEPS: dict[str, float] = {
    "CDM_PIVOT_MIN_PASS_ACC": 0.05,  # 88% -> roughly 84-92%
    "VERSATILITY_THRESHOLD": 0.10,  # 6.5 -> roughly 5.9-7.2
}

_CHANGED = 0.05  # a rating moved at all (ratings are rounded to 0.1)
_MOVED = 0.5 - 1e-9  # a rating moved by half a point or more

POSITION_GROUPS = {
    "ST": "ST",
    "CF": "ST",
    "LW": "Winger",
    "RW": "Winger",
    "LM": "WM",
    "RM": "WM",
    "CAM": "CAM",
    "CM": "CM",
    "CDM": "CDM",
    "LB": "FB/WB",
    "RB": "FB/WB",
    "LWB": "FB/WB",
    "RWB": "FB/WB",
    "CB": "CB",
    "GK": "GK",
}


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_numeric_tree(value: object) -> bool:
    if _is_number(value):
        return True
    if isinstance(value, Mapping):
        return bool(value) and all(_is_numeric_tree(v) for v in value.values())
    return False


def tunable_constants(
    cls: type[MatchRatingsService] = MatchRatingsService,
) -> dict[str, Any]:
    """Return the class-level numeric constants that can be swept.

    Scalars and (nested) mappings of numbers qualify; ``EXCLUDED`` names do not.
    """
    return {
        name: value
        for name, value in vars(cls).items()
        if name.isupper()
        and not name.startswith("_")
        and name not in EXCLUDED
        and _is_numeric_tree(value)
    }


def scale_value(value: Any, factor: float) -> Any:  # noqa: ANN401
    """Multiply a number, or every number inside a mapping, by ``factor``."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: scale_value(v, factor) for k, v in value.items()})
    return float(value) * factor


def scale_key(value: Mapping[str, Any], key: str, factor: float) -> Any:  # noqa: ANN401
    """Scale a single top-level entry of a mapping, leaving the others alone."""
    return MappingProxyType(
        {k: scale_value(v, factor) if k == key else v for k, v in value.items()}
    )


def make_variant(overrides: dict[str, Any]) -> MatchRatingsService:
    """Build a service whose class constants are replaced by ``overrides``.

    The base class is never modified: overrides live on a throwaway subclass.
    """
    base = rating.load_service()
    variant_cls = type("Variant", (MatchRatingsService,), dict(overrides))
    return variant_cls(base.weights, base.means_stds)


@dataclass
class Pool:
    """Every performance of the selected careers, ready to be re-rated quickly."""

    index: pd.DataFrame
    records: list[tuple[str, dict[str, Any], dict[str, Any]]]
    baseline: np.ndarray


def rate_pool(pool_records: list, service: MatchRatingsService) -> np.ndarray:
    """Rate every record, with NaN where the service declines to rate."""
    out = np.empty(len(pool_records))
    for i, (club, match_data, perf) in enumerate(pool_records):
        value = rating.rate_performance(service, club, match_data, perf)
        out[i] = np.nan if value is None else value
    return out


def load_pool(tag: str | None = "pool", names: list[str] | None = None) -> Pool:
    """Load careers and rate them once with the live config as the baseline."""
    rows, records = [], []
    for career in datasets.load_careers(tag, names):
        for match in career.matches:
            for perf in match["player_performances"]:
                is_gk = perf["performance_type"] == "GK"
                first = "GK" if is_gk else perf["positions_played"][0]
                rows.append(
                    {
                        "career": career.name,
                        "match_id": match["id"],
                        "player_id": perf["player_id"],
                        "primary_position": first,
                        "group": POSITION_GROUPS.get(first, first),
                    }
                )
                records.append((career.club, match["data"], perf))
    baseline = rate_pool(records, rating.load_service())
    return Pool(pd.DataFrame(rows), records, baseline)


def compare(base: np.ndarray, perturbed: np.ndarray) -> dict[str, float]:
    """Summarise how far ``perturbed`` ratings moved from ``base`` ratings."""
    ok = np.isfinite(base) & np.isfinite(perturbed)
    b, p = base[ok], perturbed[ok]
    diff = p - b
    constant = np.ptp(b) == 0 or np.ptp(p) == 0
    rho = 1.0 if constant else float(stats.spearmanr(b, p).statistic)
    return {
        "mean_shift": float(diff.mean()),
        "sd_shift": float(p.std() - b.std()),
        "rank_corr": rho,
        "mean_abs_change": float(np.abs(diff).mean()),
        "share_changed": float((np.abs(diff) >= _CHANGED).mean()),
        "share_moved_0_5": float((np.abs(diff) >= _MOVED).mean()),
        "max_abs_change": float(np.abs(diff).max()),
    }


def tornado(
    pool: Pool,
    constants: list[str] | None = None,
    step: float = DEFAULT_STEP,
    steps: dict[str, float] | None = None,
    split: list[str] | None = None,
) -> pd.DataFrame:
    """Scale each constant down and up, re-rate the pool, and compare to baseline.

    Args:
        pool: Pool from ``load_pool``.
        constants: Names to sweep (default: every tunable constant).
        step: Default relative step (0.2 means x0.8 and x1.2).
        steps: Per-constant step overrides (default ``STEPS``).
        split: Mapping constants to sweep one key at a time (e.g. ``GOAL_ALPHA``
            by position) instead of scaling the whole mapping together.

    Returns:
        One row per (parameter, key, direction) with the ``compare`` metrics.
    """
    available = tunable_constants()
    names = constants if constants is not None else list(available)
    overrides = {**STEPS, **(steps or {})}
    rows = []
    for name in names:
        value = available[name]
        rel = overrides.get(name, step)
        targets: list[str | None] = (
            list(value) if name in (split or []) and isinstance(value, Mapping) else [None]
        )
        for key in targets:
            for direction, factor in (("down", 1 - rel), ("up", 1 + rel)):
                scaled = (
                    scale_value(value, factor)
                    if key is None
                    else scale_key(value, key, factor)
                )
                service = make_variant({name: scaled})
                metrics = compare(pool.baseline, rate_pool(pool.records, service))
                rows.append(
                    {
                        "parameter": name,
                        "key": key,
                        "direction": direction,
                        "factor": round(factor, 4),
                        **metrics,
                    }
                )
    return pd.DataFrame(rows)


def summarise(result: pd.DataFrame) -> pd.DataFrame:
    """Collapse a tornado result to one row per parameter, biggest effect first.

    ``effect`` is the larger of the down and up mean absolute change in rating.
    ``worst_rank_corr`` is the lowest rank correlation with the baseline ordering,
    ``max_share_changed`` the largest share of ratings that changed at all, and
    ``max_share_moved_0_5`` the largest share that moved by half a point or more.
    """
    labelled = result.assign(
        label=result["parameter"]
        + result["key"].map(lambda k: "" if pd.isna(k) else f"[{k}]")
    )
    wide = labelled.pivot(
        index="label",
        columns="direction",
        values=[
            "mean_abs_change",
            "mean_shift",
            "rank_corr",
            "share_changed",
            "share_moved_0_5",
            "max_abs_change",
        ],
    )
    summary = pd.DataFrame(
        {
            "effect": wide["mean_abs_change"].max(axis=1),
            "down_mean_abs": wide["mean_abs_change"]["down"],
            "up_mean_abs": wide["mean_abs_change"]["up"],
            "mean_shift_down": wide["mean_shift"]["down"],
            "mean_shift_up": wide["mean_shift"]["up"],
            "worst_rank_corr": wide["rank_corr"].min(axis=1),
            "max_share_changed": wide["share_changed"].max(axis=1),
            "max_share_moved_0_5": wide["share_moved_0_5"].max(axis=1),
            "max_abs_change": wide["max_abs_change"].max(axis=1),
        }
    )
    return summary.sort_values("effect", ascending=False)


def effect_by_group(pool: Pool, name: str, factor: float) -> pd.Series:
    """Mean absolute rating change per position group for one scaled constant."""
    service = make_variant({name: scale_value(tunable_constants()[name], factor)})
    diff = np.abs(rate_pool(pool.records, service) - pool.baseline)
    frame = pool.index.assign(abs_change=diff).dropna(subset=["abs_change"])
    return frame.groupby("group")["abs_change"].mean().sort_values(ascending=False)


def plot_tornado(summary: pd.DataFrame, top: int = 20) -> Any:  # noqa: ANN401
    """Draw a tornado chart of the ``top`` parameters (mean absolute change)."""
    import matplotlib.pyplot as plt

    data = summary.head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(data) + 1.5))
    y = np.arange(len(data))
    ax.barh(y + 0.19, data["down_mean_abs"], height=0.36, label="scaled down")
    ax.barh(y - 0.19, data["up_mean_abs"], height=0.36, label="scaled up")
    ax.set_yticks(y)
    ax.set_yticklabels(data.index)
    ax.set_xlabel("Mean absolute rating change vs baseline")
    ax.legend(loc="lower right")
    ax.set_title("Tornado: effect of each constant on ratings")
    fig.tight_layout()
    return fig
