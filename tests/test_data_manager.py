"""Tests for DataManager persistence, lifecycle, and guard-clause methods."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.data_manager import DataManager


def _gk_player_data(name: str = "David Raya") -> dict[str, object]:
    """Return a minimal valid goalkeeper player UI payload."""
    return {
        "name": name,
        "age": 29,
        "height": "6'1\"",
        "weight": 183,
        "country": "Spain",
        "in_game_date": "01/08/24",
        "diving": 84,
        "handling": 78,
        "kicking": 74,
        "reflexes": 86,
        "positioning": 81,
    }


# ---------------------------------------------------------------------------
# get_all_career_names
# ---------------------------------------------------------------------------


def test_get_all_career_names_returns_single_career(tmp_path: Path) -> None:
    """get_all_career_names returns one label when only one career exists."""
    dm = DataManager(project_root=tmp_path)
    dm.create_new_career(
        "Valencia CF", "Ruben Baraja", "24/25", 6, "Professional", "La Liga"
    )

    names = dm.get_all_career_names()

    assert names == ["Valencia CF"]


def test_get_all_career_names_disambiguates_duplicate_club_names(
    tmp_path: Path,
) -> None:
    """get_all_career_names appends manager names when two careers share a club."""
    dm = DataManager(project_root=tmp_path)
    dm.create_new_career(
        "Valencia CF", "Ruben Baraja", "24/25", 6, "Professional", "La Liga"
    )
    dm.create_new_career(
        "Valencia CF", "Paco Lopez", "25/26", 6, "Professional", "La Liga"
    )

    names = dm.get_all_career_names()

    assert "Valencia CF (Ruben Baraja)" in names
    assert "Valencia CF (Paco Lopez)" in names


# ---------------------------------------------------------------------------
# get_career_details
# ---------------------------------------------------------------------------


def test_get_career_details_returns_none_for_unknown_career(tmp_path: Path) -> None:
    """get_career_details returns None when no career matches the display name."""
    dm = DataManager(project_root=tmp_path)
    dm.create_new_career(
        "Valencia CF", "Ruben Baraja", "24/25", 6, "Professional", "La Liga"
    )

    result = dm.get_career_details("Atletico Madrid")

    assert result is None


def test_get_career_details_resolves_duplicate_club_career(tmp_path: Path) -> None:
    """get_career_details returns correct metadata when two careers share a club name."""
    dm = DataManager(project_root=tmp_path)
    dm.create_new_career(
        "Valencia CF", "Ruben Baraja", "24/25", 6, "Professional", "La Liga"
    )
    dm.create_new_career(
        "Valencia CF", "Paco Lopez", "25/26", 6, "Professional", "La Liga"
    )

    result = dm.get_career_details("Valencia CF (Ruben Baraja)")

    assert result is not None
    assert result.manager_name == "Ruben Baraja"


# ---------------------------------------------------------------------------
# load_career
# ---------------------------------------------------------------------------


def test_load_career_returns_false_for_unknown_career(tmp_path: Path) -> None:
    """load_career returns False when the requested career name does not exist."""
    dm = DataManager(project_root=tmp_path)
    dm.create_new_career(
        "Valencia CF", "Ruben Baraja", "24/25", 6, "Professional", "La Liga"
    )

    result = dm.load_career("Arsenal")

    assert result is False


# ---------------------------------------------------------------------------
# get_current_career_metadata
# ---------------------------------------------------------------------------


def test_get_current_career_metadata_returns_none_without_career(
    tmp_path: Path,
) -> None:
    """get_current_career_metadata returns None when no career context is set."""
    dm = DataManager(project_root=tmp_path)

    result = dm.get_current_career_metadata()

    assert result is None


# ---------------------------------------------------------------------------
# add_competition
# ---------------------------------------------------------------------------


def test_add_competition_persists_new_competition(
    loaded_data_manager: DataManager,
) -> None:
    """add_competition appends a new competition to the metadata on disk."""
    loaded_data_manager.add_competition("Copa Del Rey")

    meta = loaded_data_manager.get_current_career_metadata()
    assert meta is not None
    assert "Copa Del Rey" in meta.competitions


def test_add_competition_is_idempotent(loaded_data_manager: DataManager) -> None:
    """add_competition does not create duplicates when called twice."""
    loaded_data_manager.add_competition("Copa Del Rey")
    loaded_data_manager.add_competition("Copa Del Rey")

    meta = loaded_data_manager.get_current_career_metadata()
    assert meta is not None
    assert meta.competitions.count("Copa Del Rey") == 1


def test_add_competition_raises_without_active_career(tmp_path: Path) -> None:
    """add_competition raises RuntimeError when no career is loaded."""
    dm = DataManager(project_root=tmp_path)

    with pytest.raises(RuntimeError, match="No career loaded"):
        dm.add_competition("La Liga")


# ---------------------------------------------------------------------------
# remove_competition
# ---------------------------------------------------------------------------


def test_remove_competition_persists_removal(loaded_data_manager: DataManager) -> None:
    """remove_competition removes a competition from metadata on disk."""
    loaded_data_manager.add_competition("Copa Del Rey")

    loaded_data_manager.remove_competition("Copa Del Rey")

    meta = loaded_data_manager.get_current_career_metadata()
    assert meta is not None
    assert "Copa Del Rey" not in meta.competitions


def test_remove_competition_raises_without_active_career(tmp_path: Path) -> None:
    """remove_competition raises RuntimeError when no career is loaded."""
    dm = DataManager(project_root=tmp_path)

    with pytest.raises(RuntimeError, match="No career loaded"):
        dm.remove_competition("La Liga")


# ---------------------------------------------------------------------------
# update_career_metadata
# ---------------------------------------------------------------------------


def test_update_career_metadata_persists_changes(
    loaded_data_manager: DataManager,
) -> None:
    """update_career_metadata writes the patched metadata back to disk."""
    loaded_data_manager.update_career_metadata(
        {"manager_name": "Paco Lopez"}  # type: ignore[typeddict-item]
    )

    meta = loaded_data_manager.get_current_career_metadata()
    assert meta is not None
    assert meta.manager_name == "Paco Lopez"


def test_update_career_metadata_raises_without_active_career(
    tmp_path: Path,
) -> None:
    """update_career_metadata raises RuntimeError when no career is loaded."""
    dm = DataManager(project_root=tmp_path)

    with pytest.raises(RuntimeError, match="No career loaded"):
        dm.update_career_metadata(
            {"manager_name": "Test"}  # type: ignore[typeddict-item]
        )


# ---------------------------------------------------------------------------
# refresh_players / refresh_matches
# ---------------------------------------------------------------------------


def test_refresh_players_reloads_cache_from_disk(
    loaded_data_manager: DataManager,
) -> None:
    """refresh_players re-populates the in-memory cache from the current disk state."""
    loaded_data_manager.add_or_update_player(
        player_ui_data=_gk_player_data("David Raya"),
        position="GK",
        in_game_date="01/08/24",
        is_gk=True,
    )
    original_count = len(loaded_data_manager.players)

    loaded_data_manager.players = []
    loaded_data_manager.refresh_players()

    assert len(loaded_data_manager.players) == original_count


def test_refresh_players_is_no_op_without_career(tmp_path: Path) -> None:
    """refresh_players does not raise when no career is loaded."""
    dm = DataManager(project_root=tmp_path)

    dm.refresh_players()

    assert dm.players == []


def test_refresh_matches_is_no_op_without_career(tmp_path: Path) -> None:
    """refresh_matches does not raise when no career is loaded."""
    dm = DataManager(project_root=tmp_path)

    dm.refresh_matches()

    assert dm.matches == []


# ---------------------------------------------------------------------------
# get_latest_match_in_game_date
# ---------------------------------------------------------------------------


def test_get_latest_match_in_game_date_returns_none_without_career(
    tmp_path: Path,
) -> None:
    """get_latest_match_in_game_date returns None when no career is loaded."""
    dm = DataManager(project_root=tmp_path)

    result = dm.get_latest_match_in_game_date()

    assert result is None


# ---------------------------------------------------------------------------
# add_or_update_player — update (existing player) path
# ---------------------------------------------------------------------------


def test_add_or_update_player_updates_existing_player(
    loaded_data_manager: DataManager,
) -> None:
    """Calling add_or_update_player twice for the same player appends a new snapshot."""
    loaded_data_manager.add_or_update_player(
        player_ui_data=_gk_player_data("David Raya"),
        position="GK",
        in_game_date="01/08/24",
        is_gk=True,
    )

    updated_data = _gk_player_data("David Raya")
    updated_data["reflexes"] = 90
    loaded_data_manager.add_or_update_player(
        player_ui_data=updated_data,
        position="GK",
        in_game_date="01/09/24",
        is_gk=True,
    )

    assert len(loaded_data_manager.players) == 1
    player = loaded_data_manager.find_player_by_name("David Raya")
    assert player is not None
    assert len(player.attribute_history) == 2


# ---------------------------------------------------------------------------
# _generate_match_id_from_raw_rows (static helper)
# ---------------------------------------------------------------------------


def test_generate_match_id_from_raw_rows_returns_next_after_max(
    tmp_path: Path,
) -> None:
    """_generate_match_id_from_raw_rows returns max id + 1."""
    rows = [{"id": 1}, {"id": 3}, {"id": 2}]

    result = DataManager._generate_match_id_from_raw_rows(rows)

    assert result == 4


def test_generate_match_id_from_raw_rows_skips_non_dict_entries(
    tmp_path: Path,
) -> None:
    """_generate_match_id_from_raw_rows ignores non-dict entries in the list."""
    rows: list[object] = ["not a dict", {"id": 5}, None]

    result = DataManager._generate_match_id_from_raw_rows(rows)  # type: ignore[arg-type]

    assert result == 6


def test_generate_match_id_from_raw_rows_returns_1_for_empty_list() -> None:
    """_generate_match_id_from_raw_rows returns 1 when there are no existing rows."""
    result = DataManager._generate_match_id_from_raw_rows([])

    assert result == 1


# ---------------------------------------------------------------------------
# Internal guard-clause helpers
# ---------------------------------------------------------------------------


def test_require_players_path_raises_without_career(tmp_path: Path) -> None:
    """_require_players_path raises RuntimeError when no career is active."""
    dm = DataManager(project_root=tmp_path)

    with pytest.raises(RuntimeError, match="no active career"):
        dm._require_players_path()


def test_require_matches_path_raises_without_career(tmp_path: Path) -> None:
    """_require_matches_path raises RuntimeError when no career is active."""
    dm = DataManager(project_root=tmp_path)

    with pytest.raises(RuntimeError, match="no active career"):
        dm._require_matches_path()


def test_load_players_strict_or_raise_raises_without_career(tmp_path: Path) -> None:
    """_load_players_strict_or_raise raises RuntimeError when no career is active."""
    dm = DataManager(project_root=tmp_path)

    with pytest.raises(RuntimeError, match="no active career"):
        dm._load_players_strict_or_raise()


def test_load_matches_strict_or_raise_raises_without_career(tmp_path: Path) -> None:
    """_load_matches_strict_or_raise raises RuntimeError when no career is active."""
    dm = DataManager(project_root=tmp_path)

    with pytest.raises(RuntimeError, match="no active career"):
        dm._load_matches_strict_or_raise()
