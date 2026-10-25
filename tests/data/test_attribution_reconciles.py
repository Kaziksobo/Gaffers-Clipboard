"""Check the attribution report itemises exactly what the rating service computes."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest
from workshop.lib import datasets, rating

_LIB_PATH = (
    Path(__file__).resolve().parents[2]
    / "workshop"
    / "ratings_creation"
    / "attribution_lib.py"
)

# Components every performance in that position must log (whether or not they fire).
_REQUIRED = {
    "CB": {"Goal bonus", "Assist bonus", "Defensive quality bonus (CB)", "Clean sheet"},
    "CDM": {
        "Defensive quality bonus (CDM)",
        "CDM Reliable Pivot",
        "Clean sheet",
        "Collapse penalty",
    },
    "RB": {"Fullback style bonus", "Clean sheet", "Collapse penalty"},
    "LB": {"Fullback style bonus", "Clean sheet", "Collapse penalty"},
    "CM": {"CM style bonus", "Clean sheet"},
    "ST": {
        "ST Hold-Up bonus",
        "ST Black Hole penalty",
        "ST Wasteful Finisher penalty",
    },
    "RW": {"Wasted-shots penalty"},
    "LW": {"Wasted-shots penalty"},
}


@pytest.fixture(scope="module")
def lib() -> Any:  # noqa: ANN401
    """Load attribution_lib.py (it lives outside any package)."""
    spec = importlib.util.spec_from_file_location("attribution_lib", _LIB_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def service() -> Any:  # noqa: ANN401
    """Return the live rating service."""
    return rating.load_service()


def _outfield(career_names: tuple[str, ...], max_matches: int | None = None):
    for name in career_names:
        career = datasets.load_career(name)
        for match in career.matches[:max_matches]:
            for performance in match["player_performances"]:
                if performance["performance_type"] == "Outfield":
                    yield career, match, performance


def _attribute(
    lib: Any,  # noqa: ANN401
    service: Any,  # noqa: ANN401
    career: Any,  # noqa: ANN401
    data: dict,
    performance: dict,
) -> tuple[Any, float | None, dict]:
    return lib.run_attribution(
        service.weights,
        service.means_stds,
        data,
        performance,
        career.club,
        data["half_length"],
    )


def _check_reconciles(svc: Any, final: float | None, blend: dict) -> int:  # noqa: ANN401
    checked = 0
    for pos in svc.position_order:
        snap = svc.position_snapshots[pos]
        itemised = sum(c["value"] for c in snap["components"])
        assert itemised == pytest.approx(snap["total_bonus"], abs=1e-9), pos
        raw_final = (
            snap["pre_modifier"]["base_rating"]
            + snap["total_bonus"]
            - snap["adjusted_supremacy"]
        )
        assert snap["position_final_rating"] == pytest.approx(
            max(0.0, min(10.0, raw_final)), abs=1e-9
        )
        checked += 1
    if blend:
        assert blend["final_rating"] == final
    return checked


def test_every_real_performance_reconciles_to_the_service(
    lib: Any,  # noqa: ANN401
    service: Any,  # noqa: ANN401
) -> None:
    """Itemised bonuses sum to the service total and the final rating matches."""
    positions = 0
    for career, match, performance in _outfield(
        ("valencia_cf_1", "arsenal_2", "ipswich_3")
    ):
        svc, final, blend = _attribute(lib, service, career, match["data"], performance)
        expected = rating.rate_performance(
            service, career.club, match["data"], performance
        )
        assert final == expected
        positions += _check_reconciles(svc, final, blend)
    assert positions > 3000


@pytest.mark.parametrize("goals_against", range(6))
def test_conceding_scenarios_reconcile(
    lib: Any,  # noqa: ANN401
    service: Any,  # noqa: ANN401
    goals_against: int,
) -> None:
    """The collapse, clean-sheet and retention branches reconcile too."""
    checked = 0
    for career, match, performance in _outfield(("arsenal_2", "ipswich_3"), 8):
        data = copy.deepcopy(match["data"])
        home = data["home_team_name"] == career.club
        data["away_score" if home else "home_score"] = goals_against
        svc, final, blend = _attribute(lib, service, career, data, performance)
        assert final == rating.rate_performance(service, career.club, data, performance)
        checked += _check_reconciles(svc, final, blend)
    assert checked > 150


def test_every_position_logs_its_expected_components(
    lib: Any,  # noqa: ANN401
    service: Any,  # noqa: ANN401
) -> None:
    """A component that is never logged would silently drop out of the report."""
    seen: dict[str, set[str]] = {}
    for career, match, performance in _outfield(("valencia_cf_1",), 40):
        svc, _, _ = _attribute(lib, service, career, match["data"], performance)
        for pos in svc.position_order:
            labels = {c["label"] for c in svc.position_snapshots[pos]["components"]}
            seen.setdefault(pos, labels)
            assert seen[pos] == labels, pos
    for pos, required in _REQUIRED.items():
        if pos in seen:
            assert required <= seen[pos], (pos, required - seen[pos])


def test_reports_carry_no_unattributed_or_mismatch_flags(
    lib: Any,  # noqa: ANN401
    service: Any,  # noqa: ANN401
) -> None:
    """Built reports show every check as OK across a spread of performances."""
    per_position: dict[str, int] = {}
    built = 0
    for career, match, performance in _outfield(
        ("valencia_cf_1", "arsenal_2", "ipswich_3")
    ):
        key = "+".join(performance.get("positions_played", []))
        if per_position.get(key, 0) >= 6:
            continue
        per_position[key] = per_position.get(key, 0) + 1
        data = match["data"]
        svc, final, blend = _attribute(lib, service, career, data, performance)
        if final is None:
            continue
        text = lib.build_full_report(
            svc, data, career.club, performance, data["half_length"], final, blend
        )
        assert "UNATTRIBUTED" not in text
        assert "MISMATCH" not in text
        assert "Service total bonus" in text
        built += 1
    assert built > 40
