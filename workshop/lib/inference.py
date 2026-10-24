"""Fast bootstrap inference for Spearman correlations.

Bootstrap resamples are represented as integer *weights* on the original rows (how many
times each row, or each row's cluster, was drawn). The Spearman correlation of a
resample is then a weighted Pearson correlation of weighted average ranks, which
vectorises across thousands of resamples with a handful of NumPy operations. A resample
with weights ``w`` gives exactly the Spearman correlation of the data expanded
``w`` times.

Conventions kept from the original notebook so results stay comparable:

- percentile confidence intervals (2.5th and 97.5th percentiles);
- the one-tailed bootstrap p-value is the share of resamples with a statistic <= 0
  (H1: statistic > 0), so the smallest reportable value is 0, not 1 / resamples;
- the standard error is the standard deviation of the resampled statistics.

Resampling draws multinomial counts from ``numpy.random.default_rng(seed)``, so
intervals agree statistically with earlier runs but not to the last decimal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

DEFAULT_RESAMPLES = 5000
DEFAULT_SEED = 42
_CHUNK = 500  # resamples per vectorised block, to bound memory


@dataclass(frozen=True)
class Estimate:
    """A point estimate with its bootstrap summary."""

    estimate: float
    ci_low: float
    ci_high: float
    se: float
    p_one_tailed: float


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation (average ranks for ties), NaN if either is constant."""
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    rx, ry = rx - rx.mean(), ry - ry.mean()
    denom = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    with np.errstate(invalid="ignore", divide="ignore"):
        return float((rx * ry).sum() / denom)


def _rank_setup(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Precompute the sort order and tie groups needed for weighted ranking."""
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    starts = np.flatnonzero(np.r_[True, ordered[1:] != ordered[:-1]])
    sizes = np.diff(np.r_[starts, len(values)])
    return order, starts, sizes


def _weighted_ranks(
    setup: tuple[np.ndarray, np.ndarray, np.ndarray], weights: np.ndarray
) -> np.ndarray:
    """Average ranks of every row under each weight vector (rows are resamples)."""
    order, starts, sizes = setup
    group_weight = np.add.reduceat(weights[:, order], starts, axis=1)
    # A tie group holding total weight G above cumulative weight C spans ranks
    # C-G+1 .. C, whose average is C - (G - 1) / 2.
    group_rank = np.cumsum(group_weight, axis=1) - (group_weight - 1.0) / 2.0
    ranks = np.empty_like(weights)
    ranks[:, order] = np.repeat(group_rank, sizes, axis=1)
    return ranks


def _weighted_pearson(rx: np.ndarray, ry: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted Pearson correlation per resample (row)."""
    total = w.sum(axis=1, keepdims=True)
    dx = rx - (w * rx).sum(axis=1, keepdims=True) / total
    dy = ry - (w * ry).sum(axis=1, keepdims=True) / total
    with np.errstate(invalid="ignore", divide="ignore"):
        return (w * dx * dy).sum(axis=1) / np.sqrt(
            (w * dx * dx).sum(axis=1) * (w * dy * dy).sum(axis=1)
        )


def _summarise(point: float, boot: np.ndarray) -> Estimate:
    finite = boot[np.isfinite(boot)]
    low, high = np.percentile(finite, [2.5, 97.5])
    return Estimate(
        estimate=point,
        ci_low=float(low),
        ci_high=float(high),
        se=float(finite.std()),
        p_one_tailed=float(np.mean(finite <= 0)),
    )


def _bootstrap(
    statistic: Callable[[np.ndarray], np.ndarray],
    codes: np.ndarray,
    n_resamples: int,
    seed: int,
) -> np.ndarray:
    """Evaluate ``statistic(weights)`` over cluster-resampling blocks.

    ``codes[i]`` is the cluster (0..k-1) of row ``i``; each resample draws k clusters
    with replacement and the weights are the resulting per-row draw counts.
    """
    n_units = int(codes.max()) + 1
    rng = np.random.default_rng(seed)
    pvals = np.full(n_units, 1.0 / n_units)
    out = np.empty(n_resamples)
    for start in range(0, n_resamples, _CHUNK):
        stop = min(start + _CHUNK, n_resamples)
        counts = rng.multinomial(n_units, pvals, size=stop - start)
        out[start:stop] = statistic(counts[:, codes].astype(float))
    return out


def _clean(*arrays: np.ndarray | pd.Series) -> list[np.ndarray]:
    return [np.asarray(a, dtype=float) for a in arrays]


def bootstrap_spearman(
    x: np.ndarray,
    y: np.ndarray,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Estimate:
    """Spearman correlation with a paired (row) percentile bootstrap."""
    x, y = _clean(x, y)
    sx, sy = _rank_setup(x), _rank_setup(y)

    def statistic(w: np.ndarray) -> np.ndarray:
        return _weighted_pearson(_weighted_ranks(sx, w), _weighted_ranks(sy, w), w)

    boot = _bootstrap(statistic, np.arange(len(x)), n_resamples, seed)
    return _summarise(spearman(x, y), boot)


def cluster_bootstrap_spearman(
    x: np.ndarray,
    y: np.ndarray,
    clusters: np.ndarray | pd.Series,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Estimate:
    """Spearman correlation with a bootstrap that resamples whole clusters.

    Rows sharing a cluster (for example players in the same match, who share one
    scoreline) are drawn together, so the intervals respect that dependence. Cluster
    labels must be unique per cluster across the data: use ``"career:match_id"``,
    since match ids restart at 1 in every career.
    """
    x, y = _clean(x, y)
    codes, _ = pd.factorize(np.asarray(clusters))
    sx, sy = _rank_setup(x), _rank_setup(y)

    def statistic(w: np.ndarray) -> np.ndarray:
        return _weighted_pearson(_weighted_ranks(sx, w), _weighted_ranks(sy, w), w)

    boot = _bootstrap(statistic, codes, n_resamples, seed)
    return _summarise(spearman(x, y), boot)


def paired_delta_rho(
    baseline: np.ndarray,
    alternative: np.ndarray,
    criterion: np.ndarray,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Estimate:
    """Bootstrap of ``rho(alternative, criterion) - rho(baseline, criterion)``.

    Both correlations come from the same resampled rows, so the interval reflects the
    difference itself rather than two separate intervals compared by eye.
    """
    base, alt, crit = _clean(baseline, alternative, criterion)
    sb, sa, sc = _rank_setup(base), _rank_setup(alt), _rank_setup(crit)

    def statistic(w: np.ndarray) -> np.ndarray:
        rc = _weighted_ranks(sc, w)
        return _weighted_pearson(_weighted_ranks(sa, w), rc, w) - _weighted_pearson(
            _weighted_ranks(sb, w), rc, w
        )

    boot = _bootstrap(statistic, np.arange(len(crit)), n_resamples, seed)
    return _summarise(spearman(alt, crit) - spearman(base, crit), boot)

def mean_gap_bootstrap(
    a: np.ndarray,
    b: np.ndarray,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Estimate:
    """Bootstrap of ``mean(a) - mean(b)``, resampling each group independently.

    The one-tailed p-value is the share of resamples with a gap <= 0 (H1: a > b).
    """
    a, b = _clean(a, b)
    rng = np.random.default_rng(seed)
    boot = np.empty(n_resamples)
    for start in range(0, n_resamples, _CHUNK):
        stop = min(start + _CHUNK, n_resamples)
        size = stop - start
        mean_a = a[rng.integers(0, len(a), size=(size, len(a)))].mean(axis=1)
        mean_b = b[rng.integers(0, len(b), size=(size, len(b)))].mean(axis=1)
        boot[start:stop] = mean_a - mean_b
    return _summarise(float(a.mean() - b.mean()), boot)

def cluster_paired_delta_rho(
    baseline: np.ndarray,
    alternative: np.ndarray,
    criterion: np.ndarray,
    clusters: np.ndarray | pd.Series,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Estimate:
    """Cluster bootstrap of ``rho(alternative, criterion) - rho(baseline, criterion)``.

    Whole clusters (for example matches) are resampled together, and both correlations
    are computed from the same resample, so the interval reflects the difference itself
    while respecting that rows in a cluster are not independent.
    """
    base, alt, crit = _clean(baseline, alternative, criterion)
    codes, _ = pd.factorize(np.asarray(clusters))
    sb, sa, sc = _rank_setup(base), _rank_setup(alt), _rank_setup(crit)

    def statistic(w: np.ndarray) -> np.ndarray:
        rc = _weighted_ranks(sc, w)
        return _weighted_pearson(_weighted_ranks(sa, w), rc, w) - _weighted_pearson(
            _weighted_ranks(sb, w), rc, w
        )

    boot = _bootstrap(statistic, codes, n_resamples, seed)
    return _summarise(spearman(alt, crit) - spearman(base, crit), boot)
