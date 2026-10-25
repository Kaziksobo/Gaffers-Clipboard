"""Check the fullback style bonus, its retention, collapse penalty and clean sheet."""

from __future__ import annotations

import copy

import pytest
from workshop.lib import datasets, rating

from src.services.analytics.match_ratings_service import MatchRatingsService

_STOPPER_KEYS = (
    "tackles_p90_z",
    "tackle_success_rate_z",
    "possession_won_p90_z",
    "possession_lost_p90_z",
)
_ATTACKING_KEYS = (
    "dribbles_p90_z",
    "dribble_success_rate_z",
    "distance_sprinted_p90_z",
    "xt_bonus_p90_z",
    "passes_p90_z",
    "pass_accuracy_z",
)
_STOPPER_Z = dict.fromkeys(_STOPPER_KEYS, 3.0)
_ATTACKING_Z = dict.fromkeys(_ATTACKING_KEYS, 3.0)
_AVERAGE_Z = dict.fromkeys((*_STOPPER_KEYS, *_ATTACKING_KEYS), 0.0)


@pytest.fixture(scope="module")
def service() -> MatchRatingsService:
    """Return the live rating service."""
    return rating.load_service()


def test_retention_tables_follow_the_schedules_and_never_rise(
    service: MatchRatingsService,
) -> None:
    """The stopper keeps less than the attacking style as goals go in."""
    stopper = [
        service._defensive_retention(g, service.FB_STOPPER_RETENTION) for g in range(7)
    ]
    attacking = [
        service._defensive_retention(g, service.FB_ATTACKING_RETENTION)
        for g in range(7)
    ]
    assert stopper == pytest.approx([1.0, 1.0, 0.7, 0.4, 0.0, 0.0, 0.0])
    assert attacking == pytest.approx([1.0, 1.0, 0.85, 0.6, 0.4, 0.4, 0.4])
    assert all(a >= s for a, s in zip(attacking, stopper, strict=True))


@pytest.mark.parametrize("style", ["Stopper", "Attacking"])
def test_style_quality_is_zero_for_average_play_and_short_cameos(
    service: MatchRatingsService, style: str
) -> None:
    """Only a strong full game earns style quality; under 30 minutes earns none."""
    assert service._fb_style_quality(style, _AVERAGE_Z, 90) == 0.0
    elite = _STOPPER_Z if style == "Stopper" else _ATTACKING_Z
    assert service._fb_style_quality(style, elite, 29) == 0.0
    assert service._fb_style_quality(style, elite, 30) == 1.0


def test_the_bonus_pays_the_better_style_not_the_sum(
    service: MatchRatingsService,
) -> None:
    """With both styles elite, the larger single bonus is paid."""
    both = {**_STOPPER_Z, **_ATTACKING_Z}
    clean = service._apply_fb_style_bonus(both, 0, 90, 1.0)
    assert clean == pytest.approx(max(service.FB_STYLE_WEIGHT.values()))
    only_attacking = service._apply_fb_style_bonus(_ATTACKING_Z, 0, 90, 1.0)
    assert only_attacking == pytest.approx(service.FB_STYLE_WEIGHT["Attacking"])
    # four goals conceded: the stopper keeps nothing, the attacking style keeps 40%
    after_four = service._apply_fb_style_bonus(both, 4, 90, 1.0)
    assert after_four == pytest.approx(0.4 * service.FB_STYLE_WEIGHT["Attacking"])


def _modifiers(service: MatchRatingsService, goals: int, xg: float, z: dict) -> float:
    return service._apply_fb_modifiers(
        z_scores=z,
        opponent_goals=goals,
        opponent_xg=xg,
        performance_metrics={},
        minutes_played=90,
        impact_scalar=1.0,
    )


def test_collapse_penalty_is_the_shared_defender_value(
    service: MatchRatingsService,
) -> None:
    """Conceding three costs a flat 0.30 more than conceding two (no style bonus)."""
    two = _modifiers(service, 2, 2.5, _AVERAGE_Z)
    three = _modifiers(service, 3, 2.5, _AVERAGE_Z)
    assert three - two == pytest.approx(-service.DEF_COLLAPSE_PENALTY)


def test_clean_sheet_uses_the_raised_fullback_ratio(
    service: MatchRatingsService,
) -> None:
    """An average fullback's clean sheet is the CB tier times the 0.7 ratio."""
    clean = _modifiers(service, 0, 0.5, _AVERAGE_Z)
    assert clean == pytest.approx(service.CS_CB_LOW_XG * 0.7)
    assert service.CS_RATIOS["RB"] == service.CS_RATIOS["LB"] == pytest.approx(0.7)


def test_attacking_style_keeps_a_larger_share_of_its_bonus_when_conceding(
    service: MatchRatingsService,
) -> None:
    """Three conceded: the stopper keeps 40% of its bonus, the attacking style 60%."""
    kept = {}
    for style, z in (("Stopper", _STOPPER_Z), ("Attacking", _ATTACKING_Z)):
        clean = service._apply_fb_style_bonus(z, 0, 90, 1.0)
        three = service._apply_fb_style_bonus(z, 3, 90, 1.0)
        kept[style] = three / clean
    assert kept["Stopper"] == pytest.approx(0.4)
    assert kept["Attacking"] == pytest.approx(0.6)


def _with_opponent_goals(data: dict, club: str, goals: int) -> dict:
    changed = copy.deepcopy(data)
    key = "away_score" if changed["home_team_name"] == club else "home_score"
    changed[key] = goals
    return changed


def test_real_fullbacks_never_gain_rating_by_conceding_more(
    service: MatchRatingsService,
) -> None:
    """Re-scoring real fullback games with 0..5 goals against is non-increasing."""
    checked = 0
    for name in ("arsenal_2", "ipswich_3"):
        career = datasets.load_career(name)
        for match in career.matches[:12]:
            for performance in match["player_performances"]:
                positions = performance.get("positions_played", [])
                if performance["performance_type"] != "Outfield" or positions not in (
                    ["LB"],
                    ["RB"],
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
    assert checked > 20
