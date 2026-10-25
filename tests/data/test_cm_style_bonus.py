"""Check the central midfielder style bonus: quality, retention and its results."""

from __future__ import annotations

import copy

import pytest
from workshop.lib import datasets, rating

from src.services.analytics.match_ratings_service import MatchRatingsService

_BALL_WINNER_KEYS = (
    "tackles_p90_z",
    "tackle_success_rate_z",
    "possession_won_p90_z",
    "possession_lost_p90_z",
)
_CREATIVE_KEYS = (
    "passes_p90_z",
    "pass_accuracy_z",
    "xt_bonus_p90_z",
    "dribbles_p90_z",
    "dribble_success_rate_z",
    "distance_sprinted_p90_z",
)
_BALL_WINNER_Z = dict.fromkeys(_BALL_WINNER_KEYS, 3.0)
_CREATIVE_Z = dict.fromkeys(_CREATIVE_KEYS, 3.0)
_AVERAGE_Z = dict.fromkeys((*_BALL_WINNER_KEYS, *_CREATIVE_KEYS), 0.0)


@pytest.fixture(scope="module")
def service() -> MatchRatingsService:
    """Return the live rating service."""
    return rating.load_service()


def test_retention_tables_follow_the_schedules_and_never_rise(
    service: MatchRatingsService,
) -> None:
    """Ball-winner keeps less than creative as goals go in."""
    ball_winner = [
        service._defensive_retention(g, 9.0, service.CM_BALLWINNER_RETENTION)
        for g in range(7)
    ]
    creative = [
        service._defensive_retention(g, 9.0, service.CM_CREATIVE_RETENTION)
        for g in range(7)
    ]
    assert ball_winner == pytest.approx([1.0, 1.0, 0.7, 0.4, 0.0, 0.0, 0.0])
    assert creative == pytest.approx([1.0, 1.0, 0.85, 0.6, 0.4, 0.4, 0.4])


@pytest.mark.parametrize("style", ["BallWinner", "Creative"])
def test_style_quality_is_zero_for_average_play_and_short_cameos(
    service: MatchRatingsService, style: str
) -> None:
    """Only a very elite full game earns style quality; under 30 minutes earns none."""
    elite = _BALL_WINNER_Z if style == "BallWinner" else _CREATIVE_Z
    assert service._cm_style_quality(style, _AVERAGE_Z, 90) == 0.0
    assert service._cm_style_quality(style, elite, 29) == 0.0
    assert service._cm_style_quality(style, elite, 30) == 1.0


def test_the_bonus_pays_the_better_style_not_the_sum(
    service: MatchRatingsService,
) -> None:
    """With both styles elite the larger single bonus is paid."""
    both = {**_BALL_WINNER_Z, **_CREATIVE_Z}
    clean = service._apply_cm_style_bonus(both, 0, 0.5, 90, 1.0)
    assert clean == pytest.approx(max(service.CM_STYLE_WEIGHT.values()))
    only_creative = service._apply_cm_style_bonus(_CREATIVE_Z, 0, 0.5, 90, 1.0)
    assert only_creative == pytest.approx(service.CM_STYLE_WEIGHT["Creative"])
    after_four = service._apply_cm_style_bonus(both, 4, 4.0, 90, 1.0)
    assert after_four == pytest.approx(0.4 * service.CM_STYLE_WEIGHT["Creative"])


def _modifiers(service: MatchRatingsService, goals: int, xg: float, z: dict) -> float:
    return service._apply_cm_modifiers(
        z_scores=z,
        opponent_goals=goals,
        opponent_xg=xg,
        performance_metrics={},
        minutes_played=90,
        impact_scalar=1.0,
    )


def test_cm_has_no_collapse_penalty(service: MatchRatingsService) -> None:
    """Conceding three costs an average CM nothing beyond the lost clean sheet."""
    assert _modifiers(service, 3, 2.5, _AVERAGE_Z) == pytest.approx(
        _modifiers(service, 2, 2.5, _AVERAGE_Z)
    )


def test_clean_sheet_ratio_is_unchanged(service: MatchRatingsService) -> None:
    """An average CM's clean sheet is still the CB tier times 0.36."""
    clean = _modifiers(service, 0, 0.5, _AVERAGE_Z)
    assert clean == pytest.approx(service.CS_CB_LOW_XG * 0.36)


def test_a_very_elite_game_without_goal_contribution_rates_well(
    service: MatchRatingsService,
) -> None:
    """The style bonus alone lifts an elite game by more than a point."""
    assert _modifiers(service, 0, 0.5, _CREATIVE_Z) - _modifiers(
        service, 0, 0.5, _AVERAGE_Z
    ) == pytest.approx(service.CM_STYLE_WEIGHT["Creative"])


def _with_opponent_goals(data: dict, club: str, goals: int) -> dict:
    changed = copy.deepcopy(data)
    key = "away_score" if changed["home_team_name"] == club else "home_score"
    changed[key] = goals
    return changed


def test_real_cms_never_gain_rating_by_conceding_more(
    service: MatchRatingsService,
) -> None:
    """Re-scoring real CM games with 0..5 goals against is non-increasing."""
    checked = 0
    for name in ("arsenal_2", "ipswich_3"):
        career = datasets.load_career(name)
        for match in career.matches[:14]:
            for performance in match["player_performances"]:
                if performance["performance_type"] != "Outfield" or performance.get(
                    "positions_played"
                ) != ["CM"]:
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
    assert checked > 15
