"""Probe runtime types for JsonService methods used by DataManager.

This script executes the `load_json` call patterns currently used by the
application (as recorded in `scripts/reports/load_json_usages_report.json`)
against real JSON files under `data/`.

It captures runtime `type(...)` information for:
- `load_json`
- `_read_raw_json`
- `_validate_single_json`
- `_validate_list_json` (requested as `_validate_raw_json` in some notes)

Usage:
    uv run python scripts/probe_load_json_types.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.data_manager import DataManager
from src.schemas import CareerDetail, CareerMetadata, Match, Player
from src.services.data import JsonService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]


def type_name(value: object) -> str:
    """Return a stable, readable runtime type name for a value."""
    value_type = type(value)
    if value_type.__module__ == "builtins":
        return value_type.__name__
    return f"{value_type.__module__}.{value_type.__name__}"


def summarize_value(value: object) -> dict[str, JsonValue]:
    """Create a JSON-serializable summary of a runtime value."""
    summary: dict[str, JsonValue] = {"type": type_name(value)}

    if isinstance(value, tuple):
        summary["length"] = len(value)
        summary["item_types"] = [type_name(item) for item in value]
        if len(value) == 2 and isinstance(value[0], bool):
            summary["loaded"] = value[0]
            summary["raw_data_type"] = type_name(value[1])

    if isinstance(value, list):
        summary["length"] = len(value)
        summary["item_types"] = sorted({type_name(item) for item in value})

    if isinstance(value, dict):
        summary["length"] = len(value)
        summary["key_types"] = sorted({type_name(k) for k in value})
        summary["value_types"] = sorted({type_name(v) for v in value.values()})

    if value is None:
        summary["is_none"] = True

    return summary


def add_observation(
    observations: list[dict[str, JsonValue]],
    *,
    method: str,
    scenario: str,
    args: dict[str, object],
    result: object,
) -> None:
    """Append one method call observation to the report list."""
    normalized_args = {k: summarize_value(v) for k, v in args.items()}
    observations.append(
        {
            "method": method,
            "scenario": scenario,
            "args": normalized_args,
            "result": summarize_value(result),
        }
    )


def read_usage_signatures(report_path: Path) -> set[tuple[str, bool]]:
    """Read unique `load_json(model_class, is_list)` signatures from report."""
    if not report_path.exists():
        return set()

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    signatures: set[tuple[str, bool]] = set()
    for item in report:
        if item.get("func") not in {"_load_json", "load_json"}:
            continue

        model_name = item.get("model_class")
        if not isinstance(model_name, str) or not model_name:
            continue

        is_list = item.get("is_list")
        signatures.add((model_name, bool(True if is_list is None else is_list)))

    return signatures


def collect_paths_by_model(
    manager: DataManager,
    json_service: JsonService,
) -> dict[str, list[Path]]:
    """Collect real JSON paths grouped by model class used by `load_json`."""
    paths_by_model: dict[str, list[Path]] = {
        "CareerDetail": [manager.careers_details_path],
        "CareerMetadata": [],
        "Player": [],
        "Match": [],
    }

    careers = json_service.load_json(manager.careers_details_path, CareerDetail)
    for career in careers:
        career_folder = manager.data_folder / career.folder_name
        paths_by_model["CareerMetadata"].append(career_folder / "metadata.json")
        paths_by_model["Player"].append(career_folder / "players.json")
        paths_by_model["Match"].append(career_folder / "matches.json")

    # Deduplicate while preserving stable order.
    for model_name, model_paths in paths_by_model.items():
        seen: set[Path] = set()
        deduped: list[Path] = []
        for path in model_paths:
            if path in seen:
                continue
            seen.add(path)
            deduped.append(path)
        paths_by_model[model_name] = deduped

    return paths_by_model


def probe() -> dict[str, JsonValue]:
    """Run runtime probes and return report payload."""
    data_folder = PROJECT_ROOT / "data"
    reports_dir = PROJECT_ROOT / "scripts" / "reports"
    usage_report_path = reports_dir / "load_json_usages_report.json"

    manager = DataManager(project_root=PROJECT_ROOT)
    json_service = JsonService()
    model_map: dict[str, type[object]] = {
        "CareerDetail": CareerDetail,
        "CareerMetadata": CareerMetadata,
        "Player": Player,
        "Match": Match,
    }

    signatures = read_usage_signatures(usage_report_path) or {
        ("CareerDetail", True),
        ("CareerMetadata", False),
        ("Player", True),
        ("Match", True),
    }

    paths_by_model = collect_paths_by_model(manager, json_service)
    observations: list[dict[str, JsonValue]] = []

    for model_name, is_list in sorted(signatures):
        model_class = model_map.get(model_name)
        if model_class is None:
            continue

        for json_path in paths_by_model.get(model_name, []):
            scenario = f"{model_name}|is_list={is_list}|path={json_path.name}"

            # 1) _read_raw_json
            read_result = json_service._read_raw_json(json_path)
            add_observation(
                observations,
                method="_read_raw_json",
                scenario=scenario,
                args={"path": json_path},
                result=read_result,
            )

            # 2) load_json
            load_result = json_service.load_json(
                json_path,
                model_class,
                is_list=is_list,
            )
            add_observation(
                observations,
                method="load_json",
                scenario=scenario,
                args={
                    "path": json_path,
                    "model_class": model_class,
                    "is_list": is_list,
                },
                result=load_result,
            )

            loaded, raw_data = read_result
            if not loaded:
                continue

            # 3) Validate method used by load_json branch.
            if is_list:
                validate_result = json_service._validate_list_json(
                    json_path,
                    model_class,
                    raw_data,
                    fallback=[],
                )
                add_observation(
                    observations,
                    method="_validate_list_json",
                    scenario=scenario,
                    args={
                        "path": json_path,
                        "model_class": model_class,
                        "raw_data": raw_data,
                        "fallback": [],
                    },
                    result=validate_result,
                )
            else:
                validate_result = json_service._validate_single_json(
                    json_path,
                    model_class,
                    raw_data,
                )
                add_observation(
                    observations,
                    method="_validate_single_json",
                    scenario=scenario,
                    args={
                        "path": json_path,
                        "model_class": model_class,
                        "raw_data": raw_data,
                    },
                    result=validate_result,
                )

    # Explicitly probe the missing-file branch for default behavior.
    missing_path = data_folder / "__probe_missing_file__.json"
    missing_read = json_service._read_raw_json(missing_path)
    add_observation(
        observations,
        method="_read_raw_json",
        scenario="missing_path",
        args={"path": missing_path},
        result=missing_read,
    )
    missing_load_list = json_service.load_json(missing_path, Player)
    add_observation(
        observations,
        method="load_json",
        scenario="missing_path|Player|is_list=True",
        args={"path": missing_path, "model_class": Player, "is_list": True},
        result=missing_load_list,
    )
    missing_load_single = json_service.load_json(
        missing_path,
        CareerMetadata,
        is_list=False,
    )
    add_observation(
        observations,
        method="load_json",
        scenario="missing_path|CareerMetadata|is_list=False",
        args={
            "path": missing_path,
            "model_class": CareerMetadata,
            "is_list": False,
        },
        result=missing_load_single,
    )

    return {
        "project_root": str(PROJECT_ROOT),
        "data_folder": str(data_folder),
        "signatures_probed": [
            {"model_class": model_name, "is_list": is_list}
            for model_name, is_list in sorted(signatures)
        ],
        "observations": observations,
    }


def main() -> None:
    """Execute probes and write report to scripts/reports directory."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    report = probe()
    out_path = PROJECT_ROOT / "scripts" / "reports" / "load_json_type_probe_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info("Wrote type probe report: %s", out_path)
    logger.info("Observations captured: %s", len(report["observations"]))


if __name__ == "__main__":
    main()
