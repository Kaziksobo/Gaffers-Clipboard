"""Tests for buffering behavior in the application service layer."""

import pytest

from src.exceptions import DuplicateRecordError, IncompleteDataError
from src.services.app.buffer_service import BufferService


def test_buffer_match_overview_merges_without_overwriting_non_none() -> None:
    """Later None values must not erase existing match overview values."""
    service = BufferService()

    service.buffer_match_overview(
        {
            "in_game_date": "01/08/24",
            "competition": "La Liga",
        }
    )
    service.buffer_match_overview(
        {
            "competition": None,
            "home_team_name": "Valencia CF",
        }
    )

    buffered = service.get_buffered_match()
    assert buffered.match_overview["competition"] == "La Liga"
    assert buffered.match_overview["home_team_name"] == "Valencia CF"


def test_buffer_player_performance_rejects_duplicate_name_case_insensitive() -> None:
    """The same player cannot be buffered twice, regardless of name casing/spacing."""
    service = BufferService()

    service.buffer_player_performance({"player_name": "V. Jr", "goals": 1})

    with pytest.raises(DuplicateRecordError):
        service.buffer_player_performance({"player_name": "  v. jr  ", "goals": 2})


def test_get_buffered_player_from_goalkeeper_payload() -> None:
    """Goalkeeper payloads should extract into a normalized BufferedPlayer object."""
    service = BufferService()

    service.buffer_player_attributes(
        {
            "name": "Giorgi Mamardashvili",
            "in_game_date": "01/08/24",
            "diving": 80,
            "handling": 79,
            "kicking": 78,
            "reflexes": 82,
            "positioning": 77,
        },
        is_goalkeeper=True,
        is_first_page=True,
    )

    buffered = service.get_buffered_player()
    assert buffered.player_name == "Giorgi Mamardashvili"
    assert buffered.position == "GK"
    assert buffered.in_game_date == "01/08/24"
    assert buffered.is_goalkeeper is True
    assert buffered.attributes["diving"] == 80


def test_get_buffered_player_requires_both_outfield_pages() -> None:
    """Outfield saves must fail if only one page of attributes is staged."""
    service = BufferService()

    service.buffer_player_attributes(
        {
            "name": "Jude Bellingham",
            "in_game_date": "01/08/24",
            "position": "CM",
            "acceleration": 85,
        },
        is_goalkeeper=False,
        is_first_page=True,
    )

    with pytest.raises(IncompleteDataError):
        service.get_buffered_player()


def test_remove_player_from_buffer_uses_normalized_name_matching() -> None:
    """Removing a buffered player should be robust to case/whitespace differences."""
    service = BufferService()
    service.buffer_player_performance(
        {
            "player_name": " Jude Bellingham ",
            "positions_played": ["CM"],
        }
    )
    service.buffer_player_performance(
        {
            "player_name": "Vinicius Jr",
            "positions_played": ["LW"],
        }
    )

    service.remove_player_from_buffer("jude bellingham")
    rows = service.get_buffered_player_performances(display_keys=["player_name"])

    assert len(rows) == 1
    assert rows[0]["player_name"] == "Vinicius Jr"
