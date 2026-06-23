"""Tests for the app-layer PlayerService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.exceptions import DataPersistenceError, IncompleteDataError
from src.services.app.player_service import PlayerService


@pytest.fixture
def mock_dm() -> MagicMock:
    """Return a MagicMock DataManager."""
    return MagicMock()


@pytest.fixture
def player_service(mock_dm: MagicMock) -> PlayerService:
    """Return a PlayerService wired to a mock DataManager."""
    return PlayerService(mock_dm)


def _mock_player(
    name: str,
    sold: bool = False,
    loaned: bool = False,
    is_gk: bool = False,
) -> MagicMock:
    """Return a mock Player with configurable sold/loaned/GK attributes."""
    p = MagicMock()
    p.name = name
    p.sold = sold
    p.loaned = loaned
    p.is_goalkeeper = is_gk
    return p


# ---------------------------------------------------------------------------
# save_player
# ---------------------------------------------------------------------------


def test_save_player_delegates_to_data_manager(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """save_player calls DataManager.add_or_update_player with the correct args."""
    player_service.save_player("Saka", {"sprint_speed": 90}, "RW", "01/08/24")

    mock_dm.add_or_update_player.assert_called_once_with(
        player_ui_data={"sprint_speed": 90},
        position="RW",
        in_game_date="01/08/24",
        is_gk=False,
    )


def test_save_player_reraises_incomplete_data_error(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """save_player re-raises IncompleteDataError from DataManager unchanged."""
    mock_dm.add_or_update_player.side_effect = IncompleteDataError("Missing name")

    with pytest.raises(IncompleteDataError, match="Missing name"):
        player_service.save_player("Saka", {}, "RW", "01/08/24")


def test_save_player_wraps_unexpected_error_as_persistence_error(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """save_player wraps any unexpected exception in DataPersistenceError."""
    mock_dm.add_or_update_player.side_effect = RuntimeError("disk full")

    with pytest.raises(DataPersistenceError, match="Failed to save player data"):
        player_service.save_player("Saka", {}, "RW", "01/08/24")


# ---------------------------------------------------------------------------
# save_financial_data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("player_name", "financial_data", "in_game_date", "expected_msg"),
    [
        ("", {"wage": 50000}, "01/08/24", "No player selected"),
        ("  ", {"wage": 50000}, "01/08/24", "No player selected"),
        ("Saka", {}, "01/08/24", "Financial data fields are empty"),
        ("Saka", {"wage": 50000}, "", "In-game date is required"),
        ("Saka", {"wage": 50000}, "   ", "In-game date is required"),
    ],
)
def test_save_financial_data_rejects_incomplete_input(
    player_name: str,
    financial_data: dict[str, int],
    in_game_date: str,
    expected_msg: str,
    player_service: PlayerService,
) -> None:
    """save_financial_data raises IncompleteDataError for any missing required field."""
    with pytest.raises(IncompleteDataError, match=expected_msg):
        player_service.save_financial_data(
            player_name, financial_data, in_game_date  # type: ignore[arg-type]
        )


def test_save_financial_data_delegates_on_valid_input(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """save_financial_data delegates to DataManager when all fields are present."""
    payload = {"wage": 50000, "market_value": 5000000}

    player_service.save_financial_data(
        "Saka", payload, "01/08/24"  # type: ignore[arg-type]
    )

    mock_dm.add_financial_data.assert_called_once_with("Saka", payload, "01/08/24")


def test_save_financial_data_wraps_backend_error(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """save_financial_data wraps a DataManager failure in DataPersistenceError."""
    mock_dm.add_financial_data.side_effect = RuntimeError("oops")

    with pytest.raises(DataPersistenceError, match="Backend failed to save financial"):
        player_service.save_financial_data(
            "Saka", {"wage": 1}, "01/08/24"  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# add_injury_record
# ---------------------------------------------------------------------------


def test_add_injury_record_rejects_empty_player_name(
    player_service: PlayerService,
) -> None:
    """add_injury_record raises IncompleteDataError when player name is blank."""
    with pytest.raises(IncompleteDataError, match="No player selected"):
        player_service.add_injury_record("", {"type": "hamstring"})  # type: ignore[arg-type]


def test_add_injury_record_rejects_empty_injury_data(
    player_service: PlayerService,
) -> None:
    """add_injury_record raises IncompleteDataError when injury data is empty."""
    with pytest.raises(IncompleteDataError, match="Injury data fields are empty"):
        player_service.add_injury_record("Saka", {})  # type: ignore[arg-type]


def test_add_injury_record_delegates_on_valid_input(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """add_injury_record delegates to DataManager when inputs are valid."""
    payload = {"type": "hamstring", "date": "01/08/24"}

    player_service.add_injury_record("Saka", payload)  # type: ignore[arg-type]

    mock_dm.add_injury_record.assert_called_once_with("Saka", payload)


def test_add_injury_record_wraps_backend_error(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """add_injury_record wraps a DataManager failure in DataPersistenceError."""
    mock_dm.add_injury_record.side_effect = RuntimeError("db error")

    with pytest.raises(DataPersistenceError, match="Failed to save injury data"):
        player_service.add_injury_record("Saka", {"type": "knee"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# sell_player
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank_name", ["", "   "])
def test_sell_player_rejects_blank_name(
    blank_name: str,
    player_service: PlayerService,
) -> None:
    """sell_player raises IncompleteDataError when player name is blank."""
    with pytest.raises(IncompleteDataError, match="No player selected"):
        player_service.sell_player(blank_name, "01/08/24")


@pytest.mark.parametrize("blank_date", ["", "   "])
def test_sell_player_rejects_blank_date(
    blank_date: str,
    player_service: PlayerService,
) -> None:
    """sell_player raises IncompleteDataError when in-game date is blank."""
    with pytest.raises(IncompleteDataError, match="In-game date is required"):
        player_service.sell_player("Saka", blank_date)


def test_sell_player_delegates_on_valid_input(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """sell_player delegates to DataManager when both fields are present."""
    player_service.sell_player("Saka", "01/08/24")

    mock_dm.sell_player.assert_called_once_with("Saka", "01/08/24")


def test_sell_player_wraps_backend_error(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """sell_player wraps a DataManager failure in DataPersistenceError."""
    mock_dm.sell_player.side_effect = RuntimeError("write failed")

    with pytest.raises(DataPersistenceError, match="Failed to sell player"):
        player_service.sell_player("Saka", "01/08/24")


# ---------------------------------------------------------------------------
# loan_out_player
# ---------------------------------------------------------------------------


def test_loan_out_player_rejects_blank_name(player_service: PlayerService) -> None:
    """loan_out_player raises IncompleteDataError when player name is blank."""
    with pytest.raises(IncompleteDataError, match="No player selected"):
        player_service.loan_out_player("  ")


def test_loan_out_player_delegates(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """loan_out_player delegates to DataManager with the player name."""
    player_service.loan_out_player("Saka")

    mock_dm.loan_out_player.assert_called_once_with("Saka")


def test_loan_out_player_wraps_backend_error(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """loan_out_player wraps a DataManager failure in DataPersistenceError."""
    mock_dm.loan_out_player.side_effect = RuntimeError("network error")

    with pytest.raises(DataPersistenceError, match="Failed to loan out player"):
        player_service.loan_out_player("Saka")


# ---------------------------------------------------------------------------
# return_loan_player
# ---------------------------------------------------------------------------


def test_return_loan_player_rejects_blank_name(player_service: PlayerService) -> None:
    """return_loan_player raises IncompleteDataError when player name is blank."""
    with pytest.raises(IncompleteDataError, match="No player selected"):
        player_service.return_loan_player("")


def test_return_loan_player_delegates(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """return_loan_player delegates to DataManager with the player name."""
    player_service.return_loan_player("Saka")

    mock_dm.return_loan_player.assert_called_once_with("Saka")


def test_return_loan_player_wraps_backend_error(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """return_loan_player wraps a DataManager failure in DataPersistenceError."""
    mock_dm.return_loan_player.side_effect = RuntimeError("network error")

    with pytest.raises(DataPersistenceError, match="Failed to return player from loan"):
        player_service.return_loan_player("Saka")


# ---------------------------------------------------------------------------
# get_all_player_names
# ---------------------------------------------------------------------------


def test_get_all_player_names_returns_empty_when_no_players(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """get_all_player_names returns [] when DataManager has no players."""
    mock_dm.players = []

    result = player_service.get_all_player_names()

    assert result == []


def test_get_all_player_names_excludes_sold_players(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """get_all_player_names omits players where sold is True."""
    mock_dm.players = [
        _mock_player("Active Player"),
        _mock_player("Sold Player", sold=True),
    ]

    result = player_service.get_all_player_names()

    assert "Active Player" in result
    assert "Sold Player" not in result


def test_get_all_player_names_excludes_loaned_when_flagged(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """get_all_player_names omits loaned players when remove_on_loan=True."""
    mock_dm.players = [
        _mock_player("Active Player"),
        _mock_player("Loaned Player", loaned=True),
    ]

    result = player_service.get_all_player_names(remove_on_loan=True)

    assert "Active Player" in result
    assert "Loaned Player" not in result


def test_get_all_player_names_includes_loaned_by_default(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """get_all_player_names includes loaned players when remove_on_loan is False."""
    mock_dm.players = [_mock_player("Loaned Player", loaned=True)]

    result = player_service.get_all_player_names(remove_on_loan=False)

    assert "Loaned Player" in result


def test_get_all_player_names_only_outfield_excludes_gk(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """only_outfield=True returns only non-goalkeeper players."""
    mock_dm.players = [
        _mock_player("Raya", is_gk=True),
        _mock_player("Saka"),
    ]

    result = player_service.get_all_player_names(only_outfield=True)

    assert "Saka" in result
    assert "Raya" not in result


def test_get_all_player_names_only_gk_excludes_outfield(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """only_gk=True returns only goalkeeper players."""
    mock_dm.players = [
        _mock_player("Raya", is_gk=True),
        _mock_player("Saka"),
    ]

    result = player_service.get_all_player_names(only_gk=True)

    assert "Raya" in result
    assert "Saka" not in result


def test_get_all_player_names_conflicting_flags_returns_all(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """Both only_outfield and only_gk True cancels the filter, returning all players."""
    mock_dm.players = [
        _mock_player("Raya", is_gk=True),
        _mock_player("Saka"),
    ]

    result = player_service.get_all_player_names(only_outfield=True, only_gk=True)

    assert "Raya" in result
    assert "Saka" in result


def test_get_all_player_names_sorts_by_surname(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """get_all_player_names returns names sorted alphabetically by surname."""
    mock_dm.players = [
        _mock_player("Bukayo Saka"),
        _mock_player("Martin Odegaard"),
        _mock_player("David Raya"),
    ]

    result = player_service.get_all_player_names()

    assert result == ["Martin Odegaard", "David Raya", "Bukayo Saka"]


# ---------------------------------------------------------------------------
# get_player_bio
# ---------------------------------------------------------------------------


def test_get_player_bio_returns_none_when_not_found(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """get_player_bio returns None when the player is not in DataManager."""
    mock_dm.find_player_by_name.return_value = None

    result = player_service.get_player_bio("Unknown Player")

    assert result is None


def test_get_player_bio_returns_populated_bio_dict(
    player_service: PlayerService,
    mock_dm: MagicMock,
) -> None:
    """get_player_bio returns a dict with age, height, weight, country, positions."""
    mock_player = MagicMock()
    mock_player.age = 22
    mock_player.height = "5'10\""
    mock_player.weight = 145
    mock_player.nationality = "England"
    mock_player.positions = ["RW", "LW"]
    mock_dm.find_player_by_name.return_value = mock_player

    result = player_service.get_player_bio("Bukayo Saka")

    assert result == {
        "age": 22,
        "height": "5'10\"",
        "weight": 145,
        "country": "England",
        "positions": ["RW", "LW"],
    }
