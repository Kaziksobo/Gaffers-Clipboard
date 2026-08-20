# ruff: noqa: E501
"""Generate a full, per-position rating report for every performance in a match.

Overview
--------
rating_attribution.ipynb (workshop/ratings_creation/) walks through the rating
pipeline for one performance, one position at a time. This script instead
takes a real match record — either a single match object (as stored inside
one entry of a career's matches.json) or the whole matches.json array — and
generates the complete step-by-step breakdown for EVERY position of EVERY
outfield performance in that match, plus the multi-position hybrid-blend
section where a performance lists more than one position.

Both the notebook and this script call the same report builders in
workshop/ratings_creation/attribution_lib.py, so their output never drifts
apart.

Quick Start
-----------
Point at a career folder (uses matches.json + metadata.json inside it,
picks the latest match):

        uv run python scripts/full_attribution_report.py --career arsenal_2

Pick a specific match by id:

        uv run python scripts/full_attribution_report.py --career arsenal_2 --match-id 34

Point directly at a standalone match record file (a single object with
"data" and "player_performances", e.g. one match exported out of matches.json):

        uv run python scripts/full_attribution_report.py --match-file match_v_zagreb.json --team-name Arsenal

Flags
-----
--career
        Career folder name under data/ (example: arsenal_2). Resolves to
        data/<career>/matches.json, and looks for data/<career>/metadata.json
        to resolve --team-name if it isn't given explicitly.

--match-file
        Path to a match JSON file: either a single match record (a dict with
        "data" and "player_performances", like one entry of matches.json) or
        a full matches.json array. Overrides --career. Can be absolute or
        relative to the project root. If a metadata.json exists alongside it,
        it's used the same way as with --career.

--match-id
        Select a specific match by its "id" field when the resolved file is
        an array. Ignored for a single match-record file. If omitted, picks
        the highest numeric id (falling back to the last array entry).

--team-name
        Override the team/club name used for home/away context. If omitted,
        resolved from metadata.json's club_name next to the matches file.

--output-dir
        Base directory for reports. Defaults to
        workshop/ratings_creation/rating_reports/. Each run writes into its
        own match_<id>_<timestamp>/ subfolder there.

Output
------
One attribution_<player_id>_<positions>.txt report per outfield performance,
plus a _summary.txt listing every performance's final rating, all inside a
match_<id>_<timestamp>/ subfolder.

Notes
-----
- GK performances are skipped (noted in the summary, not an error):
  calculate_gk_rating() uses its own internal methods, none of which
  attribution_lib.py hooks.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ATTRIBUTION_LIB_DIR = PROJECT_ROOT / "workshop" / "ratings_creation"
if str(ATTRIBUTION_LIB_DIR) not in sys.path:
    sys.path.append(str(ATTRIBUTION_LIB_DIR))

from attribution_lib import (  # noqa: E402 # type: ignore
    build_full_report,
    load_config,
    run_attribution,
)

DEFAULT_REPORTS_DIR = PROJECT_ROOT / "workshop" / "ratings_creation" / "rating_reports"


def resolve_match_path(match_file_arg: str | None, career: str | None) -> Path:
    """Resolve the match JSON path from CLI arguments or the single-career default."""
    if match_file_arg:
        path = Path(match_file_arg)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
    elif career:
        path = (DATA_DIR / career / "matches.json").resolve()
    else:
        career_dirs = (
            [p for p in DATA_DIR.iterdir() if p.is_dir()] if DATA_DIR.exists() else []
        )
        if len(career_dirs) != 1:
            raise ValueError(
                "Provide --match-file or --career when multiple (or zero) careers exist."
            )
        path = (career_dirs[0] / "matches.json").resolve()

    if path.is_dir():
        path = path / "matches.json"

    if not path.exists():
        raise FileNotFoundError(f"Match file not found: {path}")

    return path


def resolve_team_name(metadata_path: Path, override: str | None) -> str:
    """Resolve the team name from metadata.json or a CLI override."""
    if override:
        return override

    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if isinstance(metadata, dict):
            club_name = metadata.get("club_name")
            if isinstance(club_name, str) and club_name.strip():
                return club_name

    raise ValueError(
        "Unable to determine team name. Provide --team-name or place a "
        "metadata.json with club_name next to the match file."
    )


def _select_match_by_id(records: Sequence[dict], match_id: int) -> dict:
    """Return the record whose 'id' field equals match_id."""
    for record in records:
        if record.get("id") == match_id:
            return record
    raise ValueError(f"Match id {match_id} not found in match file.")


def _match_id_sort_key(record: dict) -> int:
    """Return a sortable match id value with a safe fallback."""
    value = record.get("id")
    if isinstance(value, int):
        return value
    return int(value) if isinstance(value, str) and value.isdigit() else -1


def _select_latest_match(records: Sequence[dict]) -> dict:
    """Return the record with the highest numeric id, falling back to the last entry."""
    best = max(records, key=_match_id_sort_key, default=None)
    return records[-1] if best is None or _match_id_sort_key(best) == -1 else best


def resolve_match_record(loaded: Any, match_id: int | None) -> dict:  # noqa: ANN401
    """Return a single match record from a loaded match file.

    Accepts either a single match record (dict with "data" and
    "player_performances") or a matches.json array, matched by --match-id or
    the highest numeric id.
    """
    if isinstance(loaded, dict):
        if "data" in loaded and "player_performances" in loaded:
            return loaded
        raise ValueError(
            "Match file is a single JSON object but is missing 'data' "
            "and/or 'player_performances'."
        )

    if isinstance(loaded, list):
        if not loaded:
            raise ValueError("Match file is an empty list.")
        if match_id is not None:
            return _select_match_by_id(loaded, match_id)
        return _select_latest_match(loaded)

    raise ValueError("Match file must be a JSON object or an array of match records.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the report script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--career", help="Career folder name under data/")
    parser.add_argument(
        "--match-file",
        help=(
            "Path to a single match record JSON or a matches.json array. "
            "Overrides --career."
        ),
    )
    parser.add_argument(
        "--match-id",
        type=int,
        help="Match id to select from an array (default: latest)",
    )
    parser.add_argument("--team-name", help="Override club/team name")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Base directory for reports (default: rating_reports/).",
    )
    return parser.parse_args()


def main() -> int:  # sourcery skip: extract-method
    """Run the full attribution report for every performance in a match."""
    args = parse_args()

    try:
        match_path = resolve_match_path(args.match_file, args.career)
        loaded = json.loads(match_path.read_text(encoding="utf-8"))
        match_record = resolve_match_record(loaded, args.match_id)

        match_data = match_record.get("data")
        if not isinstance(match_data, dict):
            raise ValueError("Match record is missing its 'data' section.")

        performances = match_record.get("player_performances") or []
        if not performances:
            raise ValueError("Match record has no player_performances.")

        metadata_path = match_path.parent / "metadata.json"
        team_name = resolve_team_name(metadata_path, args.team_name)
        half_length = match_data.get("half_length", 10)

        home_team = match_data.get("home_team_name", "Unknown")
        away_team = match_data.get("away_team_name", "Unknown")
        print(
            f"Match {match_record.get('id', '?')}: {home_team} vs {away_team} "
            f"({match_data.get('home_score')}-{match_data.get('away_score')})  "
            f"team={team_name}  half_length={half_length}"
        )

        weights, means_stds = load_config(PROJECT_ROOT)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = (args.output_dir or DEFAULT_REPORTS_DIR) / (
            f"match_{match_record.get('id', 'unknown')}_{timestamp}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        summary_lines = [
            f"Match {match_record.get('id')}: {home_team} vs {away_team} "
            f"({match_data.get('home_score')}-{match_data.get('away_score')})  "
            f"team={team_name}",
            "",
        ]

        for performance in performances:
            player_id = performance.get("player_id")

            if performance.get("performance_type") == "GK":
                summary_lines.append(
                    f"  player {player_id}: GK - skipped (not supported)"
                )
                continue

            svc, final_rating, blend = run_attribution(
                weights=weights,
                means_stds=means_stds,
                match_data=match_data,
                performance=performance,
                team_name=team_name,
                half_length=half_length,
            )
            report_text = build_full_report(
                svc=svc,
                match_data=match_data,
                team_name=team_name,
                performance=performance,
                half_length=half_length,
                final_rating=final_rating,
                blend=blend,
            )

            positions_tag = "-".join(performance.get("positions_played", []))
            report_path = output_dir / f"attribution_{player_id}_{positions_tag}.txt"
            report_path.write_text(report_text, encoding="utf-8")

            summary_lines.append(
                f"  player {player_id!s:<4} {positions_tag:<10} "
                f"final={final_rating}  -> {report_path.name}"
            )

        summary_text = "\n".join(summary_lines)
        (output_dir / "_summary.txt").write_text(summary_text, encoding="utf-8")

        print(summary_text)
        print(
            f"\n{len(performances)} performance(s) processed. Reports written to: {output_dir}"
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
