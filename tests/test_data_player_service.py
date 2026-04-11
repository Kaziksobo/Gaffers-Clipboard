"""Unit tests for the PlayerService data layer.

This module contains unit tests for
``src.services.data.player_service.PlayerService``. The tests cover parsing
and validation of player core fields, building attribute snapshots for
outfield and goalkeeper players, player lookup utilities, and creating or
updating player records.
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from src.schemas import Player
from src.services.data.player_service import PlayerService


def _player(
    *,
    player_id: int = 1,
    name: str = "John Doe",
    nationality: str = "England",
    age: int = 22,
    height: str = "5'8\"",
    weight: int = 145,
    positions: list[str] | None = None,
) -> Player:
    """Create a Player instance with default values, allowing overrides for testing."""
    if positions is None:
        positions = ["CM"]
    return Player(
        id=player_id,
        name=name,
        nationality=nationality,
        age=age,
        height=height,
        weight=weight,
        positions=positions,
        attribute_history=[],
        financial_history=[],
        injury_history=[],
        sold=False,
        date_sold=None,
        loaned=False,
    )


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_error"),
    [
        # Name failures
        ("name", None, "Player name is required as a non-empty string."),
        ("name", "", "Player name is required as a non-empty string."),
        ("name", "   ", "Player name is required as a non-empty string."),
        ("name", 123, "Player name is required as a non-empty string."),
        # Country failures
        ("country", None, "Player country is required as a non-empty string."),
        ("country", False, "Player country is required as a non-empty string."),
        # Height failures
        ("height", "", "Player height is required as a non-empty string."),
        ("height", ["6'0\""], "Player height is required as a non-empty string."),
    ],
)
def test_extract_player_core_fields_invalid_strings_raise_error(
    field: str, invalid_value: str | int | dict | bool | None, expected_error: str
) -> None:
    """Test that invalid string inputs raise the correct ValueError."""
    service = PlayerService()

    # Create a valid base payload
    payload = {
        "name": "John Doe",
        "country": "England",
        "age": 22,
        "height": """5'8\"""",
        "weight": 145,
        field: invalid_value,
    }

    with pytest.raises(ValueError, match=expected_error):
        service.extract_player_core_fields(payload)


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_error"),
    [
        # Age failures
        ("age", None, "Player age is required as an integer."),
        ("age", "twenty", "Player age is required as an integer."),
        ("age", False, "Player age is required as an integer."),  # Boolean trap
        # Weight failures
        ("weight", "   ", "Player weight is required as an integer."),
        ("weight", {"kg": 80}, "Player weight is required as an integer."),
    ],
)
def test_extract_player_core_fields_invalid_ints_raise_error(
    field: str, invalid_value: str | int | dict | bool | None, expected_error: str
) -> None:
    """Test that invalid integer inputs raise the correct ValueError."""
    service = PlayerService()

    payload = {
        "name": "John Doe",
        "country": "England",
        "age": 22,
        "height": "5'8\"",
        "weight": 145,
        field: invalid_value,
    }

    with pytest.raises(ValueError, match=expected_error):
        service.extract_player_core_fields(payload)


@pytest.mark.parametrize(
    "empty_or_invalid_name",
    [
        "",
        "   ",
        "\n\t",
        None,  # Testing runtime edge case, even though type hint is str
    ],
)
def test_find_player_by_name_returns_none_for_empty_input(
    empty_or_invalid_name: str | None,
) -> None:
    """Test that providing an empty, whitespace, or None name returns None."""
    service = PlayerService()
    players = [_player(name="Bukayo Saka")]

    # Should safely return None without throwing exceptions
    result = service.find_player_by_name(players, empty_or_invalid_name)

    assert result is None


def test_find_player_by_name_success_case_insensitive() -> None:
    """Test that the method correctly finds player regardless of case or whitespace."""
    service = PlayerService()
    target_player = _player(player_id=1, name="Bukayo Saka")
    decoy_player = _player(player_id=2, name="Martin Ødegaard")

    players = [decoy_player, target_player]

    # Test exact match
    assert service.find_player_by_name(players, "Bukayo Saka") is target_player

    # Test lowercase match
    assert service.find_player_by_name(players, "bukayo saka") is target_player

    # Test uppercase match
    assert service.find_player_by_name(players, "BUKAYO SAKA") is target_player

    # Test messy whitespace
    assert service.find_player_by_name(players, "  bukayo SAKA  \n") is target_player


def test_find_player_by_name_returns_none_when_not_found() -> None:
    """Test that searching for a name not in the list returns None."""
    service = PlayerService()
    players = [_player(name="Bukayo Saka")]

    result = service.find_player_by_name(players, "Declan Rice")

    assert result is None


def test_build_attribute_snapshot_outfield_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that UI payload is correctly stripped, enriched, and routed to the model."""
    service = PlayerService()
    captured_payload: dict[str, object] = {}

    # 1. Define a strictly-typed stub function
    def stub_model_validate(payload: dict[str, object]) -> str:
        captured_payload.update(payload)
        return "dummy_outfield_snapshot"

    monkeypatch.setattr(
        "src.services.data.player_service.OutfieldAttributeSnapshot.model_validate",
        stub_model_validate,
    )

    raw_ui_payload = {
        "name": "Bukayo Saka",
        "age": 22,
        "height": "5'10\"",
        "country": "England",
        "sprint_speed": 89,
        "finishing": 82,
    }

    result = service.build_attribute_snapshot(
        player_ui_data=raw_ui_payload,
        is_gk=False,
        in_game_date="2024-01-01",
        position="RW",
        player_name="Bukayo Saka",
    )

    assert result == "dummy_outfield_snapshot"

    assert "name" not in captured_payload
    assert "age" not in captured_payload
    assert "height" not in captured_payload
    assert "country" not in captured_payload

    assert captured_payload["sprint_speed"] == 89
    assert captured_payload["finishing"] == 82

    assert captured_payload["in_game_date"] == "2024-01-01"
    assert captured_payload["position_type"] == "Outfield"
    assert captured_payload["position"] == "RW"
    assert isinstance(captured_payload["datetime"], datetime)


def test_build_attribute_snapshot_gk_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Goalkeeper payloads are routed correctly and handle None positions."""
    service = PlayerService()
    captured_payload: dict[str, object] = {}

    def stub_model_validate(payload: dict[str, object]) -> str:
        captured_payload.update(payload)
        return "dummy_gk_snapshot"

    monkeypatch.setattr(
        "src.services.data.player_service.GKAttributeSnapshot.model_validate",
        stub_model_validate,
    )

    result = service.build_attribute_snapshot(
        player_ui_data={"diving": 85, "handling": 80},
        is_gk=True,
        in_game_date="2024-01-01",
        position=None,
        player_name="David Raya",
    )

    assert result == "dummy_gk_snapshot"
    assert captured_payload["position_type"] == "GK"
    assert "position" not in captured_payload
    assert captured_payload["diving"] == 85


def test_build_attribute_snapshot_raises_value_error_on_pydantic_failure() -> None:
    """Test that a Pydantic ValidationError is caught and re-raised as a ValueError."""
    service = PlayerService()

    # Use re.escape to safely match literal strings containing
    # periods or other regex tokens
    expected_error_msg = re.escape("Invalid player attributes for 'Martin Ødegaard'.")

    with pytest.raises(ValueError, match=expected_error_msg):
        service.build_attribute_snapshot(
            player_ui_data={"name": "Martin Ødegaard"},
            is_gk=False,
            in_game_date="2024-01-01",
            position="CM",
            player_name="Martin Ødegaard",
        )


def test_update_existing_player_history_and_bio() -> None:
    """Test that the player's history and bio are updated correctly."""
    service = PlayerService()

    player = _player(
        name="John Doe",
        nationality="England",
        age=20,
        height="5'9\"",
        weight=150,
        positions=["ST"],
    )

    mock_snapshot = "mock_attribute_snapshot_data"

    # Create a mock update
    class MockCoreFields:
        name = "John Doe"
        age = 21
        height = "5'10\""
        weight = 155
        country = "Spain"

    core_fields = MockCoreFields()

    service.update_existing_player(
        existing_player=player,
        attributes_snapshot=mock_snapshot,
        core_fields=core_fields,
        position="CAM",
    )

    assert len(player.attribute_history) == 1
    assert player.attribute_history[0] == mock_snapshot
    assert player.age == 21
    assert player.height == "5'10\""
    assert player.weight == 155
    assert player.nationality == "Spain"
    assert "CAM" in player.positions
    assert "ST" in player.positions


def test_create_new_player_missing_data() -> None:
    """Test that creating a new player with missing fields raises ValueError."""
    service = PlayerService()

    player_id = 1

    class MockCoreFields:
        name = "John Doe"
        age = 22
        height = "5'8\""
        weight = 145
        country = "England"

    core_fields = MockCoreFields()
    # Remove the name to simulate missing required field
    core_fields.height = None

    attributes_snapshot = "mock_attributes_snapshot"

    expected_error_msg = re.escape(
        "New players require name, country, age, height, weight, and position."
    )

    with pytest.raises(
        ValueError,
        match=expected_error_msg,
    ):
        service.create_new_player(
            player_id=player_id,
            core_fields=core_fields,
            attributes_snapshot=attributes_snapshot,
            position="LW",
        )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("name", ""),
        ("name", "   "),
        ("country", ""),
        ("country", "   "),
        ("height", ""),
        ("height", "   "),
        ("position", ""),
        ("position", "   "),
    ],
)
def test_create_new_player_rejects_blank_strings(
    field: str, invalid_value: str
) -> None:
    """Test that blank string inputs are rejected for new players."""
    service = PlayerService()

    player_id = 1

    class MockCoreFields:
        name = "John Doe"
        age = 22
        height = "5'8\""
        weight = 145
        country = "England"

    core_fields = MockCoreFields()

    position = "LW"
    if field == "position":
        position = invalid_value
    else:
        setattr(core_fields, field, invalid_value)

    attributes_snapshot = "mock_attributes_snapshot"

    expected_error_msg = re.escape(
        "New players require name, country, age, height, weight, and position."
    )

    with pytest.raises(
        ValueError,
        match=expected_error_msg,
    ):
        service.create_new_player(
            player_id=player_id,
            core_fields=core_fields,
            attributes_snapshot=attributes_snapshot,
            position=position,
        )


def test_require_existing_player_invalid_player() -> None:
    """Test that requiring an existing player with None raises ValueError."""
    service = PlayerService()

    # create a list of players
    players = [
        _player(player_id=1, name="John Doe"),
        _player(player_id=2, name="Jane Smith"),
    ]

    player_name = "Nonexistent Player"
    action_description = "update"

    expected_error_msg = re.escape(
        f"Player '{player_name}' not found. Cannot {action_description}."
    )

    with pytest.raises(ValueError, match=expected_error_msg):
        service.require_existing_player(
            players=players,
            player_name=player_name,
            action_description=action_description,
        )
