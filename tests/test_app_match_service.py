"""Tests for the app-layer MatchService."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.exceptions import (
    DataDiscrepancyError,
    DataPersistenceError,
    IncompleteDataError,
)
from src.services.app.match_service import MatchService


@pytest.fixture
def mock_dm() -> MagicMock:
    """Return a MagicMock DataManager."""
    return MagicMock()


@pytest.fixture
def match_service(mock_dm: MagicMock) -> MatchService:
    """Return a MatchService wired to a mock DataManager."""
    return MatchService(mock_dm)


def _overview(
    home_stats: dict[str, object] | None = None,
    away_stats: dict[str, object] | None = None,
    home_score: int = 1,
    away_score: int = 0,
) -> dict[str, object]:
    """Return a minimal valid match overview payload."""
    if home_stats is None:
        home_stats = {
            "shots": 10,
            "fouls_committed": 5,
            "offsides": 2,
            "tackles": 8,
            "passes": 300,
            "xg": 1.2,
        }
    if away_stats is None:
        away_stats = {
            "shots": 5,
            "fouls_committed": 3,
            "offsides": 1,
            "tackles": 6,
            "passes": 200,
            "xg": 0.5,
        }
    return {
        "home_team_name": "Valencia CF",
        "away_team_name": "Sevilla",
        "home_score": home_score,
        "away_score": away_score,
        "home_stats": home_stats,
        "away_stats": away_stats,
    }


def _outfield(
    goals: int = 0,
    shots: int = 5,
    fouls_committed: int = 2,
    offsides: int = 1,
    tackles: int = 4,
    passes: int = 50,
) -> dict[str, object]:
    """Return a minimal outfield performance payload for cohesion checks."""
    return {
        "performance_type": "Outfield",
        "goals": goals,
        "shots": shots,
        "fouls_committed": fouls_committed,
        "offsides": offsides,
        "tackles": tackles,
        "passes": passes,
    }


def _active_career_meta(mock_dm: MagicMock) -> None:
    """Configure mock_dm to return a Valencia CF career meta."""
    meta = MagicMock()
    meta.club_name = "Valencia CF"
    mock_dm.get_current_career_metadata.return_value = meta


# ---------------------------------------------------------------------------
# save_match — guard clause
# ---------------------------------------------------------------------------


def test_save_match_raises_when_overview_is_empty(
    match_service: MatchService,
) -> None:
    """save_match raises IncompleteDataError when the overview payload is empty."""
    with pytest.raises(IncompleteDataError, match="Missing match overview data"):
        match_service.save_match({})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# save_match — happy path
# ---------------------------------------------------------------------------


def test_save_match_delegates_to_data_manager_without_performances(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """save_match calls DataManager.add_match with an empty performances list."""
    overview = _overview()

    match_service.save_match(overview)  # type: ignore[arg-type]

    mock_dm.add_match.assert_called_once_with(
        match_data=overview,
        player_performances=[],
    )


def test_save_match_passes_performances_through_with_force_save(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """save_match passes player performances to DataManager when force_save=True."""
    overview = _overview()
    performances = [_outfield()]

    match_service.save_match(  # type: ignore[arg-type]
        overview, player_performances=performances, force_save=True  # type: ignore[arg-type]
    )

    mock_dm.add_match.assert_called_once_with(
        match_data=overview,
        player_performances=performances,
    )


def test_save_match_wraps_data_manager_error_as_persistence_error(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """save_match wraps a DataManager failure in DataPersistenceError."""
    mock_dm.add_match.side_effect = RuntimeError("write failed")

    with pytest.raises(DataPersistenceError, match="Failed to save match data"):
        match_service.save_match(_overview())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# save_match — stat cohesion check
# ---------------------------------------------------------------------------


def test_save_match_raises_discrepancy_when_shots_mismatch(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """save_match raises DataDiscrepancyError when shot counts mismatch."""
    _active_career_meta(mock_dm)
    home_stats: dict[str, object] = {
        "shots": 10,
        "fouls_committed": 2,
        "offsides": 0,
        "tackles": 5,
        "passes": 60,
        "xg": 1.0,
    }
    overview = _overview(home_stats=home_stats)
    performances = [
        _outfield(shots=3, fouls_committed=2, offsides=0, tackles=5, passes=60)
    ]

    with pytest.raises(DataDiscrepancyError):
        match_service.save_match(overview, player_performances=performances)  # type: ignore[arg-type]


def test_save_match_skips_cohesion_check_when_force_save(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """force_save=True bypasses cohesion validation and calls DataManager.add_match."""
    _active_career_meta(mock_dm)
    home_stats: dict[str, object] = {
        "shots": 10,
        "fouls_committed": 2,
        "offsides": 0,
        "tackles": 5,
        "passes": 60,
        "xg": 1.0,
    }
    overview = _overview(home_stats=home_stats)
    performances = [
        _outfield(shots=3, fouls_committed=2, offsides=0, tackles=5, passes=60)
    ]

    match_service.save_match(  # type: ignore[arg-type]
        overview, player_performances=performances, force_save=True  # type: ignore[arg-type]
    )

    mock_dm.add_match.assert_called_once()


def test_save_match_skips_cohesion_when_no_career_metadata(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """save_match proceeds without error when no career metadata is loaded."""
    mock_dm.get_current_career_metadata.return_value = None
    home_stats: dict[str, object] = {
        "shots": 99,
        "fouls_committed": 0,
        "offsides": 0,
        "tackles": 0,
        "passes": 0,
        "xg": 0,
    }
    overview = _overview(home_stats=home_stats)
    performances = [_outfield(shots=1)]

    match_service.save_match(overview, player_performances=performances)  # type: ignore[arg-type]

    mock_dm.add_match.assert_called_once()


def test_save_match_allows_own_goal_score_difference(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """Team score exceeding player goal sum is treated as an own goal, not an error."""
    _active_career_meta(mock_dm)
    home_stats: dict[str, object] = {
        "shots": 2,
        "fouls_committed": 2,
        "offsides": 0,
        "tackles": 5,
        "passes": 60,
        "xg": 1.0,
    }
    # Valencia CF scored 2, player scored 1 → opponent own goal → should not raise
    overview = _overview(home_score=2, away_score=0, home_stats=home_stats)
    performances = [
        _outfield(goals=1, shots=2, fouls_committed=2, offsides=0, tackles=5, passes=60)
    ]

    match_service.save_match(overview, player_performances=performances)  # type: ignore[arg-type]

    mock_dm.add_match.assert_called_once()


def test_save_match_allows_passes_within_tolerance(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """A passes gap of up to 20 (for GK passes) is allowed without a discrepancy."""
    _active_career_meta(mock_dm)
    home_stats: dict[str, object] = {
        "shots": 5,
        "fouls_committed": 2,
        "offsides": 0,
        "tackles": 4,
        "passes": 70,
        "xg": 1.0,
    }
    # 70 team passes vs 60 player passes: gap of 10 (within tolerance)
    overview = _overview(home_stats=home_stats)
    performances = [
        _outfield(shots=5, fouls_committed=2, offsides=0, tackles=4, passes=60)
    ]

    match_service.save_match(overview, player_performances=performances)  # type: ignore[arg-type]

    mock_dm.add_match.assert_called_once()


# ---------------------------------------------------------------------------
# get_latest_match_in_game_date
# ---------------------------------------------------------------------------


def test_get_latest_match_in_game_date_returns_date_from_data_manager(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """get_latest_match_in_game_date returns the datetime from DataManager."""
    expected = datetime(2024, 8, 15)
    mock_dm.get_latest_match_in_game_date.return_value = expected

    result = match_service.get_latest_match_in_game_date()

    assert result == expected


def test_get_latest_match_in_game_date_returns_none_on_error(
    match_service: MatchService,
    mock_dm: MagicMock,
) -> None:
    """get_latest_match_in_game_date returns None when DataManager raises."""
    mock_dm.get_latest_match_in_game_date.side_effect = Exception("no matches")

    result = match_service.get_latest_match_in_game_date()

    assert result is None
