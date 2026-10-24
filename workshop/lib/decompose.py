"""Per-performance decomposition of an outfield rating into its additive parts.

Since the Option A restructure the service builds a single-position rating as::

    rating = clip(base_rating + bonus - supremacy_deduction, 0, 10)

with ``base_rating = sigmoid(dot)``, ``bonus`` the total post-sigmoid position bonus
(goal and assist bonuses plus mastery and the other position modifiers) and
``supremacy_deduction = match_scalar * individual_quality_factor * position_scalar``.
Every part is in rating points, so cross-position differences can be attributed
directly, with no pre-sigmoid caveat.

The parts are captured by a subclass that wraps public-signature-stable internals and
passes everything straight through (``*args, **kwargs`` where possible). The
reconciliation test in ``tests/data/test_workshop_decompose.py`` rebuilds the rating
from the captured parts for every performance, so a service refactor that breaks the
capture fails loudly instead of silently mis-attributing.

Single-position players only: multi-position ratings blend several passes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.services.analytics.match_ratings_service import MatchRatingsService
from workshop.lib import datasets, rating

# Mirrors the literal in MatchRatingsService.calculate_outfield_rating:
#   individual_quality_factor = clip(1 - dot / 1.5, 0, 1)
# The reconciliation test fails if the service changes it.
QUALITY_FACTOR_DOT = 1.5


class DecompositionService(MatchRatingsService):
    """MatchRatingsService that records the parts of every outfield rating."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.captured: dict[str, float] = {}

    def calculate_outfield_rating(self, *args: Any, **kwargs: Any) -> float | None:
        """Reset the capture, then rate as normal."""
        self.captured = {"goal_bonus": 0.0, "assist_bonus": 0.0}
        return super().calculate_outfield_rating(*args, **kwargs)

    def _calculate_dot_product(self, z_scores: Any, weights: Any) -> float:  # noqa: ANN401
        dot = super()._calculate_dot_product(z_scores, weights)
        self.captured["dot"] = float(dot)
        # weights[0] / weights[1] are goals_p90 / assists_p90 (service col_names order)
        self.captured["scoring_dot"] = float(
            z_scores.get("goals_p90_z", 0.0) * weights[0]
            + z_scores.get("assists_p90_z", 0.0) * weights[1]
        )
        return dot

    def _apply_sigmoid_transformation(self, raw_score: float) -> float:
        base = super()._apply_sigmoid_transformation(raw_score)
        self.captured["base_rating"] = float(base)
        return base

    def _apply_pos_modifiers(self, *args: Any, **kwargs: Any) -> float:
        bonus = super()._apply_pos_modifiers(*args, **kwargs)
        self.captured["bonus"] = float(bonus)
        return bonus

    def _calculate_goal_bonus(self, *args: Any, **kwargs: Any) -> float:
        value = super()._calculate_goal_bonus(*args, **kwargs)
        self.captured["goal_bonus"] += float(value)
        return value

    def _calculate_assist_bonus(self, *args: Any, **kwargs: Any) -> float:
        value = super()._calculate_assist_bonus(*args, **kwargs)
        self.captured["assist_bonus"] += float(value)
        return value

    def _calculate_match_supremacy_scalar(self, team_xg: float, xg_against: float) -> float:
        scalar = super()._calculate_match_supremacy_scalar(team_xg, xg_against)
        self.captured["supremacy_scalar"] = float(scalar)
        return scalar


def decompose_outfield(
    tag: str | None = None,
    names: list[str] | None = None,
    config_dir: Path | None = None,
) -> pd.DataFrame:
    """Decompose every rated single-position outfield performance.

    Returns:
        One row per performance with ``career``, ``match_id``, ``player_id``,
        ``position``, ``minutes``, ``goals``, ``assists`` and, in rating points:
        ``dot`` (pre-sigmoid score), ``scoring_dot`` (its goals/assists part),
        ``base_rating``, ``bonus`` split into ``goal_bonus``, ``assist_bonus`` and
        ``other_bonus``, ``supremacy_scalar`` (match level), ``quality_factor``,
        ``supremacy_deduction``, ``unclipped`` and the service's own ``rating``.
    """
    live = rating.load_service(config_dir)
    service = DecompositionService(live.weights, live.means_stds)
    rows = []
    for career in datasets.load_careers(tag, names):
        for match in career.matches:
            for perf in match["player_performances"]:
                positions = perf.get("positions_played", [])
                if perf["performance_type"] != "Outfield" or len(positions) != 1:
                    continue
                final = rating.rate_performance(service, career.club, match["data"], perf)
                if final is None:
                    continue
                c = service.captured
                position = positions[0]
                quality = max(0.0, min(1.0, 1.0 - c["dot"] / QUALITY_FACTOR_DOT))
                position_scalar = (
                    service.CB_SUPREMACY_SCALAR if position == "CB" else 1.0
                )
                deduction = c["supremacy_scalar"] * quality * position_scalar
                rows.append(
                    {
                        "career": career.name,
                        "match_id": match["id"],
                        "player_id": perf["player_id"],
                        "position": position,
                        "minutes": perf.get("minutes_played", 0),
                        "goals": perf.get("goals", 0),
                        "assists": perf.get("assists", 0),
                        "dot": c["dot"],
                        "scoring_dot": c["scoring_dot"],
                        "base_rating": c["base_rating"],
                        "bonus": c["bonus"],
                        "goal_bonus": c["goal_bonus"],
                        "assist_bonus": c["assist_bonus"],
                        "other_bonus": c["bonus"] - c["goal_bonus"] - c["assist_bonus"],
                        "supremacy_scalar": c["supremacy_scalar"],
                        "quality_factor": quality,
                        "supremacy_deduction": deduction,
                        "unclipped": c["base_rating"] + c["bonus"] - deduction,
                        "rating": final,
                    }
                )
    return pd.DataFrame(rows)
