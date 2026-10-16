"""Tests for the data-layer MatchService."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.contracts.analytics import PlayerRatingHistory
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


_BASE_DATE = datetime(2031, 8, 1)


def _day(offset: int) -> datetime:
    """Return the base in-game date shifted by the given number of days."""
    return _BASE_DATE + timedelta(days=offset)


def _mock_performance(player_id: int, rating: float | None) -> MagicMock:
    """Return a mock performance with a player id and match rating."""
    perf = MagicMock()
    perf.player_id = player_id
    perf.match_rating = rating
    return perf


def _mock_rated_match(
    match_id: int, in_game_date: datetime, performances: list[MagicMock]
) -> MagicMock:
    """Return a mock Match with an id, in-game date, and player performances."""
    m = MagicMock()
    m.id = match_id
    m.data.in_game_date = in_game_date
    m.player_performances = performances
    return m


def _by_player_id(
    histories: list[PlayerRatingHistory],
) -> dict[int, PlayerRatingHistory]:
    """Index rating histories by player id."""
    return {history["player_id"]: history for history in histories}


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
    """normalize_player_performances builds an outfield performance model."""
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
    """_build_outfield_performance returns a valid outfield performance model."""
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


# ---------------------------------------------------------------------------
# build_rated_histories
# ---------------------------------------------------------------------------


def test_build_rated_histories_orders_appearances_chronologically(
    service: MatchService,
) -> None:
    """Appearances are chronological even when matches are passed out of order."""
    players = [_mock_player("Saka", 1)]
    matches = [
        _mock_rated_match(3, _day(14), [_mock_performance(1, 7.0)]),
        _mock_rated_match(1, _day(0), [_mock_performance(1, 6.0)]),
        _mock_rated_match(2, _day(7), [_mock_performance(1, 8.0)]),
    ]

    result = service.build_rated_histories(matches, players)

    appearances = result[0]["appearances"]
    assert [a["match_id"] for a in appearances] == [1, 2, 3]
    assert [a["rating"] for a in appearances] == [6.0, 8.0, 7.0]


def test_build_rated_histories_breaks_date_ties_by_match_id(
    service: MatchService,
) -> None:
    """Matches on the same in-game date are ordered by match id."""
    players = [_mock_player("Saka", 1)]
    matches = [
        _mock_rated_match(5, _day(0), [_mock_performance(1, 7.0)]),
        _mock_rated_match(4, _day(0), [_mock_performance(1, 6.0)]),
    ]

    result = service.build_rated_histories(matches, players)

    assert [a["match_id"] for a in result[0]["appearances"]] == [4, 5]


def test_build_rated_histories_appearances_carry_match_data(
    service: MatchService,
) -> None:
    """Each appearance holds the match id, in-game date, and rating."""
    players = [_mock_player("Saka", 1)]
    matches = [_mock_rated_match(9, _day(3), [_mock_performance(1, 7.5)])]

    result = service.build_rated_histories(matches, players)

    assert result[0]["appearances"] == [
        {"match_id": 9, "in_game_date": _day(3), "rating": 7.5}
    ]


def test_build_rated_histories_excludes_unrated_performances(
    service: MatchService,
) -> None:
    """Performances without a match rating never become appearances."""
    players = [_mock_player("Saka", 1)]
    matches = [
        _mock_rated_match(1, _day(0), [_mock_performance(1, None)]),
        _mock_rated_match(2, _day(7), [_mock_performance(1, 7.0)]),
    ]

    result = service.build_rated_histories(matches, players)

    assert [a["match_id"] for a in result[0]["appearances"]] == [2]


def test_build_rated_histories_unrated_performance_does_not_reset_absence(
    service: MatchService,
) -> None:
    """An unrated cameo leaves the absence count running."""
    players = [_mock_player("Saka", 1), _mock_player("Raya", 2)]
    matches = [
        _mock_rated_match(
            1, _day(0), [_mock_performance(1, 7.0), _mock_performance(2, 6.5)]
        ),
        _mock_rated_match(
            2, _day(7), [_mock_performance(1, None), _mock_performance(2, 6.5)]
        ),
    ]

    result = _by_player_id(service.build_rated_histories(matches, players))

    assert len(result[1]["appearances"]) == 1
    assert result[1]["matches_since_last_rated"] == 1


def test_build_rated_histories_ignores_matches_without_performances(
    service: MatchService,
) -> None:
    """Matches saved without player stats do not count as missed matches."""
    players = [_mock_player("Saka", 1)]
    matches = [
        _mock_rated_match(1, _day(0), [_mock_performance(1, 7.0)]),
        _mock_rated_match(2, _day(7), []),
    ]

    result = service.build_rated_histories(matches, players)

    assert result[0]["matches_since_last_rated"] == 0


def test_build_rated_histories_rated_in_latest_match_has_zero_missed(
    service: MatchService,
) -> None:
    """A player rated in the most recent tracked match has zero missed matches."""
    players = [_mock_player("Saka", 1)]
    matches = [
        _mock_rated_match(1, _day(0), [_mock_performance(1, 6.0)]),
        _mock_rated_match(2, _day(7), [_mock_performance(1, 7.0)]),
    ]

    result = service.build_rated_histories(matches, players)

    assert result[0]["matches_since_last_rated"] == 0


def test_build_rated_histories_counts_missed_tracked_matches(
    service: MatchService,
) -> None:
    """Each tracked match since a player's last rated one adds one to the count."""
    players = [_mock_player("Saka", 1), _mock_player("Raya", 2)]
    matches = [
        _mock_rated_match(
            1, _day(0), [_mock_performance(1, 7.0), _mock_performance(2, 6.0)]
        ),
        _mock_rated_match(2, _day(7), [_mock_performance(2, 6.0)]),
        _mock_rated_match(3, _day(14), [_mock_performance(2, 6.0)]),
    ]

    result = _by_player_id(service.build_rated_histories(matches, players))

    assert result[1]["matches_since_last_rated"] == 2
    assert result[2]["matches_since_last_rated"] == 0


def test_build_rated_histories_never_rated_player_has_empty_history(
    service: MatchService,
) -> None:
    """A never-rated player gets no appearances and misses every tracked match."""
    players = [_mock_player("Saka", 1), _mock_player("Raya", 2)]
    matches = [
        _mock_rated_match(i, _day(7 * i), [_mock_performance(1, 7.0)])
        for i in range(1, 4)
    ]

    result = _by_player_id(service.build_rated_histories(matches, players))

    assert result[2]["appearances"] == []
    assert result[2]["matches_since_last_rated"] == 3


def test_build_rated_histories_filters_by_player_ids(
    service: MatchService,
) -> None:
    """Only the requested player ids are returned."""
    players = [_mock_player("Saka", 1), _mock_player("Raya", 2)]
    matches = [
        _mock_rated_match(
            1, _day(0), [_mock_performance(1, 7.0), _mock_performance(2, 6.0)]
        )
    ]

    result = service.build_rated_histories(matches, players, player_ids={2})

    assert [h["player_id"] for h in result] == [2]


def test_build_rated_histories_ignores_performances_for_unknown_players(
    service: MatchService,
) -> None:
    """Performances whose player id is not in the player list produce no history."""
    players = [_mock_player("Saka", 1)]
    matches = [
        _mock_rated_match(
            1, _day(0), [_mock_performance(1, 7.0), _mock_performance(99, 6.0)]
        )
    ]

    result = service.build_rated_histories(matches, players)

    assert [h["player_id"] for h in result] == [1]


def test_build_rated_histories_with_no_matches_returns_empty_histories(
    service: MatchService,
) -> None:
    """With no matches every player has an empty history and nothing missed."""
    players = [_mock_player("Saka", 1), _mock_player("Raya", 2)]

    result = service.build_rated_histories([], players)

    assert [h["appearances"] for h in result] == [[], []]
    assert [h["matches_since_last_rated"] for h in result] == [0, 0]


def test_build_rated_histories_preserves_player_order_and_names(
    service: MatchService,
) -> None:
    """Histories follow the order of the players list and carry id and name."""
    players = [_mock_player("Raya", 2), _mock_player("Saka", 1)]

    result = service.build_rated_histories([], players)

    assert [(h["player_id"], h["player_name"]) for h in result] == [
        (2, "Raya"),
        (1, "Saka"),
    ]


def test_build_rated_histories_does_not_reorder_input_matches(
    service: MatchService,
) -> None:
    """The caller's match list keeps its original order."""
    players = [_mock_player("Saka", 1)]
    matches = [
        _mock_rated_match(2, _day(7), [_mock_performance(1, 7.0)]),
        _mock_rated_match(1, _day(0), [_mock_performance(1, 6.0)]),
    ]

    service.build_rated_histories(matches, players)

    assert [m.id for m in matches] == [2, 1]
