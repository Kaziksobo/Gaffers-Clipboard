"""Retroactively normalize team names in matches.json files.

This migration applies the same matching strategy used by runtime team-name
normalization:
- matches are processed in file order, one row at a time
- reference names start with the career club name from metadata.json when available
- after each row is normalized, its normalized home/away names are added to
    the reference list for subsequent rows
- each match row's home_team_name and away_team_name are re-written to the
  first matching canonical name from the reference list

How to run:
- Dry-run (no file writes):
    uv run python scripts/migrate_matches_team_names.py
- Apply changes (creates backup first for each changed file):
    uv run python scripts/migrate_matches_team_names.py --apply
- Target a specific file or directory:
    uv run python scripts/migrate_matches_team_names.py --apply data/valencia_cf_1

Output legend:
- MODE: Current execution mode (DRY-RUN or APPLY).
- WOULD_CHANGE / CHANGED: File has normalized name updates.
- UNCHANGED: File required no updates.
- BACKUP: Backup file path created before writing a changed file.
- DETAIL: One concrete field update shown as before -> after with row/id context.
- SUMMARY: Totals for processed files, updated names, backups, and errors.
- ERROR: File-level failures (e.g., invalid JSON or missing path).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.contracts.backend import JsonValue
from src.utils import normalize_team_name


@dataclass(slots=True)
class MigrationSummary:
    """Track migration counters for per-run reporting."""

    files_processed: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    names_updated: int = 0
    backups_created: int = 0
    fatal_errors: int = 0


@dataclass(frozen=True, slots=True)
class NameChange:
    """Describe one normalized team-name field change within a match row."""

    row_index: int
    match_id: int | None
    field: str
    before: str
    after: str


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


def _create_backup_copy(path: Path) -> Path:
    """Create a timestamped backup copy next to *path* and return its path."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak-{stamp}")
    suffix = 1

    while backup_path.exists():
        backup_path = path.with_name(f"{path.name}.bak-{stamp}-{suffix}")
        suffix += 1

    shutil.copy2(path, backup_path)
    return backup_path


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

    return sorted(discovered)


def _read_career_team_name(matches_path: Path) -> str | None:
    """Read sibling metadata.json and return club_name when present."""
    metadata_path = matches_path.with_name("metadata.json")
    if not metadata_path.exists():
        return None

    try:
        with Path.open(metadata_path, encoding="utf-8-sig") as f:
            raw_metadata: JsonValue = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(raw_metadata, dict):
        return None

    club_name = raw_metadata.get("club_name")
    if not isinstance(club_name, str):
        return None

    stripped = club_name.strip()
    return stripped or None


def _append_unique(target: list[str], seen: set[str], value: str) -> None:
    """Append a string only once while preserving insertion order."""
    if value in seen:
        return
    target.append(value)
    seen.add(value)


def _build_initial_reference_names(
    career_team_name: str | None,
) -> tuple[list[str], set[str]]:
    """Build initial references used before sequential row processing starts."""
    reference_names: list[str] = []
    seen: set[str] = set()

    if career_team_name and career_team_name.casefold() != "unknown":
        _append_unique(reference_names, seen, career_team_name)

    return reference_names, seen


def _migrate_matches_payload(
    value: JsonValue,
    career_team_name: str | None,
) -> tuple[JsonValue, list[NameChange]]:
    """Normalize home/away names row-by-row, mutating references as we progress."""
    if not isinstance(value, list):
        raise ValueError("matches.json must contain a list")

    reference_names, seen = _build_initial_reference_names(career_team_name)

    changes: list[NameChange] = []
    migrated_rows: list[JsonValue] = []

    for row_index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            migrated_rows.append(row)
            continue

        migrated_row: dict[str, JsonValue] = dict(row)
        data_node = migrated_row.get("data")
        row_id_raw = migrated_row.get("id")
        match_id = row_id_raw if type(row_id_raw) is int else None

        if not isinstance(data_node, dict):
            migrated_rows.append(migrated_row)
            continue

        migrated_data: dict[str, JsonValue] = dict(data_node)
        normalized_names_for_row: list[str] = []

        for key in ("home_team_name", "away_team_name"):
            current = migrated_data.get(key)
            if not isinstance(current, str):
                continue

            stripped = current.strip()
            if not stripped:
                continue

            normalized = normalize_team_name(stripped, reference_names)
            normalized_names_for_row.append(normalized)

            if normalized != current:
                migrated_data[key] = normalized
                changes.append(
                    NameChange(
                        row_index=row_index,
                        match_id=match_id,
                        field=key,
                        before=current,
                        after=normalized,
                    )
                )

        migrated_row["data"] = migrated_data
        migrated_rows.append(migrated_row)

        # Mirror add-match behavior by expanding references after each row.
        for normalized_name in normalized_names_for_row:
            _append_unique(reference_names, seen, normalized_name)

    return migrated_rows, changes


def _process_file(
    path: Path,
    apply_changes: bool,
) -> tuple[bool, list[NameChange], Path | None]:
    """Migrate one matches.json file and return changed flag with update count."""
    with Path.open(path, encoding="utf-8-sig") as f:
        raw_data: JsonValue = json.load(f)

    career_team_name = _read_career_team_name(path)
    migrated_data, changes = _migrate_matches_payload(raw_data, career_team_name)

    if not changes:
        return False, [], None

    backup_path: Path | None = None

    if apply_changes:
        backup_path = _create_backup_copy(path)
        _write_json_atomic(path, migrated_data)

    return True, changes, backup_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Retroactively normalize team names in matches.json files by "
            "replaying rows sequentially with sibling metadata.json club_name "
            "as an initial reference. In --apply mode, a backup file is created "
            "before each changed write."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("data")],
        help=(
            "File or directory paths to scan. Files are processed only when named "
            "matches.json. Directories are scanned recursively. Defaults to ./data."
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
            changed, changes, backup_path = _process_file(file_path, args.apply)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            summary.fatal_errors += 1
            _write_stderr(f"ERROR  {file_path} :: {exc}")
            continue

        if changed:
            summary.files_changed += 1
            summary.names_updated += len(changes)
            prefix = "CHANGED" if args.apply else "WOULD_CHANGE"
            _write_stdout(f"{prefix}  {file_path} :: updated {len(changes)} name(s)")

            if backup_path is not None:
                summary.backups_created += 1
                _write_stdout(f"BACKUP  {file_path} -> {backup_path}")

            for change in changes:
                row_id = change.match_id if change.match_id is not None else "-"
                _write_stdout(
                    "DETAIL  "
                    f"row={change.row_index} "
                    f"id={row_id} "
                    f"field={change.field} "
                    f":: {change.before!r} -> {change.after!r}"
                )
        else:
            summary.files_unchanged += 1
            _write_stdout(f"UNCHANGED  {file_path}")

    _write_stdout(
        "SUMMARY  "
        f"processed={summary.files_processed} "
        f"changed={summary.files_changed} "
        f"unchanged={summary.files_unchanged} "
        f"names_updated={summary.names_updated} "
        f"backups_created={summary.backups_created} "
        f"fatal_errors={summary.fatal_errors}"
    )

    return 1 if summary.fatal_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
