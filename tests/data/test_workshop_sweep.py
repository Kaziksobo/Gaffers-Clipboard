"""Check the workshop parameter-sweep helpers (variants, comparison, tornado)."""

from __future__ import annotations

from types import MappingProxyType

import numpy as np
import pytest
from workshop.lib import sweep

from src.services.analytics.match_ratings_service import MatchRatingsService

_SMALL_CAREER = ["ipswich_3"]


def _class_constants() -> dict[str, object]:
    return {
        k: dict(v) if isinstance(v, MappingProxyType) else v
        for k, v in vars(MatchRatingsService).items()
        if k.isupper()
    }


@pytest.fixture(scope="module")
def small_pool() -> sweep.Pool:
    """Return the smallest career as a pool, rated once."""
    return sweep.load_pool(names=_SMALL_CAREER)


def test_tunable_constants_exclude_structural_and_non_numeric() -> None:
    """Only numeric, non-structural class constants are swept."""
    names = set(sweep.tunable_constants())
    assert {"GOAL_BONUS_CAP", "GOAL_ALPHA", "CS_RATIOS", "Z_SCORE_FLOORS"} <= names
    assert not names & {"H_BASE", "MIRROR_PAIRS"}
    assert len(names) >= 35


def test_scale_value_handles_scalars_and_nested_mappings() -> None:
    """Scaling multiplies every number and leaves the input untouched."""
    nested = MappingProxyType({"CB": MappingProxyType({"a": -0.5, "b": 0.0}), "ST": 2})
    scaled = sweep.scale_value(nested, 1.2)
    assert scaled["CB"]["a"] == pytest.approx(-0.6)
    assert scaled["CB"]["b"] == 0.0
    assert scaled["ST"] == pytest.approx(2.4)
    assert nested["ST"] == 2
    assert sweep.scale_value(10, 0.8) == pytest.approx(8.0)


def test_scale_key_changes_only_that_key() -> None:
    """Scaling one key leaves the rest of the mapping alone."""
    scaled = sweep.scale_key(MappingProxyType({"ST": 0.3, "CB": 0.15}), "ST", 2.0)
    assert scaled == {"ST": pytest.approx(0.6), "CB": 0.15}


def test_identity_variant_reproduces_the_baseline(small_pool: sweep.Pool) -> None:
    """A variant that scales a constant by 1.0 rates exactly like the live service."""
    constant = sweep.tunable_constants()["GOAL_BONUS_CAP"]
    service = sweep.make_variant({"GOAL_BONUS_CAP": sweep.scale_value(constant, 1.0)})
    rated = sweep.rate_pool(small_pool.records, service)
    assert np.array_equal(rated, small_pool.baseline, equal_nan=True)


def test_variants_never_modify_the_service_class(small_pool: sweep.Pool) -> None:
    """Running variants leaves MatchRatingsService's own constants unchanged."""
    before = _class_constants()
    constants = sweep.tunable_constants()
    service = sweep.make_variant(
        {"GOAL_ALPHA": sweep.scale_value(constants["GOAL_ALPHA"], 3)}
    )
    sweep.rate_pool(small_pool.records, service)
    assert _class_constants() == before


def test_an_override_changes_ratings_in_the_expected_direction(
    small_pool: sweep.Pool,
) -> None:
    """Tripling the goal alphas never lowers a rating and raises some."""
    alpha = sweep.tunable_constants()["GOAL_ALPHA"]
    service = sweep.make_variant({"GOAL_ALPHA": sweep.scale_value(alpha, 3)})
    rated = sweep.rate_pool(small_pool.records, service)
    ok = np.isfinite(rated) & np.isfinite(small_pool.baseline)
    diff = rated[ok] - small_pool.baseline[ok]
    assert (diff >= -1e-9).all()
    assert (diff > 0).any()


def test_compare_identical_ratings_report_no_change() -> None:
    """Identical arrays show no movement and perfect rank agreement (NaNs ignored)."""
    ratings = np.array([6.0, 7.5, np.nan, 5.0])
    metrics = sweep.compare(ratings, ratings.copy())
    assert metrics["mean_abs_change"] == 0.0
    assert metrics["rank_corr"] == pytest.approx(1.0)
    assert metrics["share_changed"] == 0.0


def test_tornado_returns_one_row_per_direction_and_a_sorted_summary(
    small_pool: sweep.Pool,
) -> None:
    """Each constant gets a down and an up run, and the summary is sorted by effect."""
    result = sweep.tornado(small_pool, constants=["GOAL_BONUS_CAP", "GOAL_ALPHA"])
    assert len(result) == 4
    assert set(result["direction"]) == {"down", "up"}
    summary = sweep.summarise(result)
    assert list(summary.index) == ["GOAL_ALPHA", "GOAL_BONUS_CAP"] or list(
        summary.index
    ) == ["GOAL_BONUS_CAP", "GOAL_ALPHA"]
    assert summary["effect"].is_monotonic_decreasing


def test_split_sweeps_a_mapping_one_key_at_a_time(small_pool: sweep.Pool) -> None:
    """Splitting a mapping yields one labelled row pair per key."""
    result = sweep.tornado(small_pool, constants=["GOAL_ALPHA"], split=["GOAL_ALPHA"])
    labels = set(sweep.summarise(result).index)
    assert "GOAL_ALPHA[ST]" in labels
    assert len(labels) == len(sweep.tunable_constants()["GOAL_ALPHA"])
