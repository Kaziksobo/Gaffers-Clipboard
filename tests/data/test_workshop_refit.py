"""Check the refit pipeline: validation, movement, and promotion with a backup."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from workshop.lib import fit, refit

_CONFIG = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture
def scratch_config(tmp_path: Path) -> Path:
    """Return a throwaway copy of the live config directory."""
    folder = tmp_path / "config"
    folder.mkdir()
    for name in (fit.WEIGHTS_FILE, fit.MEANS_STDS_FILE, fit.MANIFEST_FILE):
        shutil.copy(_CONFIG / name, folder / name)
    return folder


@pytest.fixture(scope="module")
def candidate(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Fit Valencia only (every section, derived included) into a candidate."""
    folder = tmp_path_factory.mktemp("candidate")
    result = refit.fit_all(["valencia_cf_1"])
    fit.write_candidate(folder, result, note="test candidate")
    return folder


def test_the_live_config_is_sound() -> None:
    """The shipped config passes the same checks a candidate must pass."""
    assert refit.validate_config(_CONFIG) == []


def test_validation_catches_a_broken_config(scratch_config: Path) -> None:
    """Weights that do not sum to 1, or a negative std, are reported."""
    weights_path = scratch_config / fit.WEIGHTS_FILE
    weights = json.loads(weights_path.read_text("utf-8"))
    weights["CB"]["goals_p90"] += 0.1
    weights_path.write_text(json.dumps(weights), "utf-8")
    means_path = scratch_config / fit.MEANS_STDS_FILE
    means = json.loads(means_path.read_text("utf-8"))
    means["ST"]["passes_p90"]["std"] = -1.0
    means_path.write_text(json.dumps(means), "utf-8")

    problems = refit.validate_config(scratch_config)

    assert any("weights[CB]" in p for p in problems)
    assert any("means_stds[ST][passes_p90]" in p for p in problems)


def test_a_config_does_not_move_from_itself() -> None:
    """Movement of the live config against itself is zero everywhere."""
    moved = refit.movement(_CONFIG, _CONFIG)
    assert (moved["max_weight_change"] == 0).all()
    assert (moved["max_mean_shift_in_stds"] == 0).all()
    assert (moved["std_switches"] == 0).all()


def test_a_fit_over_all_sections_is_sound_and_complete(candidate: Path) -> None:
    """A refit produces every section the live config has, and passes validation."""
    assert refit.validate_config(candidate) == []
    live = json.loads((_CONFIG / fit.WEIGHTS_FILE).read_text("utf-8"))
    cand = json.loads((candidate / fit.WEIGHTS_FILE).read_text("utf-8"))
    assert set(cand) == set(live)


def test_promote_replaces_the_config_and_keeps_a_backup(
    candidate: Path, scratch_config: Path, tmp_path: Path
) -> None:
    """Promotion copies the candidate over the config and backs up what it replaced."""
    before = fit.config_hash(scratch_config)
    info = refit.promote(candidate, scratch_config, tmp_path / "backups")

    assert info["previous_hash"] == before
    assert info["new_hash"] == fit.config_hash(candidate)
    assert fit.config_hash(scratch_config) == info["new_hash"]
    manifest = json.loads((scratch_config / fit.MANIFEST_FILE).read_text("utf-8"))
    assert manifest["config_hash"] == fit.config_hash(scratch_config)
    backup = Path(info["backup"])
    assert backup.name == f"previous_{before[:8]}"
    assert fit.config_hash(backup) == before


def test_promote_refuses_a_candidate_whose_manifest_is_stale(
    candidate: Path, scratch_config: Path, tmp_path: Path
) -> None:
    """A candidate edited after it was written cannot be promoted."""
    tampered = tmp_path / "tampered"
    shutil.copytree(candidate, tampered)
    path = tampered / fit.WEIGHTS_FILE
    weights = json.loads(path.read_text("utf-8"))
    first = next(iter(weights["CB"]))
    weights["CB"][first], weights["CB"]["tackles_p90"] = (
        weights["CB"]["tackles_p90"],
        weights["CB"][first],
    )
    path.write_text(json.dumps(weights, indent=4), "utf-8")

    with pytest.raises(ValueError, match="manifest hash"):
        refit.promote(tampered, scratch_config, tmp_path / "backups")
    assert fit.config_hash(scratch_config) == fit.config_hash(_CONFIG)


def test_promote_refuses_an_unsound_candidate(
    candidate: Path, scratch_config: Path, tmp_path: Path
) -> None:
    """A candidate whose weights do not sum to 1 is rejected before copying."""
    broken = tmp_path / "broken"
    shutil.copytree(candidate, broken)
    path = broken / fit.WEIGHTS_FILE
    weights = json.loads(path.read_text("utf-8"))
    weights["CM"]["goals_p90"] += 0.5
    path.write_text(json.dumps(weights, indent=4), "utf-8")

    with pytest.raises(ValueError, match="not sound"):
        refit.promote(broken, scratch_config, tmp_path / "backups")
    assert fit.config_hash(scratch_config) == fit.config_hash(_CONFIG)
