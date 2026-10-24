"""Check the CB/CDM defensive quality bonus, retention schedule and collapse."""

from __future__ import annotations

import copy

import pytest
from workshop.lib import datasets, rating

from src.services.analytics.match_ratings_service import MatchRatingsService

_ELITE_Z = {
    "tackles_p90_z": 3.0,
    "tackle_success_rate_z": 3.0,
    "possession_won_p90_z": 3.0,
    "possession_lost_p90_z": 3.0,
    "passes_p90_z": 3.0,
    "pass_accuracy_z": 3.0,
}


@pytest.fixture(scope="module")
def service() -> MatchRatingsService:
    """Return the live rating service."""
    return rating.load_service()


def test_retention_follows_the_schedule_and_never_rises(
    service: MatchRatingsService,
) -> None:
    """Retention is 1, 1, 0.6, 0.2, 0 by goals conceded and never increases."""
    for xg in (0.1, 0.8, 1.4, 2.5, 4.0, 9.0):
        series = [service._defensive_retention(g, xg) for g in range(7)]
        assert series == sorted(series, reverse=True), (xg, series)
        assert series[4:] == [0.0, 0.0, 0.0]
    assert service._defensive_retention(0, 3.0) == 1.0
    assert service._defensive_retention(1, 3.0) == 1.0
    assert service._defensive_retention(2, 3.0) == pytest.approx(0.6)
    assert service._defensive_retention(3, 5.0) == pytest.approx(0.2)


def test_goals_from_low_quality_chances_keep_a_little_more(
    service: MatchRatingsService,
) -> None:
    """The uplift applies when opponent xG is at most half the goals, never at 4+."""
    assert service._defensive_retention(2, 0.9) == pytest.approx(0.7)
    assert service._defensive_retention(2, 1.1) == pytest.approx(0.6)
    assert service._defensive_retention(3, 1.5) == pytest.approx(0.3)
    assert service._defensive_retention(4, 0.1) == 0.0


@pytest.mark.parametrize("pos", ["CB", "CDM"])
def test_quality_is_zero_for_average_play_and_for_short_cameos(
    service: MatchRatingsService, pos: str
) -> None:
    """Only a strong full game earns quality; under 30 minutes earns none."""
    assert service._defensive_quality(pos, dict.fromkeys(_ELITE_Z, 0.0), 90) == 0.0
    assert service._defensive_quality(pos, _ELITE_Z, 29) == 0.0
    assert service._defensive_quality(pos, _ELITE_Z, 30) == 1.0
    assert 0.0 < service._defensive_quality(pos, dict.fromkeys(_ELITE_Z, 0.8), 90) < 1


@pytest.mark.parametrize("pos", ["CB", "CDM"])
def test_quality_bonus_is_quality_times_impact_times_retention(
    service: MatchRatingsService, pos: str
) -> None:
    """The bonus multiplies the three factors and shrinks with goals conceded."""
    full = service._apply_defensive_quality_bonus(pos, _ELITE_Z, 0, 0.5, 90, 1.0)
    assert full == pytest.approx(service.DEF_QUALITY_WEIGHT)
    half = service._apply_defensive_quality_bonus(pos, _ELITE_Z, 0, 0.5, 90, 0.5)
    assert half == pytest.approx(0.5 * full)
    two = service._apply_defensive_quality_bonus(pos, _ELITE_Z, 2, 3.0, 90, 1.0)
    assert two == pytest.approx(0.6 * full)
    assert service._apply_defensive_quality_bonus(pos, _ELITE_Z, 4, 3.0, 90, 1.0) == 0


@pytest.mark.parametrize("pos", ["CB", "CDM"])
def test_conceding_three_costs_an_elite_defender_much_more_than_one(
    service: MatchRatingsService, pos: str
) -> None:
    """One goal conceded keeps most of an elite bonus; three loses nearly all."""
    method = (
        service._apply_cb_modifiers if pos == "CB" else service._apply_cdm_modifiers
    )
    args = {
        "z_scores": _ELITE_Z,
        "opponent_xg": 2.5,
        "performance_metrics": {},
        "minutes_played": 90,
        "impact_scalar": 1.0,
    }
    clean = method(opponent_goals=0, **args)
    one = method(opponent_goals=1, **args)
    three = method(opponent_goals=3, **args)
    assert clean > one > three
    assert one - three >= 0.8
    assert clean - one <= 0.6


def _with_opponent_goals(data: dict, club: str, goals: int) -> dict:
    changed = copy.deepcopy(data)
    key = "away_score" if changed["home_team_name"] == club else "home_score"
    changed[key] = goals
    return changed


def test_real_defenders_never_gain_rating_by_conceding_more(
    service: MatchRatingsService,
) -> None:
    """Re-scoring real CB/CDM games with 0..5 goals against is non-increasing."""
    checked = 0
    for name in ("arsenal_2", "ipswich_3"):
        career = datasets.load_career(name)
        for match in career.matches[:12]:
            for performance in match["player_performances"]:
                positions = performance.get("positions_played", [])
                if performance["performance_type"] != "Outfield" or positions not in (
                    ["CB"],
                    ["CDM"],
                ):
                    continue
                series = []
                for goals in range(6):
                    data = _with_opponent_goals(match["data"], career.club, goals)
                    series.append(
                        rating.rate_performance(service, career.club, data, performance)
                    )
                if None in series:
                    continue
                assert series == sorted(series, reverse=True), (
                    name,
                    match["id"],
                    series,
                )
                checked += 1
    assert checked > 30
