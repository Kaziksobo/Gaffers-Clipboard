"""Reliability helpers: additive input noise and the intraclass correlation ICC(A,1).

Reliability asks whether two performances that differ only by the kind of off-by-one ambiguity a
user can introduce (22 vs 23 passes from a slightly unclear screenshot) get the same rating.
``perturb`` generates such variants; ``icc_a1`` (McGraw and Wong's two-way random effects, absolute
agreement, single measure; Shrout and Fleiss's ICC2) measures how interchangeable the resulting
ratings are.

Interpretation bands (Koo and Li, 2016): below 0.5 poor, 0.5 to 0.75 moderate, 0.75 to 0.9 good,
above 0.9 excellent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from workshop.lib import inference

COUNT_STATS = (
    "passes", "dribbles", "tackles", "possession_won", "possession_lost",
    "fouls_committed", "offsides", "shots",
)  # fmt: skip
DISTANCE_STATS = ("distance_covered", "distance_sprinted")
GK_COUNT_STATS = ("saves", "shots_on_target", "shots_against")
COUNT_STEP = 1
DISTANCE_STEP = 0.1


def perturb(
    performance: Mapping[str, Any],
    rng: np.random.Generator,
    count_step: float = COUNT_STEP,
    distance_step: float = DISTANCE_STEP,
    count_stats: tuple[str, ...] = COUNT_STATS,
    distance_stats: tuple[str, ...] = DISTANCE_STATS,
) -> dict[str, Any]:
    """Return a copy with additive noise of ``-step, 0 or +step`` on the noisy stats.

    Counts move by ``count_step`` and distances by ``distance_step``; values never go below 0.
    Goals, assists, percentages and minutes are left alone, as is anything not present.
    Offsets are converted to plain Python numbers: the rating service treats NumPy integers
    as non-numeric and would silently zero them.
    """
    noisy = dict(performance)
    for stat in count_stats:
        if stat in noisy:
            offset = rng.choice((-count_step, 0, count_step)).item()
            noisy[stat] = max(0, noisy[stat] + offset)
    for stat in distance_stats:
        if stat in noisy:
            offset = rng.choice((-distance_step, 0.0, distance_step)).item()
            noisy[stat] = max(0.0, noisy[stat] + offset)
    return noisy


def icc_a1(ratings: np.ndarray) -> float:
    """ICC(A,1) for a targets x raters matrix (two-way random, absolute agreement, single)."""
    x = np.asarray(ratings, dtype=float)
    n, k = x.shape
    grand = x.mean()
    row_means, col_means = x.mean(axis=1), x.mean(axis=0)
    ms_rows = k * ((row_means - grand) ** 2).sum() / (n - 1)
    ms_cols = n * ((col_means - grand) ** 2).sum() / (k - 1)
    residual = x - row_means[:, None] - col_means[None, :] + grand
    ms_error = (residual**2).sum() / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    return float((ms_rows - ms_error) / denominator)


def bootstrap_icc_a1(
    ratings: np.ndarray, n_resamples: int = 1000, seed: int = inference.DEFAULT_SEED
) -> inference.Estimate:
    """ICC(A,1) with a percentile bootstrap over targets (rows)."""
    x = np.asarray(ratings, dtype=float)
    n = x.shape[0]
    rng = np.random.default_rng(seed)
    values = np.empty(n_resamples)
    for i in range(n_resamples):
        values[i] = icc_a1(x[rng.integers(0, n, size=n)])
    low, high = np.percentile(values, [2.5, 97.5])
    return inference.Estimate(
        estimate=icc_a1(x),
        ci_low=float(low),
        ci_high=float(high),
        se=float(values.std()),
        p_one_tailed=float("nan"),
    )


def band(icc: float) -> str:
    """Label an ICC with the Koo and Li interpretation band."""
    if icc < 0.5:
        return "poor"
    if icc < 0.75:
        return "moderate"
    return "good" if icc < 0.9 else "excellent"
