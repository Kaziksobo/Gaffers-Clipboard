"""Tests for buffering behavior in the application service layer."""

from __future__ import annotations

import pytest

from src.exceptions import (
    DataPersistenceError,
    DuplicateRecordError,
    IncompleteDataError,
    PlayerNotFoundInBufferError,
)
from src.services.app.buffer_service import BufferService


def test_buffer_match_overview_merges_without_overwriting_non_none(
    buffer_service: BufferService,
) -> None:
    """Later None values must not erase existing match overview values."""
    buffer_service.buffer_match_overview(
        {
            "in_game_date": "01/08/24",
            "competition": "La Liga",
        }
    )
    buffer_service.buffer_match_overview(
        {
            "competition": None,
            "home_team_name": "Valencia CF",
        }
    )

    buffered = buffer_service.get_buffered_match()
    assert buffered.match_overview["competition"] == "La Liga"
    assert buffered.match_overview["home_team_name"] == "Valencia CF"


def test_buffer_player_performance_rejects_duplicate_name_case_insensitive(
    buffer_service: BufferService,
) -> None:
    """The same player cannot be buffered twice, regardless of name casing/spacing."""
    buffer_service.buffer_player_performance({"player_name": "V. Jr", "goals": 1})

    with pytest.raises(DuplicateRecordError):
        buffer_service.buffer_player_performance(
            {"player_name": "  v. jr  ", "goals": 2}
        )


def test_get_buffered_player_from_goalkeeper_payload(
    buffer_service: BufferService,
) -> None:
    """Goalkeeper payloads should extract into a normalized BufferedPlayer object."""
    buffer_service.buffer_player_attributes(
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

    buffered = buffer_service.get_buffered_player()
    assert buffered.player_name == "Giorgi Mamardashvili"
    assert buffered.position == "GK"
    assert buffered.in_game_date == "01/08/24"
    assert buffered.is_goalkeeper is True
    assert buffered.attributes["diving"] == 80


def test_get_buffered_player_requires_both_outfield_pages(
    buffer_service: BufferService,
) -> None:
    """Outfield saves must fail if only one page of attributes is staged."""
    buffer_service.buffer_player_attributes(
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
        buffer_service.get_buffered_player()


def test_remove_player_from_buffer_uses_normalized_name_matching(
    buffer_service: BufferService,
) -> None:
    """Removing a buffered player should be robust to case/whitespace differences."""
    buffer_service.buffer_player_performance(
        {
            "player_name": " Jude Bellingham ",
            "positions_played": ["CM"],
        }
    )
    buffer_service.buffer_player_performance(
        {
            "player_name": "Vinicius Jr",
            "positions_played": ["LW"],
        }
    )

    buffer_service.remove_player_from_buffer("jude bellingham")
    rows = buffer_service.get_buffered_player_performances(display_keys=["player_name"])

    assert len(rows) == 1
    assert rows[0]["player_name"] == "Vinicius Jr"


# ---------------------------------------------------------------------------
# clear_session_buffers / has_unsaved_work
# ---------------------------------------------------------------------------


def test_clear_session_buffers_empties_all_buffers(
    buffer_service: BufferService,
) -> None:
    """clear_session_buffers resets all three session buffers to empty."""
    buffer_service.buffer_player_attributes(
        {"name": "Saka", "in_game_date": "01/08/24"}, is_goalkeeper=True
    )
    buffer_service.buffer_match_overview({"in_game_date": "01/08/24"})
    buffer_service.buffer_player_performance({"player_name": "Saka"})

    buffer_service.clear_session_buffers()

    assert not buffer_service.has_unsaved_work()


def test_has_unsaved_work_returns_false_when_all_buffers_empty(
    buffer_service: BufferService,
) -> None:
    """has_unsaved_work returns False for a freshly initialised BufferService."""
    assert buffer_service.has_unsaved_work() is False


def test_has_unsaved_work_returns_true_when_player_buffer_non_empty(
    buffer_service: BufferService,
) -> None:
    """has_unsaved_work returns True when the player attributes buffer has data."""
    buffer_service.buffer_player_attributes(
        {"name": "Saka", "in_game_date": "01/08/24"}, is_goalkeeper=True
    )
    assert buffer_service.has_unsaved_work() is True


def test_has_unsaved_work_returns_true_when_match_overview_non_empty(
    buffer_service: BufferService,
) -> None:
    """has_unsaved_work returns True when the match overview buffer has data."""
    buffer_service.buffer_match_overview({"in_game_date": "01/08/24"})
    assert buffer_service.has_unsaved_work() is True


def test_has_unsaved_work_returns_true_when_performances_non_empty(
    buffer_service: BufferService,
) -> None:
    """has_unsaved_work returns True when the player performances buffer has data."""
    buffer_service.buffer_player_performance({"player_name": "Saka"})
    assert buffer_service.has_unsaved_work() is True


# ---------------------------------------------------------------------------
# buffer_player_attributes — outfield page 2
# ---------------------------------------------------------------------------


def test_buffer_player_attributes_stores_outfield_page_2(
    buffer_service: BufferService,
) -> None:
    """buffer_player_attributes stores page-2 outfield data in the correct buffer slot."""
    buffer_service.buffer_player_attributes(
        {"name": "Saka", "in_game_date": "01/08/24", "position": "RW", "pace": 90},
        is_goalkeeper=False,
        is_first_page=True,
    )
    buffer_service.buffer_player_attributes(
        {"stamina": 85, "strength": 70},
        is_goalkeeper=False,
        is_first_page=False,
    )

    buffered = buffer_service.get_buffered_player()
    assert buffered.player_name == "Saka"
    assert buffered.attributes["stamina"] == 85
    assert buffered.is_goalkeeper is False


# ---------------------------------------------------------------------------
# get_buffered_player — additional paths
# ---------------------------------------------------------------------------


def test_get_buffered_player_raises_when_buffer_is_empty(
    buffer_service: BufferService,
) -> None:
    """get_buffered_player raises IncompleteDataError when no player is staged."""
    with pytest.raises(IncompleteDataError, match="No player data found in buffer"):
        buffer_service.get_buffered_player()


def test_get_buffered_player_raises_when_name_is_missing(
    buffer_service: BufferService,
) -> None:
    """get_buffered_player raises IncompleteDataError when name field is empty."""
    buffer_service.buffer_player_attributes(
        {"name": "", "in_game_date": "01/08/24"},
        is_goalkeeper=True,
    )

    with pytest.raises(IncompleteDataError, match="Missing required player context"):
        buffer_service.get_buffered_player()


def test_get_buffered_player_raises_when_date_is_missing(
    buffer_service: BufferService,
) -> None:
    """get_buffered_player raises IncompleteDataError when in_game_date is empty."""
    buffer_service.buffer_player_attributes(
        {"name": "Saka", "in_game_date": ""},
        is_goalkeeper=True,
    )

    with pytest.raises(IncompleteDataError, match="Missing required player context"):
        buffer_service.get_buffered_player()


# ---------------------------------------------------------------------------
# reset_player_buffer
# ---------------------------------------------------------------------------


def test_reset_player_buffer_clears_only_player_attributes(
    buffer_service: BufferService,
) -> None:
    """reset_player_buffer clears player attributes but leaves match buffers intact."""
    buffer_service.buffer_player_attributes(
        {"name": "Saka", "in_game_date": "01/08/24"}, is_goalkeeper=True
    )
    buffer_service.buffer_match_overview({"in_game_date": "01/08/24"})

    buffer_service.reset_player_buffer()

    with pytest.raises(IncompleteDataError):
        buffer_service.get_buffered_player()

    buffered = buffer_service.get_buffered_match()
    assert buffered.match_overview["in_game_date"] == "01/08/24"


# ---------------------------------------------------------------------------
# buffer_match_overview — non-dict input
# ---------------------------------------------------------------------------


def test_buffer_match_overview_raises_for_non_dict_input(
    buffer_service: BufferService,
) -> None:
    """buffer_match_overview raises ValueError when given something other than a dict."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        buffer_service.buffer_match_overview("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# buffer_player_performance — validation
# ---------------------------------------------------------------------------


def test_buffer_player_performance_raises_for_non_dict(
    buffer_service: BufferService,
) -> None:
    """buffer_player_performance raises ValueError when given a non-dict."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        buffer_service.buffer_player_performance("not a dict")  # type: ignore[arg-type]


def test_buffer_player_performance_raises_when_player_name_key_missing(
    buffer_service: BufferService,
) -> None:
    """buffer_player_performance raises ValueError when 'player_name' key is absent."""
    with pytest.raises(ValueError, match="player_name"):
        buffer_service.buffer_player_performance({"goals": 1})


# ---------------------------------------------------------------------------
# remove_player_from_buffer — error paths
# ---------------------------------------------------------------------------


def test_remove_player_from_buffer_raises_for_empty_name(
    buffer_service: BufferService,
) -> None:
    """remove_player_from_buffer raises ValueError when given an empty name."""
    with pytest.raises(ValueError, match="non-empty string"):
        buffer_service.remove_player_from_buffer("   ")


def test_remove_player_from_buffer_is_silent_when_player_not_found(
    buffer_service: BufferService,
) -> None:
    """remove_player_from_buffer does not raise when the player is not in the buffer."""
    buffer_service.buffer_player_performance({"player_name": "Saka"})

    buffer_service.remove_player_from_buffer("Bellingham")

    rows = buffer_service.get_buffered_player_performances(display_keys=["player_name"])
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# get_buffered_match — empty buffer
# ---------------------------------------------------------------------------


def test_get_buffered_match_raises_when_no_overview_staged(
    buffer_service: BufferService,
) -> None:
    """get_buffered_match raises IncompleteDataError when no match overview is buffered."""
    with pytest.raises(IncompleteDataError, match="No match overview data found"):
        buffer_service.get_buffered_match()


# ---------------------------------------------------------------------------
# reset_match_buffers
# ---------------------------------------------------------------------------


def test_reset_match_buffers_clears_match_and_performances(
    buffer_service: BufferService,
) -> None:
    """reset_match_buffers clears overview and performances but keeps player attributes."""
    buffer_service.buffer_match_overview({"in_game_date": "01/08/24"})
    buffer_service.buffer_player_performance({"player_name": "Saka"})
    buffer_service.buffer_player_attributes(
        {"name": "Saka", "in_game_date": "01/08/24"}, is_goalkeeper=True
    )

    buffer_service.reset_match_buffers()

    with pytest.raises(IncompleteDataError):
        buffer_service.get_buffered_match()
    assert buffer_service.has_unsaved_work()


# ---------------------------------------------------------------------------
# update_match_overview
# ---------------------------------------------------------------------------


def test_update_match_overview_applies_corrections(
    buffer_service: BufferService,
) -> None:
    """update_match_overview overwrites existing keys with corrected values."""
    buffer_service.buffer_match_overview(
        {"in_game_date": "01/08/24", "home_score": 1}
    )

    buffer_service.update_match_overview({"home_score": 2})

    buffered = buffer_service.get_buffered_match()
    assert buffered.match_overview["home_score"] == 2


def test_update_match_overview_raises_when_no_overview_buffered(
    buffer_service: BufferService,
) -> None:
    """update_match_overview raises IncompleteDataError when no match is staged."""
    with pytest.raises(IncompleteDataError, match="No match is buffered"):
        buffer_service.update_match_overview({"home_score": 2})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# update_player_performance
# ---------------------------------------------------------------------------


def test_update_player_performance_applies_corrections(
    buffer_service: BufferService,
) -> None:
    """update_player_performance overwrites stats for the named player."""
    buffer_service.buffer_player_performance(
        {"player_name": "Saka", "goals": 0}
    )

    buffer_service.update_player_performance("Saka", {"goals": 2})

    rows = buffer_service.get_buffered_player_performances(
        display_keys=["player_name", "goals"]
    )
    assert rows[0]["goals"] == "2"


def test_update_player_performance_raises_when_player_not_in_buffer(
    buffer_service: BufferService,
) -> None:
    """update_player_performance raises PlayerNotFoundInBufferError when not found."""
    buffer_service.buffer_player_performance({"player_name": "Saka"})

    with pytest.raises(PlayerNotFoundInBufferError):
        buffer_service.update_player_performance("Bellingham", {"goals": 1})


# ---------------------------------------------------------------------------
# get_buffered_player_performances — formatting edge cases
# ---------------------------------------------------------------------------


def test_get_buffered_player_performances_skips_entry_missing_id_key(
    buffer_service: BufferService,
) -> None:
    """get_buffered_player_performances skips records that lack a valid id_key."""
    buffer_service.buffer_player_performance({"player_name": "Saka", "goals": 1})
    buffer_service._player_performances_buffer.append({"goals": 2})  # no player_name

    rows = buffer_service.get_buffered_player_performances(
        display_keys=["player_name", "goals"]
    )

    assert len(rows) == 1
    assert rows[0]["player_name"] == "Saka"


def test_get_buffered_player_performances_formats_gk_position_as_gk_string(
    buffer_service: BufferService,
) -> None:
    """get_buffered_player_performances shows 'GK' for positions_played on GK records."""
    buffer_service.buffer_player_performance(
        {
            "player_name": "Raya",
            "performance_type": "GK",
            "positions_played": None,
        }
    )

    rows = buffer_service.get_buffered_player_performances(
        display_keys=["player_name", "positions_played"]
    )

    assert rows[0]["positions_played"] == "GK"


def test_get_buffered_player_performances_formats_list_values_as_joined_string(
    buffer_service: BufferService,
) -> None:
    """get_buffered_player_performances joins list field values with ', '."""
    buffer_service.buffer_player_performance(
        {
            "player_name": "Saka",
            "positions_played": ["RW", "LW"],
        }
    )

    rows = buffer_service.get_buffered_player_performances(
        display_keys=["player_name", "positions_played"]
    )

    assert rows[0]["positions_played"] == "RW, LW"


def test_get_buffered_player_performances_replaces_none_with_default(
    buffer_service: BufferService,
) -> None:
    """get_buffered_player_performances substitutes the default placeholder for None values."""
    buffer_service.buffer_player_performance(
        {"player_name": "Saka", "goals": None}
    )

    rows = buffer_service.get_buffered_player_performances(
        display_keys=["player_name", "goals"], default="-"
    )

    assert rows[0]["goals"] == "-"
