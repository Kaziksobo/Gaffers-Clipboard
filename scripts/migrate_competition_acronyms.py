"""One-time migration for league/competition label normalization.

Usage:
        python scripts/migrate_competition_acronyms.py [--apply] [<path> ...]

Description:
- Scans career data files and applies the app's current competition/league
    normalization helper (`src.utils.capitalize_competition_name`).
- Targets:
    - data/*/metadata.json: normalizes the `league` value and items in the
        `competitions` list.
    - data/*/matches.json: normalizes `data.competition` for each match row.
- By default the script runs in dry-run mode and reports what would change.
    Use `--apply` to write changes back to disk; writes are performed atomically.
- If no paths are supplied the script defaults to scanning `./data`.

Exit codes:
- 0: completed with no fatal errors.
- 1: one or more fatal errors occurred while processing files.

Examples:
        # Dry-run (default) scanning the data directory
        python scripts/migrate_competition_acronyms.py

        # Dry-run on a specific career directory
        python scripts/migrate_competition_acronyms.py data/valencia_cf_1

        # Apply changes to the specified path(s)
        python scripts/migrate_competition_acronyms.py --apply data

Use `-h` for full argparse help/usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from src.contracts.backend import JsonValue
from src.utils import capitalize_competition_name

TARGET_FILE_NAMES: frozenset[str] = frozenset({"metadata.json", "matches.json"})


@dataclass(slots=True)
class MigrationSummary:
    """Track migration counters for per-run reporting."""

    files_processed: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    labels_updated: int = 0
    fatal_errors: int = 0


def _write_stdout(message: str) -> None:
    """Write a single line to stdout."""
    sys.stdout.write(f"{message}\n")


def _write_stderr(message: str) -> None:
    """Write a single line to stderr."""
    sys.stderr.write(f"{message}\n")


def _write_json_atomic(path: Path, payload: JsonValue) -> None:
    """Write JSON to a temporary file then replace target atomically."""
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    with Path.open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
        f.write("\n")
    tmp_path.replace(path)


def _normalize_if_non_empty(value: str) -> str:
    """Normalize non-empty text and leave empty/whitespace-only values unchanged."""
    return capitalize_competition_name(value) if value.strip() else value


def _migrate_metadata_payload(value: JsonValue) -> tuple[JsonValue, int]:
    """Normalize metadata league and competitions values."""
    if not isinstance(value, dict):
        raise ValueError("metadata.json must contain an object")

    migrated: dict[str, JsonValue] = dict(value)
    labels_updated = 0

    league = migrated.get("league")
    if isinstance(league, str):
        normalized_league = _normalize_if_non_empty(league)
        if normalized_league != league:
            migrated["league"] = normalized_league
            labels_updated += 1

    competitions = migrated.get("competitions")
    if isinstance(competitions, list):
        new_competitions: list[JsonValue] = []
        changed_any = False
        for item in competitions:
            if isinstance(item, str):
                normalized_competition = _normalize_if_non_empty(item)
                new_competitions.append(normalized_competition)
                if normalized_competition != item:
                    labels_updated += 1
                    changed_any = True
            else:
                new_competitions.append(item)

        if changed_any:
            migrated["competitions"] = new_competitions

    return migrated, labels_updated


def _migrate_matches_payload(value: JsonValue) -> tuple[JsonValue, int]:
    """Normalize match data.competition labels for all match rows."""
    if not isinstance(value, list):
        raise ValueError("matches.json must contain a list")

    labels_updated = 0
    migrated_rows: list[JsonValue] = []

    for row in value:
        if not isinstance(row, dict):
            migrated_rows.append(row)
            continue

        migrated_row: dict[str, JsonValue] = dict(row)
        data_node = migrated_row.get("data")

        if isinstance(data_node, dict):
            migrated_data: dict[str, JsonValue] = dict(data_node)
            competition = migrated_data.get("competition")
            if isinstance(competition, str):
                normalized_competition = _normalize_if_non_empty(competition)
                if normalized_competition != competition:
                    migrated_data["competition"] = normalized_competition
                    labels_updated += 1
            migrated_row["data"] = migrated_data

        migrated_rows.append(migrated_row)

    return migrated_rows, labels_updated


def _migrate_payload(path: Path, value: JsonValue) -> tuple[JsonValue, int]:
    """Dispatch payload migration based on target file name."""
    file_name = path.name.lower()
    if file_name == "metadata.json":
        return _migrate_metadata_payload(value)
    if file_name == "matches.json":
        return _migrate_matches_payload(value)
    return value, 0


def _iter_target_files(paths: list[Path]) -> list[Path]:
    """Resolve paths into a de-duplicated list of metadata/matches files."""
    discovered: list[Path] = []
    seen: set[Path] = set()

    for path in paths:
        if path.is_file():
            if path.name.lower() in TARGET_FILE_NAMES and path not in seen:
                discovered.append(path)
                seen.add(path)
            continue

        if path.is_dir():
            for candidate in path.rglob("*.json"):
                if (
                    candidate.name.lower() in TARGET_FILE_NAMES
                    and candidate not in seen
                ):
                    discovered.append(candidate)
                    seen.add(candidate)

    return sorted(discovered)


def _process_file(path: Path, apply_changes: bool) -> tuple[bool, int]:
    """Migrate one file and return changed flag with update count."""
    with Path.open(path, encoding="utf-8") as f:
        raw_data: JsonValue = json.load(f)

    migrated_data, labels_updated = _migrate_payload(path, raw_data)
    if labels_updated == 0:
        return False, 0

    if apply_changes:
        _write_json_atomic(path, migrated_data)

    return True, labels_updated


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize league/competition labels with current app text "
            "normalization in metadata.json and matches.json files."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("data")],
        help=(
            "File or directory paths to scan. Files are processed only when named "
            "metadata.json or matches.json. Directories are scanned recursively. "
            "Defaults to ./data."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write migration changes to disk. Omit for dry-run reporting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    summary = MigrationSummary()

    input_paths: list[Path] = []
    for path in args.paths:
        resolved = path.resolve()
        if not resolved.exists():
            summary.fatal_errors += 1
            _write_stderr(f"ERROR  Missing path: {resolved}")
            continue
        input_paths.append(resolved)

    targets = _iter_target_files(input_paths)

    mode = "APPLY" if args.apply else "DRY-RUN"
    _write_stdout(f"MODE  {mode}")

    for file_path in targets:
        summary.files_processed += 1
        try:
            changed, updated = _process_file(file_path, args.apply)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            summary.fatal_errors += 1
            _write_stderr(f"ERROR  {file_path} :: {exc}")
            continue

        if changed:
            summary.files_changed += 1
            summary.labels_updated += updated
            prefix = "CHANGED" if args.apply else "WOULD_CHANGE"
            _write_stdout(f"{prefix}  {file_path} :: updated {updated} label(s)")
        else:
            summary.files_unchanged += 1
            _write_stdout(f"UNCHANGED  {file_path}")

    _write_stdout(
        "SUMMARY  "
        f"processed={summary.files_processed} "
        f"changed={summary.files_changed} "
        f"unchanged={summary.files_unchanged} "
        f"labels_updated={summary.labels_updated} "
        f"fatal_errors={summary.fatal_errors}"
    )

    return 1 if summary.fatal_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
