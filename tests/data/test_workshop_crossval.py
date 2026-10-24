"""Check leave-one-career-out configs exclude their career and give complete ratings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from workshop.lib import crossval, datasets, fit, rating


@pytest.fixture(scope="module")
def configs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Fit the three folds once, into a scratch folder."""
    return crossval.loco_configs(root=tmp_path_factory.mktemp("loco"))


def test_one_fold_per_career_and_none_sees_its_own_career(
    configs: dict[str, Path],
) -> None:
    """Each fold's manifest cites every career except the held-out one."""
    names = set(datasets.career_names("pool"))
    assert set(configs) == names
    for held_out, directory in configs.items():
        manifest = json.loads((directory / fit.MANIFEST_FILE).read_text("utf-8"))
        cited = set(next(iter(manifest["fitted_sections"].values()))["sources"])
        assert cited == names - {held_out}
        assert manifest["config_hash"] == fit.config_hash(directory)


def test_folds_differ_from_the_live_config(configs: dict[str, Path]) -> None:
    """Dropping a career changes the fit (otherwise the check would be vacuous)."""
    live = fit.config_hash()
    assert all(fit.config_hash(d) != live for d in configs.values())
    assert len({fit.config_hash(d) for d in configs.values()}) == len(configs)


def test_oos_ratings_cover_every_performance_with_the_right_config(
    configs: dict[str, Path],
) -> None:
    """Every performance gets exactly one out-of-sample rating, from its own fold."""
    oos = crossval.oos_ratings(configs)
    total = len(rating.rated_performances("pool"))
    assert len(oos) == total
    assert not oos.duplicated(["career", "match_id", "player_id"]).any()

    career = "ipswich_3"
    direct = rating.rated_performances(
        names=[career], config_dir=configs[career], column="rating_oos"
    )
    mine = oos[oos["career"] == career].reset_index(drop=True)
    assert mine["rating_oos"].equals(direct["rating_oos"])


def test_loco_needs_two_careers() -> None:
    """A single career cannot be held out."""
    with pytest.raises(ValueError, match="at least two"):
        crossval.loco_configs(["valencia_cf_1"])
