"""Leave-one-career-out (LOCO) evaluation of the rating config.

The live config is fitted on every career, so ratings from it are in-sample for all of them.
To see how the *procedure* generalises, fit a config on all careers but one, then rate the
held-out career with it. Doing this for each career gives an out-of-sample rating for every
performance in the data (each from a config that never saw its career).

Folds are small when only a few careers exist (the Valencia fold is fitted on the other two
careers' 60 matches), so out-of-sample numbers are noisier than in-sample ones. They improve
as more careers and matches are added: the folds are always rebuilt from ``datasets/``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from workshop.lib import datasets, fit, rating, refit

LOCO_DIR = refit.CANDIDATES_DIR / "loco"
_KEYS = ["career", "match_id", "player_id"]


def loco_configs(
    careers: list[str] | None = None, root: Path = LOCO_DIR
) -> dict[str, Path]:
    """Fit and write one config per held-out career, each on all the other careers.

    Args:
        careers: Careers to include (default: every career tagged ``pool``).
        root: Folder the fold configs are written under (one sub-folder per career).

    Returns:
        ``{held-out career: config directory}``.
    """
    names = careers or datasets.career_names("pool")
    if len(names) < 2:
        raise ValueError("leave-one-career-out needs at least two careers")
    configs: dict[str, Path] = {}
    for held_out in names:
        fold = [n for n in names if n != held_out]
        result = refit.fit_all(fold)
        directory = root / held_out
        fit.write_candidate(
            directory, result, note=f"LOCO fold: fitted without {held_out}."
        )
        configs[held_out] = directory
    return configs


def oos_ratings(configs: dict[str, Path]) -> pd.DataFrame:
    """Rate every career with the config that was fitted without it.

    Returns:
        One row per performance with the key columns and ``rating_oos``.
    """
    parts = [
        rating.rated_performances(
            names=[career], config_dir=directory, column="rating_oos"
        )[[*_KEYS, "rating_oos"]]
        for career, directory in configs.items()
    ]
    return pd.concat(parts, ignore_index=True)
