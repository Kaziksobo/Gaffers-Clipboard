"""Migrate matches.json files by renaming the JSON key "xG" to "xg" recursively.

Usage:
        python scripts/migrate_matches_xg_key.py <path> [<path> ...]

Description:
- Accepts one or more file or directory paths. Files are processed only when
    their filename is `matches.json` (case-insensitive); directories are scanned
    recursively for files named `matches.json`.
- Recursively traverses JSON objects and lists, renaming object keys named
    "xG" to "xg".
- If both "xG" and "xg" exist in the same object, the existing "xg" is
    preserved and the "xG" entry is removed from the output.
- Writes changed files atomically (writes to a temporary file then replaces
    the original) and outputs per-file status lines and a final SUMMARY line.

Exit codes:
- 0: completed with no fatal errors.
- 1: one or more fatal errors occurred while processing files.

Examples:
        # Run on a directory (recursive)
        python scripts/migrate_matches_xg_key.py data/valencia_cf_1

        # Run on a single file
        python scripts/migrate_matches_xg_key.py data/valencia_cf_1/matches.json

        # Use the project's uv runner
        uv run python scripts/migrate_matches_xg_key.py data/valencia_cf_1

Use `-h` to show argparse help/usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from src.contracts.backend import JsonValue


@dataclass(slots=True)
class MigrationSummary:
    """Track migration counters for per-run reporting."""

    files_processed: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    keys_renamed: int = 0
    fatal_errors: int = 0


def _rename_xg_keys(value: JsonValue) -> tuple[JsonValue, int]:
    """Recursively rename dictionary key xG to xg and count replacements."""
    if isinstance(value, dict):
        renamed_count = 0
        migrated: dict[str, JsonValue] = {}
        has_lowercase_key = "xg" in value

        for key, raw_child in value.items():
            child, child_count = _rename_xg_keys(raw_child)
            renamed_count += child_count

            if key == "xG":
                renamed_count += 1
                if has_lowercase_key:
                    # Keep existing lowercase key when both are present.
                    continue
                migrated["xg"] = child
                continue

            migrated[key] = child

        return migrated, renamed_count

    if isinstance(value, list):
        migrated_list: list[JsonValue] = []
        renamed_count = 0
        for item in value:
            migrated_item, item_count = _rename_xg_keys(item)
            migrated_list.append(migrated_item)
            renamed_count += item_count
        return migrated_list, renamed_count

    return value, 0


def _write_json_atomic(path: Path, payload: JsonValue) -> None:
    """Write JSON to a temporary file then replace target atomically."""
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    with Path.open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
        f.write("\n")
    tmp_path.replace(path)


def _iter_target_files(paths: list[Path]) -> list[Path]:
    """Resolve paths into a de-duplicated list of matches.json files."""
    discovered: list[Path] = []
    seen: set[Path] = set()

    for path in paths:
        if path.is_file():
            if path.name.lower() == "matches.json" and path not in seen:
                discovered.append(path)
                seen.add(path)
            continue

        if path.is_dir():
            for candidate in path.rglob("matches.json"):
                if candidate not in seen:
                    discovered.append(candidate)
                    seen.add(candidate)

    return discovered


def _process_file(path: Path) -> tuple[bool, int]:
    """Migrate one matches.json file and return changed flag with rename count."""
    with Path.open(path, encoding="utf-8") as f:
        raw_data: JsonValue = json.load(f)

    migrated_data, keys_renamed = _rename_xg_keys(raw_data)
    if keys_renamed == 0:
        return False, 0

    _write_json_atomic(path, migrated_data)
    return True, keys_renamed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rename JSON key 'xG' to 'xg' recursively in matches.json files. "
            "Accepts one or more files/directories."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help=(
            "One or more file or directory paths. Files are processed only when "
            "named matches.json; directories are scanned recursively."
        ),
    )
    return parser


def _write_stdout(message: str) -> None:
    """Write a single line to stdout."""
    sys.stdout.write(f"{message}\n")


def _write_stderr(message: str) -> None:
    """Write a single line to stderr."""
    sys.stderr.write(f"{message}\n")


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

    for file_path in targets:
        summary.files_processed += 1
        try:
            changed, renamed = _process_file(file_path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            summary.fatal_errors += 1
            _write_stderr(f"ERROR  {file_path} :: {exc}")
            continue

        if changed:
            summary.files_changed += 1
            summary.keys_renamed += renamed
            _write_stdout(f"CHANGED  {file_path} :: renamed {renamed} key(s)")
        else:
            summary.files_unchanged += 1
            _write_stdout(f"UNCHANGED  {file_path}")

    _write_stdout(
        "SUMMARY  "
        f"processed={summary.files_processed} "
        f"changed={summary.files_changed} "
        f"unchanged={summary.files_unchanged} "
        f"keys_renamed={summary.keys_renamed} "
        f"fatal_errors={summary.fatal_errors}"
    )

    return 1 if summary.fatal_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
