"""Tests for the app-layer CareerService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.app.career_service import CareerService


@pytest.fixture
def mock_dm() -> MagicMock:
    """Return a MagicMock DataManager."""
    return MagicMock()


@pytest.fixture
def career_service(mock_dm: MagicMock) -> CareerService:
    """Return a CareerService wired to a mock DataManager."""
    return CareerService(mock_dm)


# ---------------------------------------------------------------------------
# get_all_career_names
# ---------------------------------------------------------------------------


def test_get_all_career_names_delegates_to_data_manager(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """get_all_career_names returns the list provided by DataManager."""
    mock_dm.get_all_career_names.return_value = ["Valencia CF 1", "Arsenal 1"]

    result = career_service.get_all_career_names()

    assert result == ["Valencia CF 1", "Arsenal 1"]
    mock_dm.get_all_career_names.assert_called_once()


# ---------------------------------------------------------------------------
# activate_career
# ---------------------------------------------------------------------------


def test_activate_career_succeeds_when_load_returns_true(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """activate_career completes without error when load_career returns True."""
    mock_dm.load_career.return_value = True

    career_service.activate_career("Valencia CF")

    mock_dm.load_career.assert_called_once_with("Valencia CF")


def test_activate_career_raises_when_load_returns_false(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """activate_career raises ValueError when DataManager cannot load the career."""
    mock_dm.load_career.return_value = False

    with pytest.raises(ValueError, match="Valencia CF"):
        career_service.activate_career("Valencia CF")


# ---------------------------------------------------------------------------
# save_new_career
# ---------------------------------------------------------------------------


def test_save_new_career_delegates_all_args_to_data_manager(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """save_new_career forwards all arguments to DataManager.create_new_career."""
    career_service.save_new_career(
        club_name="Valencia CF",
        manager_name="Ruben Baraja",
        starting_season="24/25",
        half_length=6,
        match_difficulty="Professional",
        league="La Liga",
    )

    mock_dm.create_new_career.assert_called_once_with(
        "Valencia CF", "Ruben Baraja", "24/25", 6, "Professional", "La Liga"
    )


# ---------------------------------------------------------------------------
# get_current_career_details
# ---------------------------------------------------------------------------


def test_get_current_career_details_returns_metadata(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """get_current_career_details returns the active metadata object."""
    mock_meta = MagicMock()
    mock_dm.get_current_career_metadata.return_value = mock_meta

    result = career_service.get_current_career_details()

    assert result is mock_meta


def test_get_current_career_details_returns_none_when_no_career(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """get_current_career_details returns None when no career is active."""
    mock_dm.get_current_career_metadata.return_value = None

    result = career_service.get_current_career_details()

    assert result is None


# ---------------------------------------------------------------------------
# add_competition — guard and delegation
# ---------------------------------------------------------------------------


def test_add_competition_raises_without_active_career(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """add_competition raises RuntimeError when no career is loaded."""
    mock_dm.current_career = None

    with pytest.raises(RuntimeError, match="No career loaded"):
        career_service.add_competition("UEFA Champions League")


def test_add_competition_delegates_when_career_active(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """add_competition delegates to DataManager when a career is active."""
    mock_dm.current_career = MagicMock()

    career_service.add_competition("UEFA Champions League")

    mock_dm.add_competition.assert_called_once_with("UEFA Champions League")


# ---------------------------------------------------------------------------
# remove_competition — guard and delegation
# ---------------------------------------------------------------------------


def test_remove_competition_raises_without_active_career(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """remove_competition raises RuntimeError when no career is loaded."""
    mock_dm.current_career = None

    with pytest.raises(RuntimeError, match="No career loaded"):
        career_service.remove_competition("La Liga")


def test_remove_competition_delegates_when_career_active(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """remove_competition delegates to DataManager when a career is active."""
    mock_dm.current_career = MagicMock()

    career_service.remove_competition("La Liga")

    mock_dm.remove_competition.assert_called_once_with("La Liga")


# ---------------------------------------------------------------------------
# update_career_metadata — guard and delegation
# ---------------------------------------------------------------------------


def test_update_career_metadata_raises_without_active_career(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """update_career_metadata raises RuntimeError when no career is loaded."""
    mock_dm.current_career = None

    with pytest.raises(RuntimeError, match="No career loaded"):
        career_service.update_career_metadata({"half_length": 8})  # type: ignore[typeddict-item]


def test_update_career_metadata_delegates_when_career_active(
    career_service: CareerService,
    mock_dm: MagicMock,
) -> None:
    """update_career_metadata delegates to DataManager when a career is active."""
    mock_dm.current_career = MagicMock()
    update = {"half_length": 8}

    career_service.update_career_metadata(update)  # type: ignore[typeddict-item]

    mock_dm.update_career_metadata.assert_called_once_with(update)
