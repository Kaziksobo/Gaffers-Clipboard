"""Check the hold-out gate's verdicts on identical, broken and uncertain candidates."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from workshop.lib import fit, gate

_CONFIG = Path(__file__).resolve().parents[2] / "config"
_RESAMPLES = 500


@pytest.fixture
def reversed_weights_config(tmp_path: Path) -> Path:
    """Return a candidate config with reversed weight vectors (a worse rating)."""
    for name in (fit.WEIGHTS_FILE, fit.MEANS_STDS_FILE):
        shutil.copy(_CONFIG / name, tmp_path / name)
    path = tmp_path / fit.WEIGHTS_FILE
    weights = json.loads(path.read_text("utf-8"))
    for section, stats in weights.items():
        weights[section] = dict(zip(stats, list(stats.values())[::-1], strict=True))
    path.write_text(json.dumps(weights, indent=4), "utf-8")
    return tmp_path


def test_identical_configs_pass_with_zero_difference() -> None:
    """Comparing a config with itself differs by exactly zero and passes."""
    result = gate.evaluate(["ipswich_3"], _CONFIG, _CONFIG, n_resamples=_RESAMPLES)
    assert result.passes
    frame = result.to_frame()
    assert (frame["delta"] == 0).all()
    assert (frame["ci_low"] == 0).all()
    assert (frame["ci_high"] == 0).all()


def test_the_gate_has_two_gated_metrics_and_one_secondary() -> None:
    """Team-level and player-level rho are gated; the xG metric is only reported."""
    result = gate.evaluate(["ipswich_3"], _CONFIG, _CONFIG, n_resamples=_RESAMPLES)
    frame = result.to_frame()
    assert list(frame["gated"]) == [True, True, False]
    assert frame.loc[~frame["gated"], "passes"].isna().all()
    assert result.margin == gate.NON_INFERIORITY_MARGIN == 0.05


def test_a_clearly_worse_candidate_fails(reversed_weights_config: Path) -> None:
    """A candidate that ranks performances worse is rejected on both gated metrics."""
    result = gate.evaluate(
        ["ipswich_3"], _CONFIG, reversed_weights_config, n_resamples=_RESAMPLES
    )
    gated = result.to_frame().query("gated")
    assert not result.passes
    assert (gated["delta"] < 0).all()
    assert not gated["passes"].any()


def test_non_inferiority_looks_only_at_the_interval_lower_bound() -> None:
    """A wide interval reaching below -margin fails, whatever the point estimate."""
    assert gate.non_inferior(-0.04)
    assert gate.non_inferior(0.0)
    assert not gate.non_inferior(-0.06)
    assert not gate.non_inferior(-0.05)  # the bound must be strictly inside the margin
    assert gate.non_inferior(-0.09, margin=0.10)
