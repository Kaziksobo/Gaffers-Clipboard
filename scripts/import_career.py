"""Import a career folder into ``datasets/careers/`` or update one in place.

Overview
--------
Career saves live in ``datasets/careers/<folder_name>/`` exactly as the app writes
them (``matches.json``, ``players.json``, ``metadata.json``) and are registered in
``datasets/careers.toml``. This script is the one supported way to add or refresh a
career, so every dataset passes the same checks before workshop code sees it.

Quick Start
-----------
Add a new career (for example copied across from another machine):

        uv run python scripts/import_career.py C:/path/to/ipswich_town_3 --tags ood pool

Refresh an existing career with a later export (exports are cumulative, ids are
stable, so the existing matches must be an unchanged prefix of the new file):

        uv run python scripts/import_career.py C:/path/to/arsenal_2 --update

Validate without writing anything:

        uv run python scripts/import_career.py C:/path/to/arsenal_2 --update --dry-run

Checks
------
- Every match, player and the metadata validate against the app's Pydantic models.
- Match ids run contiguously from 1 and player ids are unique.
- Every performance refers to a player that exists in ``players.json``.
- The career's club appears in every match, and match ``half_length`` agrees with
  the metadata.
- ``metadata.json`` ``folder_name`` matches the destination folder name.
- With ``--update``: the existing matches are an unchanged prefix of the new
  export (ignoring ``match_rating``), and no existing player id or name changed.

Ratings
-------
``match_rating`` values inside exports are the app's own output from whichever
algorithm version was live when the match was saved, so they are never ground
truth. By default they are nulled on import (``null`` is already valid for the
schema) so a stale value cannot leak into a notebook, and so later exports only
differ in the inputs. Pass ``--keep-ratings`` to leave them untouched.

Flags
-----
source
        Folder containing ``matches.json``, ``players.json`` and ``metadata.json``.

--update
        Replace an existing career with a later export.

--tags
        Roles for the manifest (for example ``calibration``, ``ood``, ``pool``).
        New careers default to ``ood pool``; ``--update`` keeps the existing tags
        unless this flag is given.

--keep-ratings
        Do not null ``match_rating``.

--dry-run
        Validate and report only; write nothing. With ``--update`` the source may
        be the destination folder itself, which turns this into an in-place check.

--datasets-dir
        Override the datasets directory (default: ``<project root>/datasets``).
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas import CareerMetadata, Match, Player  # noqa: E402

DATA_FILES = ("matches.json", "players.json", "metadata.json")
DEFAULT_TAGS = ["ood", "pool"]
MAX_REPORTED = 5
COVERAGE_MIN_MINUTES = 45
POSITION_GROUPS: dict[str, frozenset[str]] = {
    "ST": frozenset({"ST", "CF"}),
    "Winger": frozenset({"LW", "RW"}),
    "WM": frozenset({"LM", "RM"}),
    "CAM": frozenset({"CAM"}),
    "CM": frozenset({"CM"}),
    "CDM": frozenset({"CDM"}),
    "FB/WB": frozenset({"LB", "RB", "LWB", "RWB"}),
    "CB": frozenset({"CB"}),
}

MANIFEST_HEADER = """\
# Career dataset registry (managed by scripts/import_career.py).
#
# Each table is a career folder under datasets/careers/, stored exactly as the app
# writes it. `tags` decide which workshop stages may use the career:
#   calibration - fits weights, means/stds and anchors
#   ood         - out-of-distribution validation only
#   pool        - eligible for pooled analyses (e.g. possession-adjusted distance stats)
# `ratings` is "stored" while match_rating still holds stale values from older
# algorithm versions, or "stripped" once they have been nulled. Loaders ignore the
# stored field either way. Tags can be edited by hand; the script preserves them.
"""


class DatasetError(Exception):
    """Raised when a career folder cannot be read or fails validation."""


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read a JSON file that must contain a list of objects.

    Args:
        path (Path): File to read.

    Raises:
        DatasetError: If the file is not a JSON list.

    Returns:
        list[dict[str, Any]]: The parsed records.
    """
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise DatasetError(f"{path.name} must contain a JSON list.")
    return data


def read_object(path: Path) -> dict[str, Any]:
    """Read a JSON file that must contain a single object.

    Args:
        path (Path): File to read.

    Raises:
        DatasetError: If the file is not a JSON object.

    Returns:
        dict[str, Any]: The parsed object.
    """
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise DatasetError(f"{path.name} must contain a JSON object.")
    return data


def dump_json(data: object) -> bytes:
    """Serialise exactly as the app does: 4-space indent, ASCII, CRLF, no final newline.

    Args:
        data (object): JSON-serialisable data.

    Returns:
        bytes: The encoded file contents.
    """
    text = json.dumps(data, indent=4, ensure_ascii=True)
    return text.replace("\n", "\r\n").encode("utf-8")


def strip_ratings(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a deep copy of matches with every ``match_rating`` set to null.

    Args:
        matches (list[dict[str, Any]]): Match records.

    Returns:
        list[dict[str, Any]]: Copy with ratings nulled.
    """
    stripped = copy.deepcopy(matches)
    for match in stripped:
        for perf in match.get("player_performances", []):
            if "match_rating" in perf:
                perf["match_rating"] = None
    return stripped


def first_difference(old: object, new: object, path: str = "") -> str | None:
    """Describe the first difference between two JSON-like values.

    Args:
        old (object): Existing value.
        new (object): Incoming value.
        path (str): Location prefix used in the description.

    Returns:
        str | None: A description of the first difference, or None if equal.
    """
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            if key not in old or key not in new:
                return f"{path}/{key}: key present in only one version"
            diff = first_difference(old[key], new[key], f"{path}/{key}")
            if diff:
                return diff
        return None
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            return f"{path}: list length {len(old)} vs {len(new)}"
        for i, (a, b) in enumerate(zip(old, new, strict=True)):
            diff = first_difference(a, b, f"{path}[{i}]")
            if diff:
                return diff
        return None
    return None if old == new else f"{path}: {old!r} vs {new!r}"


def schema_problems(
    label: str, model: type[BaseModel], records: list[dict[str, Any]]
) -> list[str]:
    """Validate records against a Pydantic model and report the first few failures.

    Args:
        label (str): Record kind used in messages.
        model (type[BaseModel]): Pydantic model to validate against.
        records (list[dict[str, Any]]): Records to validate.

    Returns:
        list[str]: Human-readable problems (empty when all records validate).
    """
    problems: list[str] = []
    failures = 0
    for record in records:
        try:
            model.model_validate(record)
        except ValidationError as exc:
            failures += 1
            if failures <= MAX_REPORTED:
                err = exc.errors()[0]
                loc = ".".join(str(p) for p in err["loc"])
                problems.append(f"{label} id={record.get('id')}: {loc}: {err['msg']}")
    if failures > MAX_REPORTED:
        problems.append(f"... {failures - MAX_REPORTED} more {label} failures")
    return problems


def validate_career(
    name: str,
    matches: list[dict[str, Any]],
    players: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> list[str]:
    """Run every structural check on a career.

    Args:
        name (str): Expected folder name.
        matches (list[dict[str, Any]]): Match records.
        players (list[dict[str, Any]]): Player records.
        metadata (dict[str, Any]): Career metadata.

    Returns:
        list[str]: Problems found (empty when the career is valid).
    """
    problems = schema_problems("match", Match, matches)
    problems += schema_problems("player", Player, players)
    problems += schema_problems("metadata", CareerMetadata, [metadata])

    if metadata.get("folder_name") != name:
        problems.append(
            f"metadata folder_name {metadata.get('folder_name')!r} != {name!r}"
        )

    ids = [m.get("id") for m in matches]
    if ids != list(range(1, len(matches) + 1)):
        problems.append("match ids are not contiguous from 1")

    player_ids = [p.get("id") for p in players]
    if len(set(player_ids)) != len(player_ids):
        problems.append("duplicate player ids")

    unknown = {
        perf.get("player_id")
        for m in matches
        for perf in m.get("player_performances", [])
        if perf.get("player_id") not in set(player_ids)
    }
    if unknown:
        problems.append(f"performances reference unknown player ids: {sorted(unknown)}")

    club = metadata.get("club_name")
    missing_club = [
        m["id"]
        for m in matches
        if club
        not in (m["data"].get("home_team_name"), m["data"].get("away_team_name"))
    ]
    if missing_club:
        problems.append(
            f"club {club!r} not in match(es): {missing_club[:MAX_REPORTED]}"
        )

    half = metadata.get("half_length")
    bad_half = [m["id"] for m in matches if m["data"].get("half_length") != half]
    if bad_half:
        problems.append(
            f"half_length differs from metadata ({half}) in match(es): "
            f"{bad_half[:MAX_REPORTED]}"
        )
    return problems


def update_problems(
    old_matches: list[dict[str, Any]],
    new_matches: list[dict[str, Any]],
    old_players: list[dict[str, Any]],
    new_players: list[dict[str, Any]],
) -> list[str]:
    """Check that an incoming export extends an existing career without rewriting it.

    Args:
        old_matches (list[dict[str, Any]]): Matches currently in the datasets folder.
        new_matches (list[dict[str, Any]]): Matches in the incoming export.
        old_players (list[dict[str, Any]]): Players currently in the datasets folder.
        new_players (list[dict[str, Any]]): Players in the incoming export.

    Returns:
        list[str]: Problems found (empty when the export is a valid extension).
    """
    problems: list[str] = []
    if len(new_matches) < len(old_matches):
        problems.append(
            f"export has fewer matches ({len(new_matches)}) than the existing "
            f"career ({len(old_matches)})"
        )
    old_s, new_s = strip_ratings(old_matches), strip_ratings(new_matches)
    for old, new in zip(old_s, new_s, strict=False):
        diff = first_difference(old, new)
        if diff:
            problems.append(f"existing match id={old['id']} changed: {diff}")
            break
    new_by_id = {p["id"]: p for p in new_players}
    for player in old_players:
        incoming = new_by_id.get(player["id"])
        if incoming is None:
            problems.append(f"player id={player['id']} ({player['name']}) disappeared")
        elif incoming["name"] != player["name"]:
            problems.append(
                f"player id={player['id']} renamed {player['name']!r} -> "
                f"{incoming['name']!r}"
            )
    return problems


def summarise(matches: list[dict[str, Any]]) -> list[str]:
    """Build report lines describing a career's size and position coverage.

    Args:
        matches (list[dict[str, Any]]): Match records.

    Returns:
        list[str]: Lines ready to print.
    """
    perfs = [p for m in matches for p in m["player_performances"]]
    dates = sorted(m["data"]["in_game_date"][:10] for m in matches)
    coverage: Counter[str] = Counter()
    for perf in perfs:
        if perf["performance_type"] != "Outfield":
            continue
        if perf["minutes_played"] < COVERAGE_MIN_MINUTES:
            continue
        first = perf["positions_played"][0]
        for group, members in POSITION_GROUPS.items():
            if first in members:
                coverage[group] += 1
    lines = [
        f"  matches: {len(matches)}, performances: {len(perfs)}",
        f"  in-game dates: {dates[0]} -> {dates[-1]}",
        f"  outfield perfs >= {COVERAGE_MIN_MINUTES}' by first-listed position: "
        + ", ".join(f"{g}={coverage.get(g, 0)}" for g in POSITION_GROUPS),
    ]
    return lines


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Load the career manifest, returning an empty one if it does not exist.

    Args:
        path (Path): Manifest location.

    Returns:
        dict[str, dict[str, Any]]: Career entries keyed by folder name.
    """
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def render_manifest(manifest: dict[str, dict[str, Any]]) -> str:
    """Render the manifest as TOML.

    Args:
        manifest (dict[str, dict[str, Any]]): Career entries keyed by folder name.

    Returns:
        str: TOML text including the explanatory header.
    """
    blocks = [MANIFEST_HEADER]
    for name in sorted(manifest):
        entry = manifest[name]
        tags = ", ".join(json.dumps(t) for t in entry["tags"])
        blocks.append(
            f"[{name}]\n"
            f"club = {json.dumps(entry['club'], ensure_ascii=False)}\n"
            f"matches = {entry['matches']}\n"
            f"tags = [{tags}]\n"
            f'ratings = "{entry["ratings"]}"\n'
        )
    return "\n".join(blocks)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv (list[str] | None): Argument list, or None to use ``sys.argv``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument(
        "source", type=Path, help="Folder holding the three JSON files."
    )
    parser.add_argument(
        "--update", action="store_true", help="Replace an existing career."
    )
    parser.add_argument("--tags", nargs="+", help="Manifest tags for this career.")
    parser.add_argument(
        "--keep-ratings", action="store_true", help="Keep match_rating."
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only.")
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=PROJECT_ROOT / "datasets",
        help="Datasets directory (default: <project root>/datasets).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate a career export and add it to, or update it in, the datasets folder.

    Args:
        argv (list[str] | None): Argument list, or None to use ``sys.argv``.

    Returns:
        int: Process exit code (0 on success, 1 on any validation problem).
    """
    args = parse_args(argv)
    source: Path = args.source.resolve()
    datasets_dir: Path = args.datasets_dir.resolve()
    manifest_path = datasets_dir / "careers.toml"

    missing = [f for f in DATA_FILES if not (source / f).is_file()]
    if missing:
        print(f"ERROR: {source} is missing {', '.join(missing)}")
        return 1

    matches = read_records(source / "matches.json")
    players = read_records(source / "players.json")
    metadata = read_object(source / "metadata.json")
    name = str(metadata.get("folder_name", ""))
    if not name:
        print("ERROR: metadata.json has no folder_name.")
        return 1

    dest = datasets_dir / "careers" / name
    exists = dest.is_dir()
    if exists and not args.update:
        print(f"ERROR: {dest} already exists; pass --update to refresh it.")
        return 1
    if args.update and not exists:
        print(f"ERROR: --update given but {dest} does not exist.")
        return 1

    problems = validate_career(name, matches, players, metadata)
    in_place = exists and source == dest.resolve()
    if exists and not in_place:
        problems += update_problems(
            read_records(dest / "matches.json"),
            matches,
            read_records(dest / "players.json"),
            players,
        )

    print(f"{name}: {'update' if exists else 'new career'}")
    print("\n".join(summarise(matches)))
    if problems:
        print("PROBLEMS:")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    if args.dry_run:
        print("Dry run: all checks passed, nothing written.")
        return 0
    if in_place:
        print("ERROR: source is the destination; use --dry-run to check in place.")
        return 1

    out_matches = matches if args.keep_ratings else strip_ratings(matches)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "matches.json").write_bytes(dump_json(out_matches))
    (dest / "players.json").write_bytes(dump_json(players))
    shutil.copyfile(source / "metadata.json", dest / "metadata.json")

    manifest = load_manifest(manifest_path)
    previous = manifest.get(name, {})
    manifest[name] = {
        "club": metadata["club_name"],
        "matches": len(matches),
        "tags": args.tags or previous.get("tags") or DEFAULT_TAGS,
        "ratings": "stored" if args.keep_ratings else "stripped",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(render_manifest(manifest), encoding="utf-8")
    print(f"Wrote {dest} and updated {manifest_path.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
