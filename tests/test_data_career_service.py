"""Tests for the data-layer CareerService."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.schemas import CareerDetail, CareerMetadata
from src.services.data.career_service import CareerService


@pytest.fixture
def service() -> CareerService:
    """Return a fresh data-layer CareerService."""
    return CareerService()


def _metadata(
    club_name: str = "Valencia CF",
    manager_name: str = "Ruben Baraja",
    competitions: list[str] | None = None,
) -> CareerMetadata:
    """Construct a minimal CareerMetadata for testing."""
    return CareerMetadata(
        career_id=1,
        club_name=club_name,
        folder_name=f"{club_name.replace(' ', '_').lower()}_1",
        manager_name=manager_name,
        created_at=datetime(2024, 8, 1),
        starting_season="24/25",
        half_length=6,
        difficulty="Professional",
        league="La Liga",
        competitions=competitions if competitions is not None else [],
    )


def _detail(club_name: str, career_id: int = 1) -> CareerDetail:
    """Construct a minimal CareerDetail for testing."""
    return CareerDetail(
        id=career_id,
        club_name=club_name,
        folder_name=f"{club_name.replace(' ', '_').lower()}_{career_id}",
    )


def _mock_match(competition: str) -> MagicMock:
    """Return a mock Match whose data.competition is the given string."""
    m = MagicMock()
    m.data.competition = competition
    return m


# ---------------------------------------------------------------------------
# prepare_new_career — config loading paths
# ---------------------------------------------------------------------------


def test_prepare_new_career_loads_default_competitions_from_config(
    tmp_path: Path,
    service: CareerService,
) -> None:
    """prepare_new_career seeds competitions from the league_competitions config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "league_competitions.json").write_text(
        json.dumps({
            "leagues": {
                "La Liga": ["La Liga", "Copa Del Rey", "UEFA Champions League"]
            }
        }),
        encoding="utf-8",
    )

    result = service.prepare_new_career(
        data_folder=tmp_path / "data",
        project_root=tmp_path,
        club_name="Valencia CF",
        manager_name="Ruben Baraja",
        starting_season="24/25",
        half_length=6,
        difficulty="Professional",
        league="La Liga",
        career_id=1,
    )

    assert "La Liga" in result.metadata.competitions
    assert "Copa Del Rey" in result.metadata.competitions
    assert "UEFA Champions League" in result.metadata.competitions


def test_prepare_new_career_returns_empty_competitions_when_config_absent(
    tmp_path: Path,
    service: CareerService,
) -> None:
    """prepare_new_career returns empty competition list when config file is absent."""
    result = service.prepare_new_career(
        data_folder=tmp_path / "data",
        project_root=tmp_path,
        club_name="Valencia CF",
        manager_name="Ruben Baraja",
        starting_season="24/25",
        half_length=6,
        difficulty="Professional",
        league="La Liga",
        career_id=1,
    )

    assert result.metadata.competitions == []


def test_prepare_new_career_returns_empty_competitions_on_corrupt_config(
    tmp_path: Path,
    service: CareerService,
) -> None:
    """prepare_new_career falls back to empty competitions when config JSON is invalid."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "league_competitions.json").write_text(
        "not valid json !!!", encoding="utf-8"
    )

    result = service.prepare_new_career(
        data_folder=tmp_path / "data",
        project_root=tmp_path,
        club_name="Valencia CF",
        manager_name="Ruben Baraja",
        starting_season="24/25",
        half_length=6,
        difficulty="Professional",
        league="La Liga",
        career_id=1,
    )

    assert result.metadata.competitions == []


def test_prepare_new_career_returns_empty_competitions_when_league_not_in_config(
    tmp_path: Path,
    service: CareerService,
) -> None:
    """prepare_new_career returns empty competitions when the league is not in the config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "league_competitions.json").write_text(
        json.dumps({"leagues": {"Premier League": ["Premier League"]}}),
        encoding="utf-8",
    )

    result = service.prepare_new_career(
        data_folder=tmp_path / "data",
        project_root=tmp_path,
        club_name="Valencia CF",
        manager_name="Ruben Baraja",
        starting_season="24/25",
        half_length=6,
        difficulty="Professional",
        league="La Liga",
        career_id=1,
    )

    assert result.metadata.competitions == []


def test_prepare_new_career_assembles_correct_folder_paths(
    tmp_path: Path,
    service: CareerService,
) -> None:
    """prepare_new_career builds normalized folder names and file paths."""
    result = service.prepare_new_career(
        data_folder=tmp_path / "data",
        project_root=tmp_path,
        club_name="Valencia CF",
        manager_name="Ruben Baraja",
        starting_season="24/25",
        half_length=6,
        difficulty="Professional",
        league="La Liga",
        career_id=2,
    )

    assert result.career_folder_name == "valencia_cf_2"
    assert result.career_path == tmp_path / "data" / "valencia_cf_2"
    assert result.players_path == tmp_path / "data" / "valencia_cf_2" / "players.json"
    assert result.matches_path == tmp_path / "data" / "valencia_cf_2" / "matches.json"


# ---------------------------------------------------------------------------
# get_duplicate_club_names
# ---------------------------------------------------------------------------


def test_get_duplicate_club_names_identifies_repeated_clubs() -> None:
    """get_duplicate_club_names returns clubs appearing more than once."""
    details = [
        _detail("Valencia CF", 1),
        _detail("Valencia CF", 2),
        _detail("Arsenal", 3),
    ]

    result = CareerService.get_duplicate_club_names(details)

    assert result == {"Valencia CF"}
    assert "Arsenal" not in result


def test_get_duplicate_club_names_returns_empty_when_all_unique() -> None:
    """get_duplicate_club_names returns an empty set when all club names differ."""
    details = [_detail("Valencia CF", 1), _detail("Arsenal", 2)]

    result = CareerService.get_duplicate_club_names(details)

    assert result == set()


def test_get_duplicate_club_names_empty_list_returns_empty_set() -> None:
    """get_duplicate_club_names returns an empty set for an empty input."""
    assert CareerService.get_duplicate_club_names([]) == set()


# ---------------------------------------------------------------------------
# build_display_name
# ---------------------------------------------------------------------------


def test_build_display_name_returns_club_name_when_not_duplicate() -> None:
    """build_display_name returns just the club name when is_duplicate is False."""
    detail = _detail("Valencia CF")

    result = CareerService.build_display_name(detail, is_duplicate=False, metadata=None)

    assert result == "Valencia CF"


def test_build_display_name_appends_manager_name_when_duplicate_with_metadata() -> None:
    """build_display_name appends the manager name when duplicate and metadata is present."""
    detail = _detail("Valencia CF")
    meta = _metadata(manager_name="Ruben Baraja")

    result = CareerService.build_display_name(detail, is_duplicate=True, metadata=meta)

    assert result == "Valencia CF (Ruben Baraja)"


def test_build_display_name_appends_career_id_when_duplicate_without_metadata() -> None:
    """build_display_name falls back to career id when duplicate but no metadata."""
    detail = _detail("Valencia CF", career_id=3)

    result = CareerService.build_display_name(detail, is_duplicate=True, metadata=None)

    assert result == "Valencia CF (3)"


# ---------------------------------------------------------------------------
# build_display_names
# ---------------------------------------------------------------------------


def test_build_display_names_produces_label_for_each_career(
    service: CareerService,
) -> None:
    """build_display_names returns one label per CareerDetail in input order."""
    details = [_detail("Valencia CF", 1), _detail("Arsenal", 2)]
    meta = _metadata()
    metadata_by_folder = {
        "valencia_cf_1": meta,
        "arsenal_2": None,
    }

    result = service.build_display_names(details, set(), metadata_by_folder)

    assert result == ["Valencia CF", "Arsenal"]


def test_build_display_names_disambiguates_duplicate_clubs(
    service: CareerService,
) -> None:
    """build_display_names appends manager name when clubs share the same name."""
    details = [_detail("Valencia CF", 1), _detail("Valencia CF", 2)]
    meta1 = _metadata(manager_name="Baraja")
    meta2 = _metadata(manager_name="Paco")
    metadata_by_folder = {
        "valencia_cf_1": meta1,
        "valencia_cf_2": meta2,
    }

    result = service.build_display_names(details, {"Valencia CF"}, metadata_by_folder)

    assert result == ["Valencia CF (Baraja)", "Valencia CF (Paco)"]


# ---------------------------------------------------------------------------
# find_career_by_display_name
# ---------------------------------------------------------------------------


def test_find_career_by_display_name_returns_matching_detail(
    service: CareerService,
) -> None:
    """find_career_by_display_name returns the detail whose display name matches."""
    details = [_detail("Valencia CF", 1), _detail("Arsenal", 2)]

    result = service.find_career_by_display_name(
        careers_details=details,
        duplicate_club_names=set(),
        metadata_by_folder={},
        selected_name="Arsenal",
    )

    assert result is not None
    assert result.club_name == "Arsenal"


def test_find_career_by_display_name_returns_none_when_no_match(
    service: CareerService,
) -> None:
    """find_career_by_display_name returns None when no career matches the name."""
    details = [_detail("Valencia CF")]

    result = service.find_career_by_display_name(
        careers_details=details,
        duplicate_club_names=set(),
        metadata_by_folder={},
        selected_name="Atletico Madrid",
    )

    assert result is None


# ---------------------------------------------------------------------------
# add_competition_to_metadata
# ---------------------------------------------------------------------------


def test_add_competition_appends_normalized_name_and_returns_true(
    service: CareerService,
) -> None:
    """add_competition_to_metadata adds a new competition and returns True."""
    meta = _metadata(competitions=["La Liga"])

    changed = service.add_competition_to_metadata(
        metadata=meta, competition="copa del rey"
    )

    assert changed is True
    assert "Copa Del Rey" in meta.competitions


def test_add_competition_returns_false_when_already_present(
    service: CareerService,
) -> None:
    """add_competition_to_metadata returns False when competition is already listed."""
    meta = _metadata(competitions=["La Liga"])

    changed = service.add_competition_to_metadata(
        metadata=meta, competition="la liga"
    )

    assert changed is False
    assert meta.competitions.count("La Liga") == 1


# ---------------------------------------------------------------------------
# ensure_competition_not_referenced
# ---------------------------------------------------------------------------


def test_ensure_competition_not_referenced_raises_when_match_uses_it(
    service: CareerService,
) -> None:
    """ensure_competition_not_referenced raises ValueError when a match references it."""
    matches = [_mock_match("La Liga")]

    with pytest.raises(ValueError, match="La Liga"):
        service.ensure_competition_not_referenced(
            matches=matches, competition="la liga"
        )


def test_ensure_competition_not_referenced_passes_when_no_match_uses_it(
    service: CareerService,
) -> None:
    """ensure_competition_not_referenced does not raise when no match references it."""
    matches = [_mock_match("La Liga")]

    service.ensure_competition_not_referenced(
        matches=matches, competition="Copa Del Rey"
    )


def test_ensure_competition_not_referenced_passes_with_empty_match_list(
    service: CareerService,
) -> None:
    """ensure_competition_not_referenced does not raise with an empty match list."""
    service.ensure_competition_not_referenced(matches=[], competition="La Liga")


# ---------------------------------------------------------------------------
# remove_competition_from_metadata
# ---------------------------------------------------------------------------


def test_remove_competition_removes_and_returns_true(service: CareerService) -> None:
    """remove_competition_from_metadata removes a competition and returns True."""
    meta = _metadata(competitions=["La Liga", "Copa Del Rey"])

    changed = service.remove_competition_from_metadata(
        metadata=meta, competition="copa del rey"
    )

    assert changed is True
    assert "Copa Del Rey" not in meta.competitions
    assert "La Liga" in meta.competitions


def test_remove_competition_returns_false_when_not_present(
    service: CareerService,
) -> None:
    """remove_competition_from_metadata returns False when competition is not listed."""
    meta = _metadata(competitions=["La Liga"])

    changed = service.remove_competition_from_metadata(
        metadata=meta, competition="Premier League"
    )

    assert changed is False
    assert meta.competitions == ["La Liga"]


# ---------------------------------------------------------------------------
# build_updated_metadata
# ---------------------------------------------------------------------------


def test_build_updated_metadata_applies_valid_patch(service: CareerService) -> None:
    """build_updated_metadata returns updated CareerMetadata when the patch is valid."""
    meta = _metadata()

    updated = service.build_updated_metadata(
        metadata=meta,
        updates={"manager_name": "Paco Lopez"},  # type: ignore[typeddict-item]
    )

    assert updated.manager_name == "Paco Lopez"
    assert updated.club_name == "Valencia CF"


def test_build_updated_metadata_raises_on_invalid_patch(
    service: CareerService,
) -> None:
    """build_updated_metadata raises ValidationError when the patch produces invalid data."""
    meta = _metadata()

    with pytest.raises(ValidationError):
        service.build_updated_metadata(
            metadata=meta,
            updates={"half_length": []},  # type: ignore[typeddict-item]
        )
