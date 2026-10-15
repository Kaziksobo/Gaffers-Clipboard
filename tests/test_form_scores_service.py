"""Tests for FormScoresService EMA, absence decay, and form score scaling."""

from __future__ import annotations

import copy
import datetime as dt

import pytest

from src.contracts.analytics import PlayerRatingHistory, RatedAppearance
from src.services.analytics.form_scores_service import FormScoresService

_BASE_DATE = dt.datetime(2031, 8, 1)


def _appearance(index: int, rating: float) -> RatedAppearance:
    """Return a rated appearance whose match id and date increase with index."""
    return RatedAppearance(
        match_id=100 + index,
        in_game_date=_BASE_DATE + dt.timedelta(days=7 * index),
        rating=rating,
    )


def _history(ratings: list[float], missed: int = 0) -> PlayerRatingHistory:
    """Return a rating history with chronological appearances for the ratings."""
    return PlayerRatingHistory(
        player_id=7,
        player_name="Test Player",
        appearances=[_appearance(i + 1, r) for i, r in enumerate(ratings)],
        matches_since_last_rated=missed,
    )


@pytest.fixture
def service() -> FormScoresService:
    """Return a FormScoresService instance."""
    return FormScoresService()


# ── Minimum-appearance gate ───────────────────────────────────────────────────────


@pytest.mark.parametrize("count", [0, 1, 2])
def test_calculate_player_form_below_minimum_returns_empty_form(
    service: FormScoresService, count: int
) -> None:
    """Fewer than the minimum rated appearances yields no series, value or score."""
    form = service.calculate_player_form(_history([6.5] * count, missed=3))

    assert form["series"] == []
    assert form["current"] is None
    assert form["form_score"] is None
    assert form["rated_count"] == count
    assert form["matches_since_last_rated"] == 3


def test_calculate_player_form_at_minimum_returns_form(
    service: FormScoresService,
) -> None:
    """Exactly the minimum appearances gives a single series point and a result."""
    form = service.calculate_player_form(_history([6.5] * 3))

    assert len(form["series"]) == 1
    assert form["current"] is not None
    assert form["form_score"] is not None
    assert form["rated_count"] == 3


def test_calculate_player_form_echoes_identity_fields(
    service: FormScoresService,
) -> None:
    """Player id and name are copied through to the result."""
    form = service.calculate_player_form(_history([6.5] * 3))

    assert form["player_id"] == 7
    assert form["player_name"] == "Test Player"


# ── Series ────────────────────────────────────────────────────────────────────────


def test_calculate_player_form_series_starts_from_third_appearance(
    service: FormScoresService,
) -> None:
    """The series skips the first two points but keeps every later one."""
    form = service.calculate_player_form(_history([6.0, 6.5, 7.0, 7.5, 6.5, 8.0]))

    assert len(form["series"]) == 4
    assert form["series"][0]["match_id"] == 103
    assert form["series"][-1]["match_id"] == 106


def test_calculate_player_form_series_points_carry_match_data(
    service: FormScoresService,
) -> None:
    """Each series point keeps its match id, date, and raw rating."""
    history = _history([7.0, 7.5, 8.0, 6.5, 7.0])
    displayed = history["appearances"][FormScoresService.MIN_APPEARANCES - 1 :]

    form = service.calculate_player_form(history)

    for point, appearance in zip(form["series"], displayed, strict=True):
        assert point["match_id"] == appearance["match_id"]
        assert point["in_game_date"] == appearance["in_game_date"]
        assert point["rating"] == appearance["rating"]


def test_calculate_player_form_ema_values_match_hand_calculation(
    service: FormScoresService,
) -> None:
    """EMA values match a hand calculation (ALPHA=0.3, seeded at 6.0)."""
    form = service.calculate_player_form(_history([7.0, 7.5, 8.0, 6.5]))

    # Hidden first two points: 6.3, 6.66. Displayed: 7.062, then 6.8934.
    assert [p["ema"] for p in form["series"]] == pytest.approx([7.062, 6.8934])


def test_calculate_player_form_neutral_ratings_stay_neutral(
    service: FormScoresService,
) -> None:
    """Ratings of exactly the neutral value leave the EMA, current and score flat."""
    form = service.calculate_player_form(_history([6.0] * 5))

    assert [p["ema"] for p in form["series"]] == pytest.approx([6.0] * 3)
    assert form["current"] == pytest.approx(6.0)
    assert form["form_score"] == pytest.approx(0.0)


# ── Absence decay ─────────────────────────────────────────────────────────────────


def test_calculate_player_form_no_absence_leaves_current_undecayed(
    service: FormScoresService,
) -> None:
    """With zero missed matches the current value equals the last EMA point."""
    form = service.calculate_player_form(_history([7.0, 7.5, 8.0], missed=0))

    assert form["current"] == pytest.approx(form["series"][-1]["ema"])


def test_calculate_player_form_decay_matches_hand_calculation(
    service: FormScoresService,
) -> None:
    """Four missed matches decay 7.062 toward 6.0 (DECAY=0.9, SATURATION_UP=2.0)."""
    form = service.calculate_player_form(_history([7.0, 7.5, 8.0], missed=4))

    assert form["current"] == pytest.approx(6.0 + 1.062 * 0.9**4)
    assert form["form_score"] == pytest.approx(1.062 * 0.9**4 / 2.0)


def test_calculate_player_form_decay_leaves_series_untouched(
    service: FormScoresService,
) -> None:
    """Absence decays only the current value, never the series points."""
    fresh = service.calculate_player_form(_history([7.0, 7.5, 8.0], missed=0))
    absent = service.calculate_player_form(_history([7.0, 7.5, 8.0], missed=6))

    assert absent["series"] == fresh["series"]
    assert absent["current"] != fresh["current"]


def test_calculate_player_form_decay_pulls_good_form_down_toward_neutral(
    service: FormScoresService,
) -> None:
    """Above-average form drops toward 6.0 but stays above it."""
    form = service.calculate_player_form(_history([8.0] * 4, missed=3))

    assert form["current"] is not None
    assert 6.0 < form["current"] < form["series"][-1]["ema"]


def test_calculate_player_form_decay_pulls_bad_form_up_toward_neutral(
    service: FormScoresService,
) -> None:
    """Below-average form recovers toward 6.0 but stays below it."""
    form = service.calculate_player_form(_history([4.0] * 4, missed=3))

    assert form["current"] is not None
    assert form["series"][-1]["ema"] < form["current"] < 6.0


def test_calculate_player_form_long_absence_converges_to_neutral(
    service: FormScoresService,
) -> None:
    """A very long absence decays current form to exactly average."""
    form = service.calculate_player_form(_history([9.0] * 5, missed=500))

    assert form["current"] == pytest.approx(6.0, abs=1e-6)
    assert form["form_score"] == pytest.approx(0.0, abs=1e-6)


# ── Form score scaling ────────────────────────────────────────────────────────────


def test_calculate_player_form_score_mid_range_is_linear(
    service: FormScoresService,
) -> None:
    """A mid-range EMA above neutral maps linearly (FORM_SATURATION_UP=2.0)."""
    form = service.calculate_player_form(_history([6.5] * 3))

    assert form["current"] == pytest.approx(6.3285)
    assert form["form_score"] == pytest.approx(0.16425)


def test_calculate_player_form_score_is_steeper_below_neutral_than_above(
    service: FormScoresService,
) -> None:
    """The same rating gap moves the score more below neutral (UP=2.0, DOWN=0.5)."""
    above = service.calculate_player_form(_history([6.5] * 3))
    below = service.calculate_player_form(_history([5.5] * 3))

    assert above["form_score"] == pytest.approx(0.16425)
    assert below["form_score"] == pytest.approx(-0.657)


def test_calculate_player_form_score_clamps_at_plus_one(
    service: FormScoresService,
) -> None:
    """Exceptional form saturates at +1 while current keeps the raw value."""
    form = service.calculate_player_form(_history([9.0] * 10))

    assert form["form_score"] == 1.0
    assert form["current"] is not None
    assert form["current"] > 8.0


def test_calculate_player_form_score_clamps_at_minus_one(
    service: FormScoresService,
) -> None:
    """Terrible form saturates at -1 while current keeps the raw value."""
    form = service.calculate_player_form(_history([3.0] * 10))

    assert form["form_score"] == -1.0
    assert form["current"] is not None
    assert form["current"] < 4.0


# ── Purity ────────────────────────────────────────────────────────────────────────


def test_calculate_player_form_does_not_mutate_input(
    service: FormScoresService,
) -> None:
    """The input history is left unchanged by the calculation."""
    history = _history([7.0, 7.5, 8.0, 6.5], missed=2)
    snapshot = copy.deepcopy(history)

    service.calculate_player_form(history)

    assert history == snapshot
