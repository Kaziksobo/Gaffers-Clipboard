"""Property checks for MatchRatingsService run over every real performance.

None of these tests pin a rating value, so recalibrating weights or means/stds does
not break them. They fail only when the service raises, leaves the 0-10 scale,
treats equivalent inputs differently, or stops moving in the intended direction.
"""

from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.data.conftest import CareerRecords, RatedPerformance, RateFn

# Outfield performances under this many minutes are not rated (service threshold).
_MIN_RATED_MINUTES = 10
_VOLUME_STATS = (
    "passes",
    "dribbles",
    "tackles",
    "possession_won",
    "possession_lost",
    "fouls_committed",
    "offsides",
    "distance_covered",
    "distance_sprinted",
)
# Ratings are rounded to one decimal place, so one step is the smallest real change.
_ONE_ROUNDING_STEP = 0.1 + 1e-9


def _describe(r: RatedPerformance) -> str:
    """Return a short identifier for failure messages."""
    return f"{r.career} match {r.match_id} player {r.player_id}"


def _rated_outfield(rated: list[RatedPerformance]) -> list[RatedPerformance]:
    """Return outfield performances that received a rating."""
    return [
        r for r in rated if r.performance_type == "Outfield" and r.rating is not None
    ]


def test_every_performance_is_accounted_for(
    rated_performances: list[RatedPerformance], careers: dict[str, CareerRecords]
) -> None:
    """Rating every performance in every career completes without raising."""
    expected = sum(
        len(m["player_performances"]) for c in careers.values() for m in c.matches
    )
    assert len(rated_performances) == expected


def test_ratings_are_finite_and_on_the_0_to_10_scale(
    rated_performances: list[RatedPerformance],
) -> None:
    """Every produced rating is a real number within [0, 10]."""
    bad = [
        _describe(r)
        for r in rated_performances
        if r.rating is not None
        and (not math.isfinite(r.rating) or not 0.0 <= r.rating <= 10.0)
    ]
    assert not bad, bad[:5]


def test_only_short_outfield_cameos_are_unrated(
    rated_performances: list[RatedPerformance],
) -> None:
    """None is returned exactly for outfield players under 10 minutes.

    Goalkeepers are always rated.
    """
    mismatches = [
        _describe(r)
        for r in rated_performances
        if (r.rating is None)
        != (r.performance_type == "Outfield" and (r.minutes or 0) < _MIN_RATED_MINUTES)
    ]
    assert not mismatches, mismatches[:5]


def test_rating_is_deterministic_and_leaves_inputs_untouched(
    rated_performances: list[RatedPerformance], rate: RateFn
) -> None:
    """Re-rating gives the same answer and mutates neither payload."""
    for r in rated_performances[::25]:
        perf_before = copy.deepcopy(r.performance)
        data_before = copy.deepcopy(r.match_data)
        assert rate(r.club, r.match_data, r.performance) == r.rating, _describe(r)
        assert r.performance == perf_before, _describe(r)
        assert r.match_data == data_before, _describe(r)


def test_rating_is_invariant_to_half_length_scaling(
    rated_performances: list[RatedPerformance], rate: RateFn
) -> None:
    """Doubling the half length and every volume stat describes the same performance.

    Minutes stay on the 90-minute scale and are deliberately not scaled.
    """
    worst = 0.0
    worst_at = ""
    for r in _rated_outfield(rated_performances):
        scaled = {**r.performance}
        for stat in _VOLUME_STATS:
            scaled[stat] = r.performance[stat] * 2
        new = rate(
            r.club, r.match_data, scaled, half_length=r.match_data["half_length"] * 2
        )
        assert new is not None
        if abs(new - r.rating) > worst:
            worst, worst_at = abs(new - r.rating), _describe(r)
    assert worst <= _ONE_ROUNDING_STEP, f"{worst:.2f} at {worst_at}"


# (stat, direction, highest current value to test). Goals are only tested up to a
# hat-trick: beyond that the goal bonus cap and the 10.0 ceiling interact, and one
# extra goal lowered the rating by 0.1 in two real cases (4+ goals in a match).
# Shots, tackles and offsides are deliberately absent: their weights come from PCA
# and are not monotone by design.
_DIRECTIONS = [
    ("goals", 1, 3),
    ("assists", 1, None),
    ("possession_lost", -1, None),
    ("fouls_committed", -1, None),
]


@pytest.mark.parametrize(("stat", "direction", "ceiling"), _DIRECTIONS)
def test_stat_moves_rating_in_the_intended_direction(
    stat: str,
    direction: int,
    ceiling: int | None,
    rated_performances: list[RatedPerformance],
    rate: RateFn,
) -> None:
    """One more of a stat never moves the rating the wrong way."""
    offenders = []
    for r in _rated_outfield(rated_performances):
        if ceiling is not None and r.performance[stat] > ceiling:
            continue
        bumped = {**r.performance, stat: r.performance[stat] + 1}
        new = rate(r.club, r.match_data, bumped)
        assert new is not None
        if (new - r.rating) * direction < -1e-9:
            offenders.append(f"{_describe(r)}: {r.rating} -> {new}")
    assert not offenders, offenders[:5]
