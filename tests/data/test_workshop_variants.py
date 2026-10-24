"""Check the counterfactual rating services in workshop.lib.variants."""

from __future__ import annotations

import numpy as np
import pytest
from workshop.lib import rating, sweep, variants


@pytest.fixture(scope="module")
def small_pool() -> sweep.Pool:
    """Return the smallest career as a pool, rated once with the live service."""
    return sweep.load_pool(names=["ipswich_3"])


def test_no_supremacy_service_changes_ratings(small_pool: sweep.Pool) -> None:
    """Disabling the supremacy scalar must move some ratings.

    If the service renames the private method this override targets, nothing would
    change and the analysis would silently run against the live algorithm.
    """
    ablated = sweep.rate_pool(small_pool.records, variants.no_supremacy_service())
    ok = np.isfinite(ablated) & np.isfinite(small_pool.baseline)
    assert (np.abs(ablated[ok] - small_pool.baseline[ok]) > 0).any()


def test_no_supremacy_only_removes_the_scalar() -> None:
    """With level xG the scalar is zero anyway, so the two services agree exactly."""
    live = rating.load_service()
    ablated = variants.no_supremacy_service()
    match = {
        "home_team_name": "Ipswich",
        "away_team_name": "Other",
        "home_score": 1,
        "away_score": 1,
        "half_length": 10,
        "home_stats": {"xg": 1.5},
        "away_stats": {"xg": 1.5},
    }
    perf = {
        "performance_type": "Outfield",
        "positions_played": ["CM"],
        "goals": 0,
        "assists": 0,
        "shots": 1,
        "shot_accuracy": 0,
        "passes": 30,
        "pass_accuracy": 85,
        "dribbles": 3,
        "dribble_success_rate": 66,
        "tackles": 2,
        "tackle_success_rate": 50,
        "offsides": 0,
        "fouls_committed": 1,
        "possession_won": 3,
        "possession_lost": 4,
        "minutes_played": 90,
        "distance_covered": 10.5,
        "distance_sprinted": 3.0,
        "player_id": 1,
    }
    assert rating.rate_performance(
        live, "Ipswich", match, perf
    ) == rating.rate_performance(ablated, "Ipswich", match, perf)


def test_siege_bonus_and_dominance_deduction_are_removed() -> None:
    """A dominant team loses its deduction and a besieged team its bonus."""
    live = rating.load_service()
    ablated = variants.no_supremacy_service()
    perf = {
        "performance_type": "Outfield",
        "positions_played": ["CM"],
        "goals": 0,
        "assists": 0,
        "shots": 1,
        "shot_accuracy": 0,
        "passes": 30,
        "pass_accuracy": 85,
        "dribbles": 3,
        "dribble_success_rate": 66,
        "tackles": 2,
        "tackle_success_rate": 50,
        "offsides": 0,
        "fouls_committed": 1,
        "possession_won": 3,
        "possession_lost": 4,
        "minutes_played": 90,
        "distance_covered": 10.5,
        "distance_sprinted": 3.0,
        "player_id": 1,
    }

    def match(team_xg: float, opp_xg: float) -> dict:
        return {
            "home_team_name": "Ipswich",
            "away_team_name": "Other",
            "home_score": 1,
            "away_score": 1,
            "half_length": 10,
            "home_stats": {"xg": team_xg},
            "away_stats": {"xg": opp_xg},
        }

    dominant = match(4.0, 0.2)
    besieged = match(0.2, 4.0)
    assert rating.rate_performance(
        ablated, "Ipswich", dominant, perf
    ) > rating.rate_performance(live, "Ipswich", dominant, perf)
    assert rating.rate_performance(
        ablated, "Ipswich", besieged, perf
    ) < rating.rate_performance(live, "Ipswich", besieged, perf)
