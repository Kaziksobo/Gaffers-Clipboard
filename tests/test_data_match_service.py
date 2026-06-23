"""Tests for the data-layer MatchService."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.services.data.match_service import MatchService


@pytest.fixture
def service() -> MatchService:
    """Return a fresh data-layer MatchService."""
    return MatchService()


def _mock_player(name: str, player_id: int = 1) -> MagicMock:
    """Return a mock Player with configurable name and id."""
    p = MagicMock()
    p.name = name
    p.id = player_id
    return p


def _mock_match(in_game_date: datetime) -> MagicMock:
    """Return a mock Match with the given in-game date."""
    m = MagicMock()
    m.data.in_game_date = in_game_date
    return m


def _mock_match_with_teams(home: str, away: str) -> MagicMock:
    """Return a mock Match with home and away team names."""
    m = MagicMock()
    m.data.home_team_name = home
    m.data.away_team_name = away
    return m


def _gk_payload(player_name: str = "David Raya") -> dict[str, object]:
    """Return a minimal valid goalkeeper performance payload."""
    return {
        "player_name": player_name,
        "performance_type": "GK",
        "shots_against": 5,
        "shots_on_target": 3,
        "saves": 3,
        "goals_conceded": 0,
        "save_success_rate": 100,
        "punch_saves": 1,
        "rush_saves": 0,
        "penalty_saves": 0,
        "penalty_goals_conceded": 0,
        "shoot_out_saves": 0,
        "shoot_out_goals_conceded": 0,
    }


def _outfield_payload(player_name: str = "Bukayo Saka") -> dict[str, object]:
    """Return a minimal valid outfield performance payload."""
    return {
        "player_name": player_name,
        "performance_type": "Outfield",
        "positions_played": ["RW"],
        "goals": 1,
        "assists": 0,
        "shots": 3,
        "shot_accuracy": 66,
        "passes": 40,
        "pass_accuracy": 85,
        "dribbles": 5,
        "dribble_success_rate": 80,
        "tackles": 2,
        "tackle_success_rate": 50,
        "offsides": 0,
        "fouls_committed": 1,
        "possession_won": 4,
        "possession_lost": 3,
        "minutes_played": 90,
        "distance_covered": 10.5,
        "distance_sprinted": 2.3,
    }


# ---------------------------------------------------------------------------
# find_player_id_by_name
# ---------------------------------------------------------------------------


def test_find_player_id_by_name_returns_none_for_empty_name(
    service: MatchService,
) -> None:
    """find_player_id_by_name returns None when the name string is empty."""
    players = [_mock_player("Saka", 42)]

    result = service.find_player_id_by_name(players, "")

    assert result is None


def test_find_player_id_by_name_returns_id_on_exact_case_insensitive_match(
    service: MatchService,
) -> None:
    """find_player_id_by_name matches names case-insensitively."""
    players = [_mock_player("Bukayo Saka", 7), _mock_player("David Raya", 1)]

    result = service.find_player_id_by_name(players, "bukayo saka")

    assert result == 7


def test_find_player_id_by_name_returns_none_when_no_match(
    service: MatchService,
) -> None:
    """find_player_id_by_name returns None when no player name matches."""
    players = [_mock_player("Saka", 7)]

    result = service.find_player_id_by_name(players, "Bellingham")

    assert result is None


def test_find_player_id_by_name_strips_whitespace(
    service: MatchService,
) -> None:
    """find_player_id_by_name strips surrounding whitespace before comparing."""
    players = [_mock_player("Saka", 7)]

    result = service.find_player_id_by_name(players, "  Saka  ")

    assert result == 7


# ---------------------------------------------------------------------------
# normalize_player_performances
# ---------------------------------------------------------------------------


def test_normalize_player_performances_returns_empty_for_empty_buffer(
    service: MatchService,
) -> None:
    """normalize_player_performances returns an empty list when buffer is empty."""
    result = service.normalize_player_performances(
        player_performances=[],
        players=[],
        match_id=1,
    )

    assert result == []


def test_normalize_player_performances_skips_unknown_player(
    service: MatchService,
) -> None:
    """normalize_player_performances skips performances for unrecognised players."""
    players = [_mock_player("Saka", 7)]
    performances = [_outfield_payload("Unknown Player")]

    result = service.normalize_player_performances(
        player_performances=performances,  # type: ignore[arg-type]
        players=players,  # type: ignore[arg-type]
        match_id=1,
    )

    assert result == []


def test_normalize_player_performances_builds_outfield_model(
    service: MatchService,
) -> None:
    """normalize_player_performances builds an OutfieldPlayerPerformance for Outfield type."""
    from src.schemas import OutfieldPlayerPerformance

    players = [_mock_player("Bukayo Saka", 7)]
    performances = [_outfield_payload("Bukayo Saka")]

    result = service.normalize_player_performances(
        player_performances=performances,  # type: ignore[arg-type]
        players=players,  # type: ignore[arg-type]
        match_id=1,
    )

    assert len(result) == 1
    assert isinstance(result[0], OutfieldPlayerPerformance)
    assert result[0].player_id == 7
    assert result[0].goals == 1


def test_normalize_player_performances_builds_gk_model(
    service: MatchService,
) -> None:
    """normalize_player_performances builds a GoalkeeperPerformance for GK type."""
    from src.schemas import GoalkeeperPerformance

    players = [_mock_player("David Raya", 1)]
    performances = [_gk_payload("David Raya")]

    result = service.normalize_player_performances(
        player_performances=performances,  # type: ignore[arg-type]
        players=players,  # type: ignore[arg-type]
        match_id=1,
    )

    assert len(result) == 1
    assert isinstance(result[0], GoalkeeperPerformance)
    assert result[0].player_id == 1
    assert result[0].saves == 3


def test_normalize_player_performances_handles_mixed_buffer(
    service: MatchService,
) -> None:
    """normalize_player_performances processes GK and outfield entries in one pass."""
    from src.schemas import GoalkeeperPerformance, OutfieldPlayerPerformance

    players = [_mock_player("David Raya", 1), _mock_player("Bukayo Saka", 7)]
    performances = [_gk_payload("David Raya"), _outfield_payload("Bukayo Saka")]

    result = service.normalize_player_performances(
        player_performances=performances,  # type: ignore[arg-type]
        players=players,  # type: ignore[arg-type]
        match_id=1,
    )

    assert len(result) == 2
    assert isinstance(result[0], GoalkeeperPerformance)
    assert isinstance(result[1], OutfieldPlayerPerformance)


# ---------------------------------------------------------------------------
# _build_goalkeeper_performance / _build_outfield_performance (static)
# ---------------------------------------------------------------------------


def test_build_goalkeeper_performance_sets_all_fields() -> None:
    """_build_goalkeeper_performance constructs a valid GoalkeeperPerformance model."""
    from src.schemas import GoalkeeperPerformance

    payload = _gk_payload()
    result = MatchService._build_goalkeeper_performance(payload, player_id=99)  # type: ignore[arg-type]

    assert isinstance(result, GoalkeeperPerformance)
    assert result.player_id == 99
    assert result.saves == 3
    assert result.shots_against == 5


def test_build_outfield_performance_sets_all_fields() -> None:
    """_build_outfield_performance constructs a valid OutfieldPlayerPerformance model."""
    from src.schemas import OutfieldPlayerPerformance

    payload = _outfield_payload()
    result = MatchService._build_outfield_performance(payload, player_id=42)  # type: ignore[arg-type]

    assert isinstance(result, OutfieldPlayerPerformance)
    assert result.player_id == 42
    assert result.goals == 1
    assert result.positions_played == ["RW"]


# ---------------------------------------------------------------------------
# get_latest_in_game_date
# ---------------------------------------------------------------------------


def test_get_latest_in_game_date_returns_none_for_empty_list(
    service: MatchService,
) -> None:
    """get_latest_in_game_date returns None when the match list is empty."""
    result = service.get_latest_in_game_date([])

    assert result is None


def test_get_latest_in_game_date_returns_date_from_single_match(
    service: MatchService,
) -> None:
    """get_latest_in_game_date returns the date when there is only one match."""
    date = datetime(2024, 9, 15)
    matches = [_mock_match(date)]

    result = service.get_latest_in_game_date(matches)  # type: ignore[arg-type]

    assert result == date


def test_get_latest_in_game_date_returns_latest_from_multiple_matches(
    service: MatchService,
) -> None:
    """get_latest_in_game_date returns the most recent in-game date."""
    matches = [
        _mock_match(datetime(2024, 8, 1)),
        _mock_match(datetime(2024, 10, 30)),
        _mock_match(datetime(2024, 9, 15)),
    ]

    result = service.get_latest_in_game_date(matches)  # type: ignore[arg-type]

    assert result == datetime(2024, 10, 30)


# ---------------------------------------------------------------------------
# normalize_team_names
# ---------------------------------------------------------------------------


def test_normalize_team_names_uses_existing_match_names_as_references(
    service: MatchService,
) -> None:
    """normalize_team_names resolves names against teams seen in existing matches."""
    existing = [_mock_match_with_teams("Valencia CF", "Real Madrid")]

    result = service.normalize_team_names(
        ["valencia cf", "real madrid"],
        full_matches_list=existing,  # type: ignore[arg-type]
    )

    assert result == ["Valencia CF", "Real Madrid"]


def test_normalize_team_names_includes_career_team_name_in_reference_set(
    service: MatchService,
) -> None:
    """normalize_team_names adds career_team_name to the reference pool."""
    result = service.normalize_team_names(
        ["Valencia CF"],
        full_matches_list=[],
        career_team_name="Valencia CF",
    )

    assert result == ["Valencia CF"]


def test_normalize_team_names_returns_original_when_no_reference_match(
    service: MatchService,
) -> None:
    """normalize_team_names returns the raw name when no reference matches."""
    result = service.normalize_team_names(
        ["Atletico Madrid"],
        full_matches_list=[],
    )

    assert result == ["Atletico Madrid"]
