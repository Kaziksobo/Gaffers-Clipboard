"""Check that real career saves still load and save through DataManager.

Careers are copied (a slice of the first matches, every player) into a scratch
``data/`` folder, so the datasets are never written to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.data_manager import DataManager

if TYPE_CHECKING:
    from tests.data.conftest import CareerRecords, ProjectBuilder


def test_career_loads_through_data_manager(
    career_name: str,
    careers: dict[str, CareerRecords],
    build_career_project: ProjectBuilder,
    slice_matches: int,
) -> None:
    """Each career loads with the expected number of matches and players."""
    career = careers[career_name]
    manager = build_career_project(career_name)

    assert manager.load_career(career.club) is True
    assert len(manager.matches) == min(slice_matches, len(career.matches))
    assert len(manager.players) == len(career.players)


def test_pre_suspension_saves_still_load(
    career_name: str,
    careers: dict[str, CareerRecords],
    build_career_project: ProjectBuilder,
) -> None:
    """A save written before suspension tracking existed still loads.

    The key is removed from every player to simulate the older schema, regardless
    of which app version exported the dataset.
    """
    career = careers[career_name]
    manager = build_career_project(
        career_name, drop_player_keys=("suspension_history",)
    )

    assert manager.load_career(career.club) is True
    assert len(manager.players) == len(career.players)
    assert all(p.suspension_history == [] for p in manager.players)


def test_old_save_accepts_a_suspension_and_changes_nothing_else(
    career_name: str,
    careers: dict[str, CareerRecords],
    build_career_project: ProjectBuilder,
) -> None:
    """An older save adopts the suspension feature without disturbing other data."""
    career = careers[career_name]
    manager = build_career_project(
        career_name, drop_player_keys=("suspension_history",)
    )
    assert manager.load_career(career.club) is True
    target = manager.players[0]
    others_before = [p.model_dump() for p in manager.players if p.id != target.id]

    manager.add_suspension_record(
        target.name,
        {"in_game_date": "01/01/40", "reason": "Red Card", "matches_out": 3},
    )

    reloaded = DataManager(project_root=manager.project_root)
    assert reloaded.load_career(career.club) is True
    updated = reloaded.find_player_by_name(target.name)
    assert updated is not None
    assert len(updated.suspension_history) == 1
    assert updated.suspension_history[0].matches_out == 3
    others_after = [p.model_dump() for p in reloaded.players if p.id != target.id]
    assert others_after == others_before
    assert len(reloaded.matches) == len(manager.matches)
