"""Hold-out gate: is a refit config non-inferior to a baseline on an unseen career?

The gate compares two configs (a baseline and a candidate) on career data that neither was
fitted on. Two primary metrics, both Spearman correlations of rating with goal difference
on outfield performances:

- **team-level**: match-average rating vs goal difference, paired bootstrap over matches;
- **player-level**: individual rating vs goal difference, cluster bootstrap over matches.

For each, the candidate passes if the lower bound of the 95% interval of
``rho(candidate) - rho(baseline)`` is above ``-NON_INFERIORITY_MARGIN``. The gate asks
"not worse", not "better": a refit that barely moves the weights cannot show a gain, and
the interval has to rule out a meaningful loss. Position-level results are descriptive
and are not part of the gate (hold-out cells are too small).

Secondary, never gated: rating vs xG differential (team level).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from workshop.lib import inference, rating

NON_INFERIORITY_MARGIN = 0.05
_KEYS = ["career", "match_id", "player_id"]


def non_inferior(ci_low: float, margin: float = NON_INFERIORITY_MARGIN) -> bool:
    """Return whether a difference interval rules out a loss larger than ``margin``.

    Only the lower bound matters: a positive point estimate with a wide interval that
    reaches below ``-margin`` still fails.
    """
    return ci_low > -margin


@dataclass(frozen=True)
class MetricResult:
    """One metric compared between baseline and candidate."""

    name: str
    gated: bool
    baseline_rho: float
    candidate_rho: float
    delta: float
    ci_low: float
    ci_high: float
    passes: bool | None  # None for ungated metrics


@dataclass(frozen=True)
class GateResult:
    """All metrics for one hold-out, plus the overall verdict."""

    holdout: list[str]
    n_matches: int
    n_rows: int
    margin: float
    metrics: list[MetricResult]

    @property
    def passes(self) -> bool:
        """True when every gated metric passes."""
        return all(m.passes for m in self.metrics if m.gated)

    def to_frame(self) -> pd.DataFrame:
        """One row per metric."""
        return pd.DataFrame([m.__dict__ for m in self.metrics]).set_index("name")


def _rated(names: list[str], config_dir: Path, column: str) -> pd.DataFrame:
    frame = rating.rated_performances(names=names, config_dir=config_dir, column=column)
    frame = frame[(frame["performance_type"] == "Outfield") & frame[column].notna()]
    return frame[
        [*_KEYS, column, "team_score", "opp_score", "team_xg", "opp_xg"]
    ].copy()


def evaluate(
    holdout: list[str],
    baseline_dir: Path,
    candidate_dir: Path,
    margin: float = NON_INFERIORITY_MARGIN,
    n_resamples: int = inference.DEFAULT_RESAMPLES,
    seed: int = inference.DEFAULT_SEED,
) -> GateResult:
    """Compare a candidate config with a baseline config on hold-out career(s).

    Args:
        holdout: Career names neither config was fitted on.
        baseline_dir: Config directory of the baseline (for example ``config/``).
        candidate_dir: Config directory of the candidate.
        margin: Non-inferiority margin for the gated metrics.
        n_resamples: Bootstrap resamples.
        seed: Bootstrap seed.
    """
    base = _rated(holdout, baseline_dir, "base")
    cand = _rated(holdout, candidate_dir, "cand")
    both = base.merge(
        cand[[*_KEYS, "cand"]], on=_KEYS, validate="one_to_one"
    ).assign(match_key=lambda d: d["career"] + ":" + d["match_id"].astype(str))
    both["goal_diff"] = both["team_score"] - both["opp_score"]
    both["xg_diff"] = both["team_xg"] - both["opp_xg"]

    teams = both.groupby("match_key").agg(
        base=("base", "mean"),
        cand=("cand", "mean"),
        goal_diff=("goal_diff", "first"),
        xg_diff=("xg_diff", "first"),
    )

    def team_metric(name: str, criterion: str, gated: bool) -> MetricResult:
        b = inference.bootstrap_spearman(
            teams["base"], teams[criterion], n_resamples, seed
        )
        c = inference.bootstrap_spearman(
            teams["cand"], teams[criterion], n_resamples, seed
        )
        d = inference.paired_delta_rho(
            teams["base"], teams["cand"], teams[criterion], n_resamples, seed
        )
        return MetricResult(
            name, gated, b.estimate, c.estimate, d.estimate, d.ci_low, d.ci_high,
            non_inferior(d.ci_low, margin) if gated else None,
        )  # fmt: skip

    pb = inference.cluster_bootstrap_spearman(
        both["base"], both["goal_diff"], both["match_key"], n_resamples, seed
    )
    pc = inference.cluster_bootstrap_spearman(
        both["cand"], both["goal_diff"], both["match_key"], n_resamples, seed
    )
    pd_ = inference.cluster_paired_delta_rho(
        both["base"], both["cand"], both["goal_diff"], both["match_key"], n_resamples, seed
    )
    player = MetricResult(
        "player-level rho vs goal difference", True, pb.estimate, pc.estimate,
        pd_.estimate, pd_.ci_low, pd_.ci_high, non_inferior(pd_.ci_low, margin),
    )  # fmt: skip
    metrics = [
        team_metric("team-level rho vs goal difference", "goal_diff", True),
        player,
        team_metric("team-level rho vs xG differential (secondary)", "xg_diff", False),
    ]
    return GateResult(holdout, len(teams), len(both), margin, metrics)
