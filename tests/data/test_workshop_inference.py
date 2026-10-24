"""Check the fast bootstrap helpers against scipy and against their own invariants."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats
from workshop.lib import inference

_RESAMPLES = 800


@pytest.fixture(scope="module")
def correlated() -> tuple[np.ndarray, np.ndarray]:
    """Return 300 noisy, tied (integer-valued) correlated pairs."""
    rng = np.random.default_rng(0)
    x = rng.integers(0, 12, size=300).astype(float)
    y = np.round(0.6 * x + rng.normal(0, 2.5, size=300))
    return x, y


def test_spearman_matches_scipy_including_ties(
    correlated: tuple[np.ndarray, np.ndarray],
) -> None:
    """The NumPy implementation agrees with scipy on tied data."""
    x, y = correlated
    assert inference.spearman(x, y) == pytest.approx(
        stats.spearmanr(x, y)[0], abs=1e-12
    )


def test_weighted_correlation_equals_spearman_of_the_expanded_data() -> None:
    """A resample's weights act exactly like repeating each row that many times."""
    rng = np.random.default_rng(2)
    x = rng.integers(0, 8, 50).astype(float)
    y = rng.integers(0, 8, 50).astype(float)
    weights = rng.integers(0, 4, size=(6, 50)).astype(float)

    sx, sy = inference._rank_setup(x), inference._rank_setup(y)
    got = inference._weighted_pearson(
        inference._weighted_ranks(sx, weights),
        inference._weighted_ranks(sy, weights),
        weights,
    )
    for row, w in enumerate(weights.astype(int)):
        want = stats.spearmanr(np.repeat(x, w), np.repeat(y, w))[0]
        assert got[row] == pytest.approx(want, abs=1e-12)


def test_constant_input_gives_nan() -> None:
    """A constant variable has no rank correlation."""
    assert np.isnan(inference.spearman(np.ones(10), np.arange(10.0)))


def test_bootstrap_is_reproducible_and_brackets_the_estimate(
    correlated: tuple[np.ndarray, np.ndarray],
) -> None:
    """Same seed, same answer; the interval contains the point estimate."""
    x, y = correlated
    a = inference.bootstrap_spearman(x, y, n_resamples=_RESAMPLES, seed=7)
    b = inference.bootstrap_spearman(x, y, n_resamples=_RESAMPLES, seed=7)
    assert a == b
    assert a.ci_low < a.estimate < a.ci_high
    assert a.se > 0


def test_p_value_follows_the_strength_of_the_relationship() -> None:
    """A perfect monotone relationship gives p = 0; independence gives a middling p."""
    x = np.arange(60.0)
    strong = inference.bootstrap_spearman(x, x**2, n_resamples=_RESAMPLES)
    assert strong.estimate == pytest.approx(1.0)
    assert strong.p_one_tailed == 0.0

    rng = np.random.default_rng(1)
    null = inference.bootstrap_spearman(
        rng.normal(size=200), rng.normal(size=200), n_resamples=_RESAMPLES
    )
    assert 0.05 < null.p_one_tailed < 0.95


def test_cluster_bootstrap_with_singleton_clusters_matches_the_row_bootstrap(
    correlated: tuple[np.ndarray, np.ndarray],
) -> None:
    """When every row is its own cluster the two schemes agree closely."""
    x, y = correlated
    rows = inference.bootstrap_spearman(x, y, n_resamples=2000)
    clusters = inference.cluster_bootstrap_spearman(
        x, y, np.arange(len(x)), n_resamples=2000
    )
    assert clusters.estimate == pytest.approx(rows.estimate)
    assert clusters.ci_low == pytest.approx(rows.ci_low, abs=0.04)
    assert clusters.ci_high == pytest.approx(rows.ci_high, abs=0.04)


def test_clustering_widens_the_interval_when_rows_within_a_cluster_agree() -> None:
    """A shared cluster-level signal widens the interval versus independent rows."""
    rng = np.random.default_rng(3)
    cluster_signal = rng.normal(size=40)
    clusters = np.repeat(np.arange(40), 15)
    x = np.repeat(cluster_signal, 15) + rng.normal(0, 0.3, size=600)
    y = np.repeat(cluster_signal, 15) * 0.5 + rng.normal(0, 1.0, size=600)

    naive = inference.bootstrap_spearman(x, y, n_resamples=1000)
    clustered = inference.cluster_bootstrap_spearman(x, y, clusters, n_resamples=1000)
    assert (clustered.ci_high - clustered.ci_low) > (naive.ci_high - naive.ci_low)


def test_cluster_labels_are_taken_as_given() -> None:
    """String labels work, which is how 'career:match_id' keys are passed."""
    rng = np.random.default_rng(5)
    x, y = rng.normal(size=60), rng.normal(size=60)
    labels = np.array([f"a:{i // 3}" for i in range(60)])
    result = inference.cluster_bootstrap_spearman(x, y, labels, n_resamples=200)
    assert np.isfinite(result.estimate)


def test_paired_delta_is_zero_when_both_ratings_are_identical(
    correlated: tuple[np.ndarray, np.ndarray],
) -> None:
    """Comparing a rating with itself gives no difference at all."""
    x, y = correlated
    result = inference.paired_delta_rho(x, x.copy(), y, n_resamples=_RESAMPLES)
    assert result.estimate == 0.0
    assert result.ci_low == 0.0
    assert result.ci_high == 0.0


def test_paired_delta_detects_a_better_alternative() -> None:
    """An alternative closer to the criterion shows a positive difference."""
    rng = np.random.default_rng(11)
    criterion = rng.normal(size=150)
    weak = criterion + rng.normal(0, 2.0, size=150)
    strong = criterion + rng.normal(0, 0.3, size=150)
    result = inference.paired_delta_rho(weak, strong, criterion, n_resamples=_RESAMPLES)
    assert result.estimate > 0.3
    assert result.ci_low > 0


def test_mean_gap_bootstrap_detects_a_real_gap_and_a_null_one() -> None:
    """A clear difference excludes zero; two draws from one distribution do not."""
    rng = np.random.default_rng(21)
    high = rng.normal(1.0, 1.0, size=200)
    low = rng.normal(0.0, 1.0, size=200)
    gap = inference.mean_gap_bootstrap(high, low, n_resamples=_RESAMPLES)
    assert gap.estimate == pytest.approx(high.mean() - low.mean())
    assert gap.ci_low > 0
    assert gap.p_one_tailed == 0.0

    same = inference.mean_gap_bootstrap(
        rng.normal(size=200), rng.normal(size=200), n_resamples=_RESAMPLES
    )
    assert same.ci_low < 0 < same.ci_high


def test_cluster_paired_delta_zero_when_identical_positive_when_better() -> None:
    """Identical ratings differ by zero; a rating nearer the criterion scores higher."""
    rng = np.random.default_rng(31)
    clusters = np.repeat(np.arange(60), 10)
    criterion = np.repeat(rng.normal(size=60), 10) + rng.normal(0, 0.5, size=600)
    weak = criterion + rng.normal(0, 2.0, size=600)
    strong = criterion + rng.normal(0, 0.4, size=600)

    same = inference.cluster_paired_delta_rho(
        weak, weak.copy(), criterion, clusters, n_resamples=_RESAMPLES
    )
    assert same.estimate == 0.0
    assert same.ci_low == 0.0
    assert same.ci_high == 0.0

    better = inference.cluster_paired_delta_rho(
        weak, strong, criterion, clusters, n_resamples=_RESAMPLES
    )
    assert better.estimate > 0.3
    assert better.ci_low > 0
