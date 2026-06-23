"""Shared pytest fixtures for the Gaffer's Clipboard test suite."""

from pathlib import Path

import pytest

from src.data_manager import DataManager
from src.services.app.buffer_service import BufferService
from src.services.data.player_service import PlayerService

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def buffer_service() -> BufferService:
    """Return a fresh BufferService instance for each test."""
    return BufferService()


@pytest.fixture
def data_player_service() -> PlayerService:
    """Return a fresh data-layer PlayerService instance for each test."""
    return PlayerService()


@pytest.fixture
def fixture_data_path() -> Path:
    """Return the path to the testing_data fixture directory."""
    return _PROJECT_ROOT / "tests" / "fixtures" / "testing_data"


@pytest.fixture
def validation_data_path() -> Path:
    """Return the path to the validation_data fixture directory."""
    return _PROJECT_ROOT / "tests" / "fixtures" / "validation_data"


@pytest.fixture
def screenshots_path() -> Path:
    """Return the path to the fixture screenshots directory."""
    return _PROJECT_ROOT / "tests" / "fixtures" / "screenshots"


@pytest.fixture
def loaded_data_manager(tmp_path: Path) -> DataManager:
    """Return a DataManager with a Valencia CF career created and loaded.

    Uses tmp_path so each test gets a clean, isolated data directory.
    """
    manager = DataManager(project_root=tmp_path)
    manager.create_new_career(
        club_name="Valencia CF",
        manager_name="Ruben Baraja",
        starting_season="24/25",
        half_length=6,
        difficulty="Professional",
        league="La Liga",
    )
    assert manager.load_career("Valencia CF") is True
    return manager


@pytest.fixture
def minimal_team_stats() -> dict[str, int | float]:
    """Return a minimal valid MatchStats payload for use in match-related tests."""
    return {
        "possession": 50,
        "ball_recovery": 45,
        "shots": 10,
        "xg": 1.2,
        "passes": 350,
        "tackles": 20,
        "tackles_won": 12,
        "interceptions": 8,
        "saves": 3,
        "fouls_committed": 7,
        "offsides": 2,
        "corners": 5,
        "free_kicks": 4,
        "penalty_kicks": 0,
        "yellow_cards": 1,
    }
