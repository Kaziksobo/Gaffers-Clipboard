"""Integrity checks for every career dataset registered in ``datasets/careers.toml``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    from tests.data.conftest import CareerRecords

_KNOWN_TAGS = {"calibration", "ood", "pool"}
_DATA_FILES = ("matches.json", "players.json", "metadata.json")


def test_every_career_folder_is_registered(
    datasets_dir: Path, manifest: dict[str, dict[str, Any]]
) -> None:
    """Folders under datasets/careers and manifest entries match one-to-one."""
    folders = {p.name for p in (datasets_dir / "careers").iterdir() if p.is_dir()}
    assert folders == set(manifest)


def test_tags_are_known(manifest: dict[str, dict[str, Any]]) -> None:
    """Only the documented tags are used."""
    unknown = {
        name: sorted(set(entry["tags"]) - _KNOWN_TAGS)
        for name, entry in manifest.items()
        if set(entry["tags"]) - _KNOWN_TAGS
    }
    assert not unknown


def test_calibration_and_ood_never_mix(manifest: dict[str, dict[str, Any]]) -> None:
    """A career is either calibration data or out-of-distribution, never both."""
    mixed = [
        name
        for name, entry in manifest.items()
        if {"calibration", "ood"} <= set(entry["tags"])
    ]
    assert not mixed, f"Tagged both calibration and ood: {mixed}"


def test_career_files_present(career_name: str, datasets_dir: Path) -> None:
    """Each career folder holds the three app-written JSON files."""
    folder = datasets_dir / "careers" / career_name
    missing = [f for f in _DATA_FILES if not (folder / f).is_file()]
    assert not missing


def test_career_passes_import_checks(
    career_name: str,
    careers: dict[str, CareerRecords],
    import_career: ModuleType,
) -> None:
    """Datasets satisfy the same checks scripts/import_career.py applies."""
    c = careers[career_name]
    assert import_career.validate_career(c.name, c.matches, c.players, c.metadata) == []


def test_manifest_matches_dataset(
    career_name: str,
    careers: dict[str, CareerRecords],
    manifest: dict[str, dict[str, Any]],
) -> None:
    """The manifest's pinned match count and club agree with the files.

    A mismatch usually means a file was overwritten by hand with an older or newer
    export instead of going through scripts/import_career.py.
    """
    c, entry = careers[career_name], manifest[career_name]
    assert len(c.matches) == entry["matches"]
    assert c.club == entry["club"]
    assert c.metadata["club_name"] == entry["club"]


def test_ratings_status_is_accurate(
    career_name: str,
    careers: dict[str, CareerRecords],
    manifest: dict[str, dict[str, Any]],
) -> None:
    """``ratings = "stripped"`` means every stored rating really is null."""
    ratings = [
        perf.get("match_rating")
        for match in careers[career_name].matches
        for perf in match["player_performances"]
    ]
    if manifest[career_name]["ratings"] == "stripped":
        assert all(r is None for r in ratings)
    else:
        assert any(r is not None for r in ratings)
