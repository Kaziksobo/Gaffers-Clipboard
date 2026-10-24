"""Check the rating decomposition reconciles with the service for every performance."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from workshop.lib import decompose, rating

from src.services.analytics.match_ratings_service import MatchRatingsService


@pytest.fixture(scope="module")
def parts() -> pd.DataFrame:
    """Decompose every single-position outfield performance in every career."""
    return decompose.decompose_outfield("pool")


def test_parts_rebuild_the_rating_exactly(parts: pd.DataFrame) -> None:
    """clip(base + bonus - deduction, 0, 10), rounded, equals the service's rating.

    This is the guard for the capture hooks: if the service restructures how a rating
    is assembled, some rows stop reconciling and this fails.
    """
    rebuilt = np.round(np.clip(parts["unclipped"], 0.0, 10.0), 1)
    bad = parts[rebuilt != parts["rating"]]
    assert bad.empty, bad[["career", "match_id", "player_id", "rating"]].head()


def test_decomposition_matches_the_plain_service(parts: pd.DataFrame) -> None:
    """Capturing does not change any rating."""
    plain = rating.rated_performances("pool")[
        ["career", "match_id", "player_id", "rating"]
    ].rename(columns={"rating": "plain_rating"})
    merged = parts.merge(plain, on=["career", "match_id", "player_id"], validate="1:1")
    assert (merged["rating"] == merged["plain_rating"]).all()


def test_only_rated_single_position_outfield_rows_are_kept(parts: pd.DataFrame) -> None:
    """Row count equals the rated single-position outfield performances."""
    frame = rating.rated_performances("pool")
    expected = frame[
        (frame["performance_type"] == "Outfield")
        & (frame["n_positions"] == 1)
        & frame["rating"].notna()
    ]
    assert len(parts) == len(expected)


def test_event_bonuses_are_non_negative_and_within_their_caps(
    parts: pd.DataFrame,
) -> None:
    """A double-counted capture would push a bonus past its cap."""
    assert (parts["goal_bonus"] >= 0).all()
    assert (parts["assist_bonus"] >= 0).all()
    assert (parts["goal_bonus"] <= MatchRatingsService.GOAL_BONUS_CAP + 1e-9).all()
    assert (parts["assist_bonus"] <= MatchRatingsService.ASSIST_BONUS_CAP + 1e-9).all()


def test_no_goal_bonus_without_a_goal(parts: pd.DataFrame) -> None:
    """Goal and assist bonuses only exist for performances with goals or assists."""
    assert (parts.loc[parts["goals"] < 1, "goal_bonus"] == 0).all()
    assert (parts.loc[parts["assists"] < 1, "assist_bonus"] == 0).all()


def test_scoring_dot_is_part_of_the_dot_product(parts: pd.DataFrame) -> None:
    """The dot product and its goals/assists share are finite."""
    assert np.isfinite(parts[["dot", "scoring_dot"]]).all().all()


def test_the_quality_factor_stays_in_the_unit_interval(parts: pd.DataFrame) -> None:
    """The share of a dominant-team deduction applied stays within 0 to 1."""
    assert parts["quality_factor"].between(0.0, 1.0).all()
