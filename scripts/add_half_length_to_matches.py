"""
Script to add half-length information to existing match records.

Usage:
    python scripts/add_half_length_to_matches.py [--apply] [<career_folder_path> ...]

Description:
- Scans given career folder for a metadata.json file, and scrapes the half_length value.
- For each match in matches.json, ensures half_length is stored at
    match["data"]["half_length"].
- If a misplaced top-level match["half_length"] exists, it is migrated into
    match["data"] and removed from the top level.
- By default, the script runs in "dry-run" mode, printing proposed changes
    without modifying files.
- Use `--apply` to write changes back to disk; writes are performed atomically.

Exit Codes:
- 0: Success (no changes needed or all changes applied)
- 1: Invalid command-line arguments (e.g., missing folder paths)
- 2: File I/O errors (e.g., missing metadata.json, read/write failures)

Example:
    # Dry-run mode (no changes applied)
    python scripts/add_half_length_to_matches.py /path/to/career_folder

    # Apply changes to disk
    python scripts/add_half_length_to_matches.py --apply /path/to/career_folder
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path


def _read_json(path: str | Path) -> object:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json_atomic(path: str | Path, data: object) -> None:
    p = Path(path)
    dirpath = p.parent
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=str(dirpath), prefix=".tmp-", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp.write("\n")
        Path(tmp.name).replace(p)
    except Exception:
        tmp_path = Path(tmp.name)
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _find_half_length(metadata: dict[str, object]) -> object | None:
    if "half_length" in metadata:
        return metadata["half_length"]
    return next(
        (
            metadata[alt]
            for alt in ("match_half_length", "halftime_length", "halfLength")
            if alt in metadata
        ),
        None,
    )


def _ensure_match_data_half_length(match: dict[str, object], fallback: object) -> bool:
    """Ensure a match stores `half_length` under `match["data"]`.

    Returns True when the match was modified.
    """
    match_data = match.get("data")
    if not isinstance(match_data, dict):
        return False

    changed = False
    top_level_half_length = match.get("half_length")

    if "half_length" not in match_data:
        match_data["half_length"] = (
            top_level_half_length if top_level_half_length is not None else fallback
        )
        changed = True

    if "half_length" in match:
        del match["half_length"]
        changed = True

    return changed


def _resolve_match_identifier(match: dict[str, object], idx: int) -> str:
    match_id = match.get("match_id") or match.get("id") or match.get("date") or str(idx)
    return str(match_id)


def process_career_folder(
    folder: str | Path, apply: bool = False
) -> tuple[int, list[tuple[int, str]], str]:
    """Process a career folder and ensure `data.half_length` is populated.

    Returns a tuple: (count_updated, details_list, matches_path)
    """
    p = Path(folder)
    metadata_path = p / "metadata.json"
    matches_path = p / "matches.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Missing metadata.json: {metadata_path}")
    if not matches_path.is_file():
        raise FileNotFoundError(f"Missing matches.json: {matches_path}")

    metadata = _read_json(metadata_path)
    half_length = _find_half_length(metadata)
    if half_length is None:
        raise KeyError(f"'half_length' not found in metadata: {metadata_path}")

    matches_json = _read_json(matches_path)
    if isinstance(matches_json, dict) and isinstance(matches_json.get("matches"), list):
        matches_list = matches_json["matches"]
        container = matches_json
    elif isinstance(matches_json, list):
        matches_list = matches_json
        container = matches_list
    else:
        raise ValueError(f"Unexpected structure for matches.json: {matches_path}")

    updated: list[tuple[int, str]] = []
    for idx, match in enumerate(matches_list):
        if not isinstance(match, dict):
            continue
        if not _ensure_match_data_half_length(match, half_length):
            continue
        updated.append((idx, _resolve_match_identifier(match, idx)))

    if updated and apply:
        _write_json_atomic(matches_path, container)

    return len(updated), updated, str(matches_path)


def _print_changes(
    folder: str,
    count: int,
    details: list[tuple[int, str]],
    matches_path: str,
    apply: bool,
) -> None:
    if count == 0:
        print(f"No changes needed for {folder}")
        return
    if apply:
        print(f"Updated {count} match(es) in {matches_path}")
    else:
        msg = f"DRY RUN (no changes): would add half_length to {count} match(es)"
        print(msg, "in", matches_path)
    for idx, mid in details:
        print(f" - match[{idx}] id={mid}")


def main(argv: Iterable[str] | None = None) -> int:
    """Command-line entry point for the script."""
    parser = argparse.ArgumentParser(
        prog="add_half_length_to_matches.py",
        description=(
            "Add missing `half_length` values to matches.json from metadata.json"
        ),
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to disk.")
    parser.add_argument(
        "career_folders", nargs="*", help="Paths to career folders to process."
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.career_folders:
        parser.print_usage(sys.stderr)
        print("Error: missing career folder path(s)", file=sys.stderr)
        return 1

    exit_code = 0
    for folder in args.career_folders:
        folder = Path(folder).resolve()
        try:
            count, details, matches_path = process_career_folder(
                folder, apply=args.apply
            )
        except FileNotFoundError as exc:
            print(f"File error for {folder}: {exc}", file=sys.stderr)
            exit_code = 2
            continue
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            print(f"Error processing {folder}: {exc}", file=sys.stderr)
            exit_code = 2
            continue

        _print_changes(folder, count, details, matches_path, args.apply)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
