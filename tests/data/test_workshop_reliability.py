"""Check the ICC and noise helpers used by the reliability notebook."""

from __future__ import annotations

import numpy as np
import pytest
from workshop.lib import datasets, rating, reliability


def test_icc_is_one_for_identical_raters() -> None:
    """Raters that agree exactly on varied targets give ICC 1."""
    rng = np.random.default_rng(0)
    column = rng.normal(size=50)
    assert reliability.icc_a1(np.tile(column[:, None], (1, 4))) == pytest.approx(1.0)


def test_icc_is_near_zero_for_unrelated_raters() -> None:
    """Independent noise columns give an ICC close to zero."""
    rng = np.random.default_rng(1)
    assert abs(reliability.icc_a1(rng.normal(size=(400, 5)))) < 0.1


def test_icc_penalises_a_rater_offset_that_correlation_would_ignore() -> None:
    """Absolute agreement drops when a rater is shifted, though ranks agree."""
    rng = np.random.default_rng(2)
    base = rng.normal(size=(200, 1))
    aligned = np.hstack([base, base + 0.01 * rng.normal(size=(200, 1))])
    shifted = np.hstack([base, base + 2.0])
    assert reliability.icc_a1(aligned) > 0.99
    assert reliability.icc_a1(shifted) < reliability.icc_a1(aligned) - 0.2


def test_icc_matches_pingouin_when_available() -> None:
    """ICC(A,1) agrees with pingouin on a random matrix."""
    pingouin = pytest.importorskip("pingouin")
    import pandas as pd

    rng = np.random.default_rng(3)
    x = rng.normal(size=(60, 4)) + rng.normal(size=(60, 1))
    long = pd.DataFrame(
        {
            "target": np.repeat(np.arange(60), 4),
            "rater": np.tile(np.arange(4), 60),
            "score": x.ravel(),
        }
    )
    table = pingouin.intraclass_corr(long, "target", "rater", "score")
    expected = float(table.set_index("Type").loc["ICC(A,1)", "ICC"])
    assert reliability.icc_a1(x) == pytest.approx(expected, abs=1e-9)


def test_bootstrap_interval_contains_the_estimate() -> None:
    """The percentile interval brackets the point estimate and is reproducible."""
    rng = np.random.default_rng(4)
    x = rng.normal(size=(150, 1)) + 0.3 * rng.normal(size=(150, 6))
    a = reliability.bootstrap_icc_a1(x, n_resamples=200, seed=5)
    b = reliability.bootstrap_icc_a1(x, n_resamples=200, seed=5)
    assert a == b or (a.estimate == b.estimate and a.ci_low == b.ci_low)
    assert a.ci_low <= a.estimate <= a.ci_high


def test_perturb_only_touches_the_noisy_stats_and_stays_non_negative() -> None:
    """Counts move by at most one, distances by 0.1; others are unchanged."""
    rng = np.random.default_rng(6)
    performance = {
        "passes": 20, "tackles": 0, "shots": 2, "distance_covered": 9.0,
        "distance_sprinted": 0.05, "goals": 1, "pass_accuracy": 85,
        "minutes_played": 90,
    }  # fmt: skip
    for _ in range(200):
        noisy = reliability.perturb(performance, rng)
        assert noisy["goals"] == 1
        assert noisy["pass_accuracy"] == 85
        assert noisy["minutes_played"] == 90
        assert abs(noisy["passes"] - 20) <= 1
        assert noisy["tackles"] in (0, 1)
        assert abs(noisy["distance_covered"] - 9.0) <= 0.1 + 1e-9
        assert noisy["distance_sprinted"] >= 0
    assert performance["passes"] == 20  # the original is not mutated


def test_bands_follow_koo_and_li() -> None:
    """The interpretation bands sit at 0.5, 0.75 and 0.9."""
    assert [reliability.band(v) for v in (0.2, 0.6, 0.8, 0.95)] == [
        "poor",
        "moderate",
        "good",
        "excellent",
    ]


def test_zero_noise_leaves_real_ratings_unchanged_and_types_plain() -> None:
    """A step of 0 is a no-op through the real service; values stay Python numbers."""
    service = rating.load_service()
    career = datasets.load_career("ipswich_3")
    rng = np.random.default_rng(7)
    checked = 0
    for match in career.matches[:8]:
        for performance in match["player_performances"]:
            if performance["performance_type"] != "Outfield":
                continue
            noisy = reliability.perturb(performance, rng, 0, 0.0)
            for stat in reliability.COUNT_STATS:
                assert type(noisy[stat]) is type(performance[stat])
            before = rating.rate_performance(
                service, career.club, match["data"], performance
            )
            after = rating.rate_performance(service, career.club, match["data"], noisy)
            assert before == after
            checked += 1
    assert checked > 50
