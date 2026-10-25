"""Check the pure position fit reproduces the live config and behaves as a function."""

from __future__ import annotations

import copy
import json
import math
import warnings
from pathlib import Path

import pytest
from workshop.lib import datasets, fit, rating

_CONFIG = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="module")
def live() -> tuple[dict, dict]:
    """Return the live weights and means/stds."""
    return (
        json.loads((_CONFIG / fit.WEIGHTS_FILE).read_text("utf-8")),
        json.loads((_CONFIG / fit.MEANS_STDS_FILE).read_text("utf-8")),
    )


@pytest.fixture(scope="module")
def manifest() -> dict:
    """Return the live config's fit manifest."""
    return json.loads((_CONFIG / fit.MANIFEST_FILE).read_text("utf-8"))


@pytest.fixture(scope="module")
def reproduced(manifest: dict) -> fit.FitResult:
    """Refit on exactly what the manifest says the live config was fitted on."""
    recorded = {m["method"] for m in manifest["fitted_sections"].values()}
    assert recorded <= {"workshop/lib/fit.py", "workshop/lib/fit.py:fit_gk"}
    first = next(iter(manifest["fitted_sections"].values()))["sources"]
    ranges = {career: tuple(info["match_ids"]) for career, info in first.items()}
    policy = manifest["rare_event_policy"]
    direct = manifest.get("direct_fit_policy")
    return fit.fit_positions(
        fit.load_sources(ranges),
        rare_event_policy=fit.RareEventPolicy(**policy) if policy else None,
        derive_unknown=bool(manifest["derived_sections"]),
        include_gk="GK" in manifest["fitted_sections"],
        direct_fit_policy=fit.DirectFitPolicy(**direct) if direct else None,
    )


def test_manifest_hash_matches_the_live_config(manifest: dict) -> None:
    """Changing the config without updating its manifest fails here."""
    assert manifest["config_hash"] == fit.config_hash(_CONFIG)


def test_every_config_section_is_accounted_for(manifest: dict, live: tuple) -> None:
    """Each section is fitted, derived or legacy, and never more than one."""
    weights, means_stds = live
    all_fitted = set(manifest["fitted_sections"])
    fitted = all_fitted - {"GK"}  # GK has means/stds only, no weights
    derived = set(manifest["derived_sections"])
    legacy = manifest["legacy_sections"]
    assert fitted == {s for spec in fit.SPECS.values() for s in spec.sections}
    assert not fitted & derived
    assert fitted | derived | set(legacy[fit.WEIGHTS_FILE]) == set(weights)
    assert all_fitted | derived | set(legacy[fit.MEANS_STDS_FILE]) == set(means_stds)
    assert not (all_fitted | derived) & set(legacy[fit.MEANS_STDS_FILE])


def test_refit_reproduces_the_live_config_exactly(
    reproduced: fit.FitResult, live: tuple
) -> None:
    """Refitting the recorded sources and policy matches every section exactly."""
    weights, means_stds = live
    assert set(reproduced.weights) == set(reproduced.means_stds) - {"GK"}
    assert reproduced.weights
    for section in reproduced.weights:
        assert reproduced.weights[section] == weights[section], section
        assert reproduced.means_stds[section] == means_stds[section], section
    if "GK" in reproduced.means_stds:
        assert reproduced.means_stds["GK"] == means_stds["GK"]


def test_derived_sections_follow_from_the_fitted_ones(live: tuple) -> None:
    """Wing-back, wide-midfielder and CAM sections follow from their proxies."""
    weights, means_stds = live
    derived_weights, derived_means, proxies = fit.derive_sections(weights, means_stds)
    assert set(derived_weights) == {"RWB", "LWB", "RM", "LM", "CAM"}
    for section in derived_weights:
        assert derived_weights[section] == weights[section], section
        assert derived_means[section] == means_stds[section], section
        assert sum(derived_weights[section].values()) == pytest.approx(1.0, abs=1e-9)
    assert proxies["CAM"] == "CM"
    assert proxies["LM"] == "RW"
    assert proxies["RWB"] == "RB"


def test_config_covers_every_available_match(manifest: dict) -> None:
    """Warn (not fail) when datasets hold matches the live config was not fitted on."""
    first = next(iter(manifest["fitted_sections"].values()))["sources"]
    stale = []
    for career in datasets.career_names("pool"):
        available = len(datasets.load_career(career).matches)
        fitted = first.get(career, {}).get("n_matches", 0)
        if available > fitted:
            stale.append(f"{career}: {available} matches, config fitted on {fitted}")
    if stale:
        warnings.warn(
            "config is behind the datasets (run scripts/refit_config.py): "
            + "; ".join(stale),
            stacklevel=1,
        )


def test_fit_is_pure() -> None:
    """Fitting changes neither its input matches nor any config file."""
    sources = fit.load_sources({"ipswich_3": None})
    before_matches = copy.deepcopy(sources[0].matches)
    before_hash = fit.config_hash(_CONFIG)

    fit.fit_positions(sources, positions=["CB"])

    assert sources[0].matches == before_matches
    assert fit.config_hash(_CONFIG) == before_hash


def test_pooled_fit_is_well_formed() -> None:
    """Pooling careers gives finite weights summing to 1 and non-negative stds."""
    solo = fit.fit_positions(fit.load_sources({"valencia_cf_1": (1, 155)}))
    pooled = fit.fit_positions(
        fit.load_sources({"valencia_cf_1": (1, 155), "ipswich_3": None})
    )
    for name, rows in solo.rows.items():
        assert pooled.rows[name] > rows
    for section, section_weights in pooled.weights.items():
        assert list(section_weights) == fit.STAT_COLUMNS
        assert all(math.isfinite(w) for w in section_weights.values())
        assert sum(section_weights.values()) == pytest.approx(1.0, abs=1e-9)
        stds = [v["std"] for v in pooled.means_stds[section].values()]
        # A constant stat (no events) has std 0; the service maps it to z = 0.
        assert all(s >= 0 and math.isfinite(s) for s in stds)


def test_pooling_provenance_is_recorded() -> None:
    """The fit result says which careers and match ranges fed it."""
    ipswich = [m["id"] for m in datasets.load_career("ipswich_3").matches]
    result = fit.fit_positions(
        fit.load_sources({"valencia_cf_1": (1, 60), "ipswich_3": None}),
        positions=["CB"],
    )
    assert result.sources == {
        "valencia_cf_1": {"match_ids": [1, 60], "n_matches": 60},
        "ipswich_3": {
            "match_ids": [min(ipswich), max(ipswich)],
            "n_matches": len(ipswich),
        },
    }


def test_candidate_writer_keeps_unfitted_sections_and_is_loadable(
    tmp_path: Path, live: tuple
) -> None:
    """A candidate keeps unfitted sections, carries a manifest, and loads."""
    weights, means_stds = live
    result = fit.fit_positions(
        fit.load_sources({"valencia_cf_1": (1, 100)}), positions=["CB", "ST"]
    )
    manifest = fit.write_candidate(tmp_path, result, note="test")

    written_weights = json.loads((tmp_path / fit.WEIGHTS_FILE).read_text("utf-8"))
    written_means = json.loads((tmp_path / fit.MEANS_STDS_FILE).read_text("utf-8"))
    assert written_weights["CB"] == result.weights["CB"]
    assert written_means["ST"] == result.means_stds["ST"]
    for section in set(weights) - {"CB", "ST"}:
        assert written_weights[section] == weights[section]
    for section in set(means_stds) - {"CB", "ST"}:
        assert written_means[section] == means_stds[section]
    assert manifest["config_hash"] == fit.config_hash(tmp_path)
    assert set(manifest["fitted_sections"]) == {"CB", "ST"}
    assert "CAM" in manifest["legacy_sections"][fit.WEIGHTS_FILE]
    assert rating.load_service(tmp_path) is not None


def test_career_names_in_manifest_exist(manifest: dict) -> None:
    """Every career the manifest cites is a registered dataset."""
    cited = {
        career
        for entry in manifest["fitted_sections"].values()
        for career in entry["sources"]
    }
    assert cited <= set(datasets.career_names())


def test_rare_event_floor_relaxes_as_events_accumulate() -> None:
    """The floor is full up to 10 events, falls linearly, and is gone from 50."""
    policy = fit.RareEventPolicy()
    assert policy.floor_for(0) == policy.floor_for(10) == policy.floor
    assert policy.floor_for(30) == pytest.approx(policy.floor / 2)
    assert policy.floor_for(50) == 0.0
    assert policy.floor_for(500) == 0.0


def test_rare_event_policy_only_raises_stds_with_some_events() -> None:
    """No events stays inactive; a low std is floored; a high one is kept."""
    policy = fit.RareEventPolicy()
    assert policy.apply(0.0, 0) == 0.0
    assert policy.apply(0.05, 6) == policy.floor
    assert policy.apply(0.12, 6) == 0.12
    assert policy.apply(0.03, 60) == 0.03


def test_policy_touches_only_rare_stats_below_the_floor() -> None:
    """On all three careers only rare stats below the floor move."""
    sources = fit.load_sources(
        {"valencia_cf_1": None, "arsenal_2": None, "ipswich_3": None}
    )
    plain = fit.fit_positions(sources)
    floored = fit.fit_positions(sources, rare_event_policy=fit.RareEventPolicy())

    for section, stats in plain.means_stds.items():
        for stat, before in stats.items():
            after = floored.means_stds[section][stat]
            assert after["std"] >= before["std"]
            assert after["mean"] == before["mean"]
            if stat not in fit.RARE_EVENT_COLUMNS:
                assert after == before
    policy = fit.RareEventPolicy()
    for section, counts in floored.rare_events.items():
        for stat in ("goals_p90", "assists_p90"):
            events = counts[stat]
            before = plain.means_stds[section][stat]
            after = floored.means_stds[section][stat]
            assert after["std"] == pytest.approx(policy.apply(before["std"], events))
            if events == 0:  # no events: the stat stays inactive
                assert after == before
    assert floored.policy == {
        "floor": 0.08,
        "full_until_events": 10,
        "data_only_from_events": 50,
    }


def test_candidate_manifest_records_the_policy_and_event_counts(
    tmp_path: Path,
) -> None:
    """A candidate says which rare-event rule it was fitted under."""
    result = fit.fit_positions(
        fit.load_sources({"valencia_cf_1": (1, 100)}),
        positions=["CB"],
        rare_event_policy=fit.RareEventPolicy(),
    )
    manifest = fit.write_candidate(tmp_path, result)
    assert manifest["rare_event_policy"]["floor"] == 0.08
    assert manifest["fitted_sections"]["CB"]["rare_event_counts"]["goals_p90"] >= 0


def test_gk_fit_reproduces_the_legacy_goalkeeper_numbers_from_100_matches() -> None:
    """The legacy GK mean and std are the heuristic over Valencia's first 100."""
    got = fit.fit_gk(fit.load_sources({"valencia_cf_1": (1, 100)}))
    assert got == {"mean": 2.100523416647707, "std": 1.7031209589540022}


def test_gk_fit_uses_every_goalkeeper_row_of_every_career() -> None:
    """Pooling takes the heuristic over all goalkeeper rows, one per match."""
    ranges = {"valencia_cf_1": None, "arsenal_2": None, "ipswich_3": None}
    sources = fit.load_sources(ranges)
    got = fit.fit_gk(sources)
    assert math.isfinite(got["mean"])
    assert got["std"] > 0
    gk_rows = sum(
        p["performance_type"] == "GK"
        for s in sources
        for m in s.matches
        for p in m["player_performances"]
    )
    assert gk_rows == sum(len(s.matches) for s in sources)


def test_candidate_with_gk_lists_it_as_fitted(tmp_path: Path) -> None:
    """Including the goalkeeper fit makes GK a fitted section, not a legacy one."""
    result = fit.fit_positions(
        fit.load_sources({"valencia_cf_1": (1, 100)}), positions=["CB"], include_gk=True
    )
    manifest = fit.write_candidate(tmp_path, result)
    means = json.loads((tmp_path / fit.MEANS_STDS_FILE).read_text("utf-8"))
    assert manifest["fitted_sections"]["GK"]["method"].endswith("fit_gk")
    assert "GK" not in manifest["legacy_sections"][fit.MEANS_STDS_FILE]
    assert means["GK"] == result.means_stds["GK"]


def test_direct_fit_weight_ramps_from_min_to_full_rows() -> None:
    """No weight up to min_rows, full weight from full_rows, linear in between."""
    policy = fit.DirectFitPolicy(min_rows=85, full_rows=250)
    assert policy.alpha(0) == policy.alpha(85) == 0.0
    assert policy.alpha(250) == policy.alpha(1000) == 1.0
    assert policy.alpha(167.5) == pytest.approx(0.5)


@pytest.fixture(scope="module")
def all_sources() -> list[fit.FitSource]:
    """Every career, all matches."""
    return fit.load_sources(
        {"arsenal_2": None, "ipswich_3": None, "valencia_cf_1": None}
    )


def test_default_policy_leaves_derived_positions_derived_on_current_data(
    all_sources: list[fit.FitSource],
) -> None:
    """With under 85 rows each, wide midfielders, CAM and wing-backs stay derived."""
    plain = fit.fit_positions(all_sources, derive_unknown=True)
    blended = fit.fit_positions(
        all_sources, derive_unknown=True, direct_fit_policy=fit.DirectFitPolicy()
    )
    for section in ("RM", "LM", "CAM", "RWB", "LWB"):
        assert blended.weights[section] == plain.weights[section]
        assert blended.means_stds[section] == plain.means_stds[section]
        assert blended.direct[section]["weight"] == 0.0
    assert blended.direct["RWB"]["rows"] == 0


def test_direct_fit_takes_over_as_rows_pass_the_thresholds(
    all_sources: list[fit.FitSource],
) -> None:
    """A lowered threshold lets the wide-midfielder fit in fully and CAM in partly."""
    policy = fit.DirectFitPolicy(min_rows=20, full_rows=60)
    plain = fit.fit_positions(all_sources, derive_unknown=True)
    blended = fit.fit_positions(
        all_sources, derive_unknown=True, direct_fit_policy=policy
    )
    assert blended.direct["RM"]["weight"] == 1.0
    assert 0 < blended.direct["CAM"]["weight"] < 1
    assert blended.direct["RWB"] == {"rows": 0, "weight": 0.0}
    assert blended.weights["RWB"] == plain.weights["RWB"]

    frame = fit._performance_frame(all_sources)
    anchored, shares = fit.load_inputs()
    direct = fit.fit_position(
        frame, fit.DIRECT_SPECS["WideMidfielder"], anchored, shares
    )
    assert blended.weights["RM"] == direct.weights
    assert blended.means_stds["LM"] == direct.means_stds

    alpha = blended.direct["CAM"]["weight"]
    cam = fit.fit_position(frame, fit.DIRECT_SPECS["CAM"], anchored, shares)
    for stat, mixed in blended.weights["CAM"].items():
        expected = alpha * cam.weights[stat] + (1 - alpha) * plain.weights["CAM"][stat]
        assert mixed == pytest.approx(expected, abs=1e-12)
    for section in ("RM", "LM", "CAM"):
        assert sum(blended.weights[section].values()) == pytest.approx(1.0, abs=1e-9)


def test_candidate_manifest_records_direct_fit_weights(tmp_path: Path) -> None:
    """Derived sections say how much of their own fit they carry."""
    result = fit.fit_positions(
        fit.load_sources({"valencia_cf_1": None, "ipswich_3": None}),
        derive_unknown=True,
        direct_fit_policy=fit.DirectFitPolicy(min_rows=20, full_rows=60),
    )
    manifest = fit.write_candidate(tmp_path, result)
    assert manifest["direct_fit_policy"] == {"min_rows": 20, "full_rows": 60}
    assert 0.5 < manifest["derived_sections"]["RM"]["direct_fit"]["weight"] <= 1.0
    assert manifest["derived_sections"]["RWB"]["direct_fit"]["weight"] == 0.0


def test_xt_coefficients_match_the_services_position_scalars() -> None:
    """The fit must compute xT with the same coefficient the service applies."""
    from src.services.analytics.match_ratings_service import MatchRatingsService

    specs = [*fit.SPECS.values(), *fit.DIRECT_SPECS.values()]
    for spec in specs:
        for section in spec.sections:
            service_scalar = MatchRatingsService.XT_POSITION_SCALARS[section]
            assert spec.xt_coefficient == service_scalar, (spec.name, section)


def test_every_spec_has_a_positive_philosophy_for_every_block() -> None:
    """A missing or non-positive block would break (or silently zero) the fit."""
    for spec in [*fit.SPECS.values(), *fit.DIRECT_SPECS.values()]:
        assert set(spec.philosophy) == set(fit.BLOCKS), spec.name
        assert all(value > 0 for value in spec.philosophy.values()), spec.name
