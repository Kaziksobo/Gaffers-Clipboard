"""Compute a match rating for a pasted performance JSON.

Overview
--------
This script helps you manually add a new performance to a match record by
calculating the missing `match_rating` value. It loads the most recent match
from a career's `matches.json` (or a specific match via `--match-id`) and then
uses `MatchRatingsService` to compute a rating on the 0-10 scale.

The script reads a single JSON object from stdin (your pasted performance
payload), validates the minimum required fields, and prints the calculated
rating so you can paste it into `matches.json`.

Quick Start
-----------
Run with a career folder name under `data/`:

        uv run python scripts/rate_latest_match.py --career valencia_cf_1

If you already activated the venv:

        python scripts/rate_latest_match.py --career valencia_cf_1

Then paste a performance JSON object, finish with an empty line, and the
script prints the rating.

Flags
-----
--career
        Career folder name under `data/` (example: `valencia_cf_1`).
        Used to resolve `data/<career>/matches.json` and `metadata.json`.

--matches
        Path to a `matches.json` file OR a folder containing `matches.json`.
        This can be absolute or relative to the project root.
        Example: `--matches data/valencia_cf_1` or
                         `--matches data/valencia_cf_1/matches.json`.

--team-name
        Override the team/club name used for home/away context. If omitted, the
        script uses `metadata.json` in the matches folder to resolve `club_name`.

--match-id
        Use a specific match by id instead of the most recent one. The id is
        matched against the top-level `id` field in `matches.json`.

How It Chooses The Match
------------------------
1) If `--match-id` is provided, it searches for that exact id.
2) Otherwise it picks the match with the highest numeric `id`.
3) If ids are missing or non-numeric, it falls back to the last array entry.

Input Format (Paste JSON)
-------------------------
Paste a single JSON object for the performance. The script strips any existing
`match_rating` value so it always recalculates it.

Outfield example:

        {
            "performance_type": "Outfield",
            "positions_played": ["CM"],
            "goals": 0,
            "assists": 1,
            "shots": 2,
            "shot_accuracy": 50,
            "passes": 34,
            "pass_accuracy": 88,
            "dribbles": 6,
            "dribble_success_rate": 83,
            "tackles": 3,
            "tackle_success_rate": 67,
            "offsides": 0,
            "fouls_committed": 1,
            "possession_won": 4,
            "possession_lost": 2,
            "minutes_played": 90,
            "distance_covered": 10.8,
            "distance_sprinted": 3.4
        }

GK example:

        {
            "performance_type": "GK",
            "shots_against": 12,
            "shots_on_target": 7,
            "saves": 4,
            "goals_conceded": 2,
            "save_success_rate": 57,
            "punch_saves": 0,
            "rush_saves": 0,
            "penalty_saves": 0,
            "penalty_goals_conceded": 0,
            "shoot_out_saves": 0,
            "shoot_out_goals_conceded": 0
        }

Notes:
- `performance_type` must be either "GK" or "Outfield".
- `positions_played` is required for outfield. You can also supply a single
    string and it will be normalized to a one-item list.
- If `minutes_played` is under 10 for outfield, the script prints a message
    and exits without a rating.

Where Match Context Comes From
------------------------------
- Team/opponent xG, goals, and half length are taken from the selected match's
    `data` section.
- `half_length` falls back to `metadata.json` if missing; it defaults to 10.

Output
------
The script prints the calculated rating as a single decimal (e.g., 6.8) and
reminds you to paste it into `match_rating` inside `matches.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from src.contracts.backend import (
    JsonValue,
    MatchOverviewPayload,
    PerformanceMeansStdsMap,
    PerformanceWeightsMap,
    PlayerPerformancePayload,
)
from src.services.analytics import MatchRatingsService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"

JsonObject = dict[str, JsonValue]


def load_json(path: Path) -> JsonValue:
    """Load and parse JSON from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_matches_path(matches_arg: str | None, career: str | None) -> Path:
    """Resolve the matches.json path from CLI arguments or career defaults."""
    if matches_arg:
        matches_path = Path(matches_arg)
        if not matches_path.is_absolute():
            matches_path = (PROJECT_ROOT / matches_path).resolve()
    elif career:
        matches_path = (DATA_DIR / career / "matches.json").resolve()
    else:
        career_dirs = [path for path in DATA_DIR.iterdir() if path.is_dir()]
        if len(career_dirs) != 1:
            raise ValueError(
                "Provide --career or --matches when multiple careers exist."
            )
        matches_path = (career_dirs[0] / "matches.json").resolve()

    if matches_path.is_dir():
        matches_path = matches_path / "matches.json"

    if not matches_path.exists():
        raise FileNotFoundError(f"Matches file not found: {matches_path}")

    return matches_path


def resolve_team_name(metadata_path: Path, override: str | None) -> str:
    """Resolve the team name from metadata.json or a CLI override."""
    if override:
        return override

    if metadata_path.exists():
        metadata = load_json(metadata_path)
        if isinstance(metadata, dict):
            club_name = metadata.get("club_name")
            if isinstance(club_name, str) and club_name.strip():
                return club_name

    raise ValueError(
        "Unable to determine team name. Provide --team-name or metadata.json."
    )


def resolve_latest_match(records: list[JsonObject], match_id: int | None) -> JsonObject:
    """Return the requested match record or the most recent entry."""
    if match_id is not None:
        for match in records:
            if match.get("id") == match_id:
                return match
        raise ValueError(f"Match id {match_id} not found in matches.json.")

    def key(match: JsonObject) -> int:
        """Return a sortable match id value with a safe fallback."""
        match_id_value = match.get("id")
        if isinstance(match_id_value, int):
            return match_id_value
        if isinstance(match_id_value, str) and match_id_value.isdigit():
            return int(match_id_value)
        return -1

    best_match = max(records, key=key, default=None)
    if best_match is None or key(best_match) == -1:
        return records[-1]

    return best_match


def read_performance_from_stdin() -> JsonObject:
    """Prompt for a JSON object and return it as a dictionary."""
    print("Paste the performance JSON, then submit an empty line:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)

    raw = "\n".join(lines).strip()
    if not raw:
        raise ValueError("No JSON input provided.")

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Performance JSON must be a single object.")

    return cast(JsonObject, parsed)


def normalize_positions(performance: JsonObject) -> None:
    """Ensure positions_played is always a list for outfield payloads."""
    positions = performance.get("positions_played")
    if isinstance(positions, str):
        performance["positions_played"] = [positions]


def load_configs() -> tuple[PerformanceWeightsMap, PerformanceMeansStdsMap]:
    """Load and return the performance weights and means/stds maps."""
    weights = cast(
        PerformanceWeightsMap, load_json(CONFIG_DIR / "performance_weights.json")
    )
    means_stds = cast(
        PerformanceMeansStdsMap,
        load_json(CONFIG_DIR / "performance_means_stds.json"),
    )
    return weights, means_stds


def get_match_context(
    matches_path: Path, match_id: int | None, team_name_override: str | None
) -> tuple[JsonObject, MatchOverviewPayload, int, str]:
    """Load the latest match record, and resolve the match context.

    Args:
        matches_path (Path): Path to matches.json file.
        match_id (int | None): Match id to use instead of latest.
        team_name_override (str | None): Override club/team name.

    Raises:
        ValueError: If the match is not found or the context is invalid.
        ValueError: If the match data is missing or invalid.

    Returns:
        tuple[JsonObject, MatchOverviewPayload, int, str]: The latest match record,
                                                           match overview, half length,
                                                           and team name.
    """
    metadata_path = matches_path.parent / "metadata.json"
    team_name = resolve_team_name(metadata_path, team_name_override)

    match_records = load_json(matches_path)
    if not isinstance(match_records, list) or not match_records:
        raise ValueError("matches.json is empty or not a list.")

    latest_match = resolve_latest_match(cast(list[JsonObject], match_records), match_id)
    match_overview = latest_match.get("data", {})
    if not isinstance(match_overview, dict):
        raise ValueError("Match data is missing or invalid.")
    match_overview = cast(MatchOverviewPayload, match_overview)

    half_length = match_overview.get("half_length")
    if not isinstance(half_length, int):
        metadata = load_json(metadata_path) if metadata_path.exists() else {}
        half_length = metadata.get("half_length")
    if not isinstance(half_length, int):
        half_length = 10

    home_team = match_overview.get("home_team_name", "Unknown")
    away_team = match_overview.get("away_team_name", "Unknown")
    print(
        f"Using match {latest_match.get('id', '?')}: {home_team} vs {away_team} "
        f"(half_length={half_length})"
    )

    return latest_match, match_overview, half_length, team_name


def compute_rating(
    service: MatchRatingsService,
    performance: JsonObject,
    match_overview: MatchOverviewPayload,
    half_length: int,
    team_name: str,
) -> float | None:
    """Compute a match rating for a single performance using the analytics service.

    This function dispatches to the appropriate GK or outfield rating method
    based on the performance type.

    Args:
        service: MatchRatingsService instance used to perform rating calculations.
        performance: Raw performance payload to rate.
        match_overview: Overview of the match providing contextual stats.
        half_length: Half length in minutes for the match.
        team_name: Name of the team the player represents.

    Raises:
        ValueError: If performance_type is missing or not 'GK' or 'Outfield'.
        ValueError: If required fields such as positions_played are
                    missing for outfield.

    Returns:
        A numeric rating on the 0-10 scale, or None when no rating should be produced.
    """
    performance_type = performance.get("performance_type")
    if performance_type not in {"GK", "Outfield"}:
        raise ValueError("performance_type must be 'GK' or 'Outfield'.")

    typed_performance = cast(PlayerPerformancePayload, performance)

    if performance_type == "GK":
        return service.calculate_gk_rating(
            performance=typed_performance,
            match_overview=match_overview,
            half_length=half_length,
            team_name=team_name,
        )

    normalize_positions(performance)
    if not performance.get("positions_played"):
        return service.calculate_outfield_rating(
            performance=typed_performance,
            match_overview=match_overview,
            half_length=half_length,
            team_name=team_name,
        )
    else:
        raise ValueError("positions_played is required for outfield ratings.")


def main() -> int:
    """Run the CLI flow and return an appropriate process exit code."""
    parser = argparse.ArgumentParser(
        description="Compute a match rating for a performance in the latest match."
    )
    parser.add_argument("--career", help="Career folder name under data/")
    parser.add_argument("--matches", help="Path to matches.json (file or folder)")
    parser.add_argument("--team-name", help="Override club/team name")
    parser.add_argument(
        "--match-id", type=int, help="Match id to use instead of latest"
    )
    args = parser.parse_args()

    try:
        matches_path = resolve_matches_path(args.matches, args.career)
        weights, means_stds = load_configs()

        _latest_match, match_overview, half_length, team_name = get_match_context(
            matches_path, args.match_id, args.team_name
        )

        performance = dict(read_performance_from_stdin())
        performance.pop("match_rating", None)

        service = MatchRatingsService(weights=weights, means_stds=means_stds)
        rating = compute_rating(
            service, performance, match_overview, half_length, team_name
        )

        if rating is None:
            print("No rating: minutes_played < 10.")
            return 0

        print(f"Calculated rating: {rating:.1f}")
        print("Use this value for match_rating in matches.json.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
