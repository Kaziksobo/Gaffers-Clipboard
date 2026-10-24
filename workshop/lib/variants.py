"""Counterfactual rating services used by validation analyses.

These override a single private method of ``MatchRatingsService``. If the service ever
renames that method the tests in ``tests/data/test_workshop_variants.py`` fail loudly,
rather than the analysis silently running against the unmodified algorithm.

For sweeps over class constants use ``workshop.lib.sweep`` instead; the supremacy
scalar's gamma and caps are hard-coded inside the method, so it cannot be swept.
"""

from __future__ import annotations

from pathlib import Path

from src.services.analytics.match_ratings_service import MatchRatingsService
from workshop.lib import rating


class NoSupremacyService(MatchRatingsService):
    """MatchRatingsService with the match supremacy scalar neutralised.

    The counterfactual used to isolate how much of rating's correlation with xG
    dominance is attributable to the supremacy scalar itself.
    """

    def _calculate_match_supremacy_scalar(
        self, team_xg: float, xg_against: float
    ) -> float:
        """Return zero so no supremacy deduction (or siege bonus) is applied."""
        return 0.0


def no_supremacy_service(config_dir: Path | None = None) -> MatchRatingsService:
    """Build a no-supremacy service from the live (or a candidate) config."""
    base = rating.load_service(config_dir)
    return NoSupremacyService(base.weights, base.means_stds)
