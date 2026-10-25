"""Tests for ReliableRatingService shrinkage, season drift, and uncertainty."""

from __future__ import annotations

import datetime as dt

import pytest

from src.contracts.analytics import PlayerRatingHistory, RatedAppearance
from src.services.analytics.reliable_rating_service import ReliableRatingService

_BASE_DATE = dt.datetime(2031, 8, 1)  # start of the 2031 season


def _appearance(index: int, rating: float, date: dt.datetime) -> RatedAppearance:
    """Return a rated appearance with a match id that increases with index."""
    return RatedAppearance(match_id=100 + index, in_game_date=date, rating=rating)


def _history(ratings: list[float]) -> PlayerRatingHistory:
    """Return a single-season history, one appearance a week from the base date."""
    return _dated_history(
        [(_BASE_DATE + dt.timedelta(days=7 * i), r) for i, r in enumerate(ratings)]
    )


def _dated_history(entries: list[tuple[dt.datetime, float]]) -> PlayerRatingHistory:
    """Return a history from chronological (date, rating) pairs."""
    return PlayerRatingHistory(
        player_id=7,
        player_name="Test Player",
        appearances=[_appearance(i + 1, r, d) for i, (d, r) in enumerate(entries)],
        matches_since_last_rated=0,
    )


@pytest.fixture(autouse=True)
def pinned_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the tunable constants so hand calculations survive refitting.

    The service constants are refitted offline, so tests that assert exact
    numbers must not depend on their live values. Drift defaults to zero; tests
    that exercise drift patch it themselves.
    """
    monkeypatch.setattr(ReliableRatingService, "PRIOR_MEAN", 6.0)
    monkeypatch.setattr(ReliableRatingService, "PRIOR_VARIANCE", 0.25)
    monkeypatch.setattr(ReliableRatingService, "OBSERVATION_VARIANCE", 0.58)
    monkeypatch.setattr(ReliableRatingService, "SEASON_DRIFT_VARIANCE", 0.0)


@pytest.fixture
def service() -> ReliableRatingService:
    """Return a ReliableRatingService instance."""
    return ReliableRatingService()


# ── Empty and identity ────────────────────────────────────────────────────────────


def test_calculate_player_rating_no_appearances_returns_none(
    service: ReliableRatingService,
) -> None:
    """A player with no rated appearances has no rating, not the prior."""
    assert service.calculate_player_rating(_history([])) is None


def test_calculate_player_rating_echoes_identity_and_count(
    service: ReliableRatingService,
) -> None:
    """Player id is copied through and n is the number of rated appearances."""
    rating = service.calculate_player_rating(_history([6.5, 7.0, 7.5]))

    assert rating is not None
    assert rating["player_id"] == 7
    assert rating["n"] == 3


# ── Shrinkage (no drift) ──────────────────────────────────────────────────────────


def test_calculate_player_rating_single_appearance_is_heavily_shrunk(
    service: ReliableRatingService,
) -> None:
    """One rating of 8.0 moves the estimate only part of the way from 6.0."""
    rating = service.calculate_player_rating(_history([8.0]))

    # (8 + 2.32 * 6) / 3.32, where k = 0.58 / 0.25 = 2.32
    assert rating is not None
    assert rating["rating"] == pytest.approx(6.60241, abs=1e-5)
    assert rating["std_error"] == pytest.approx(0.41797, abs=1e-5)


def test_calculate_player_rating_two_appearances_match_hand_calculation(
    service: ReliableRatingService,
) -> None:
    """Two ratings of 8.0 give the closed-form shrunk mean and posterior SD."""
    rating = service.calculate_player_rating(_history([8.0, 8.0]))

    # (16 + 2.32 * 6) / 4.32, and variance 1 / (1/0.25 + 2/0.58)
    assert rating is not None
    assert rating["rating"] == pytest.approx(6.92593, abs=1e-5)
    assert rating["std_error"] == pytest.approx(0.36641, abs=1e-5)


@pytest.mark.parametrize(
    "ratings",
    [
        [7.0, 5.0, 8.0],
        [4.0, 4.5, 5.0, 4.2],
        [6.0, 6.0, 6.0],
        [9.0],
        [7.2, 6.8, 7.5, 8.1, 6.4, 7.0, 7.7],
    ],
)
def test_calculate_player_rating_without_drift_matches_closed_form(
    service: ReliableRatingService, ratings: list[float]
) -> None:
    """With no drift the filter equals (sum + k * prior) / (n + k)."""
    k = (
        ReliableRatingService.OBSERVATION_VARIANCE
        / ReliableRatingService.PRIOR_VARIANCE
    )
    n = len(ratings)
    expected_rating = (sum(ratings) + k * ReliableRatingService.PRIOR_MEAN) / (n + k)
    expected_variance = 1 / (
        1 / ReliableRatingService.PRIOR_VARIANCE
        + n / ReliableRatingService.OBSERVATION_VARIANCE
    )

    rating = service.calculate_player_rating(_history(ratings))

    assert rating is not None
    assert rating["rating"] == pytest.approx(expected_rating)
    assert rating["std_error"] == pytest.approx(expected_variance**0.5)


def test_calculate_player_rating_sits_between_prior_and_raw_mean(
    service: ReliableRatingService,
) -> None:
    """The estimate is pulled toward 6.0 from either side, never past it."""
    high = service.calculate_player_rating(_history([8.0, 7.5, 8.5]))
    low = service.calculate_player_rating(_history([4.0, 4.5, 3.5]))

    assert high is not None
    assert low is not None
    assert ReliableRatingService.PRIOR_MEAN < high["rating"] < 8.0
    assert 4.0 < low["rating"] < ReliableRatingService.PRIOR_MEAN


def test_calculate_player_rating_more_evidence_means_more_certainty(
    service: ReliableRatingService,
) -> None:
    """Uncertainty falls and the estimate nears the evidence as ratings accrue."""
    results = [
        service.calculate_player_rating(_history([7.5] * count)) for count in (1, 5, 50)
    ]

    assert all(result is not None for result in results)
    errors = [result["std_error"] for result in results if result is not None]
    estimates = [result["rating"] for result in results if result is not None]
    assert errors == sorted(errors, reverse=True)
    assert estimates == sorted(estimates)
    assert estimates[-1] == pytest.approx(7.5, abs=0.1)


# ── Season drift ──────────────────────────────────────────────────────────────────


def test_calculate_player_rating_no_drift_within_a_season(
    service: ReliableRatingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Appearances in one season ignore drift, even a large one."""
    entries = [(dt.datetime(2030, 8, 1), 8.0), (dt.datetime(2031, 5, 1), 8.0)]
    baseline = service.calculate_player_rating(_dated_history(entries))

    monkeypatch.setattr(ReliableRatingService, "SEASON_DRIFT_VARIANCE", 0.5)
    drifted = service.calculate_player_rating(_dated_history(entries))

    assert baseline is not None
    assert drifted is not None
    assert drifted["rating"] == pytest.approx(baseline["rating"])
    assert drifted["std_error"] == pytest.approx(baseline["std_error"])


def test_calculate_player_rating_drift_across_seasons_matches_hand_calculation(
    service: ReliableRatingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A two-season gap inflates variance by 2q before the second update."""
    monkeypatch.setattr(ReliableRatingService, "SEASON_DRIFT_VARIANCE", 0.1)
    entries = [(dt.datetime(2029, 8, 1), 8.0), (dt.datetime(2031, 8, 1), 8.0)]

    rating = service.calculate_player_rating(_dated_history(entries))

    assert rating is not None
    assert rating["rating"] == pytest.approx(7.15093, abs=1e-5)
    assert rating["std_error"] == pytest.approx(0.47711, abs=1e-5)


def test_calculate_player_rating_drift_reacts_faster_than_plain_shrinkage(
    service: ReliableRatingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With drift on, an improved player's new rating counts for more."""
    entries = [
        (dt.datetime(2029, 8, 1), 6.0),
        (dt.datetime(2029, 9, 1), 6.0),
        (dt.datetime(2031, 8, 1), 8.0),
    ]
    plain = service.calculate_player_rating(_dated_history(entries))

    monkeypatch.setattr(ReliableRatingService, "SEASON_DRIFT_VARIANCE", 0.1)
    drifting = service.calculate_player_rating(_dated_history(entries))

    assert plain is not None
    assert drifting is not None
    assert drifting["rating"] > plain["rating"]


def test_calculate_player_rating_larger_season_gap_means_less_certainty(
    service: ReliableRatingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drift scales with the gap in seasons, not the count of boundaries crossed."""
    monkeypatch.setattr(ReliableRatingService, "SEASON_DRIFT_VARIANCE", 0.1)
    one_season = [(dt.datetime(2029, 8, 1), 8.0), (dt.datetime(2030, 8, 1), 8.0)]
    two_seasons = [(dt.datetime(2029, 8, 1), 8.0), (dt.datetime(2031, 8, 1), 8.0)]

    short_gap = service.calculate_player_rating(_dated_history(one_season))
    long_gap = service.calculate_player_rating(_dated_history(two_seasons))

    assert short_gap is not None
    assert long_gap is not None
    assert short_gap["rating"] == pytest.approx(7.05159, abs=1e-5)
    assert short_gap["std_error"] == pytest.approx(0.43175, abs=1e-5)
    assert long_gap["std_error"] > short_gap["std_error"]


def test_calculate_player_rating_season_boundary_is_one_july(
    service: ReliableRatingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """30 June and 1 July of the same year fall in different seasons."""
    monkeypatch.setattr(ReliableRatingService, "SEASON_DRIFT_VARIANCE", 0.1)
    entries = [(dt.datetime(2031, 6, 30), 8.0), (dt.datetime(2031, 7, 1), 8.0)]

    rating = service.calculate_player_rating(_dated_history(entries))

    # Same result as a one-season gap
    assert rating is not None
    assert rating["rating"] == pytest.approx(7.05159, abs=1e-5)
    assert rating["std_error"] == pytest.approx(0.43175, abs=1e-5)
