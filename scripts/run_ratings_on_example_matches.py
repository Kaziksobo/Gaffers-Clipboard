"""Run MatchRatingsService against docs/example_matches.json.

Overview
--------
Loads the bundled example match dataset (`docs/example_matches.json`), builds
the match overview + performance payloads it expects, and prints the
calculated 0-10 rating for every player performance in every match. Useful for
sanity-checking rating changes against a fixed, known dataset without needing
a real career save.

Quick Start
-----------
    uv run python scripts/run_ratings_on_example_matches.py

Flags
-----
--input
    Path to the example matches JSON file. Defaults to
    `docs/example_matches.json`.

--team-name
    The club whose performances are being rated (matches "home_team_name" or
    "away_team_name" in each match). If omitted, the script auto-detects the
    team name common to every match in the dataset.
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
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_INPUT = PROJECT_ROOT / "docs" / "example_matches.json"

JsonObject = dict[str, JsonValue]


def load_json(path: Path) -> JsonValue:
    """Load and parse JSON from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def resolve_team_name(matches: list[JsonObject], override: str | None) -> str:
    """Resolve the team name to rate, auto-detecting it if not overridden.

    The example dataset has no metadata.json, so the team being tracked is
    inferred as whichever club appears as home_team_name or away_team_name in
    every match record.
    """
    if override:
        return override

    common: set[str] | None = None
    for match in matches:
        data = cast(JsonObject, match.get("data", {}))
        teams = {
            str(data.get("home_team_name", "")),
            str(data.get("away_team_name", "")),
        }
        common = teams if common is None else common & teams

    candidates = sorted(t for t in (common or set()) if t)
    if len(candidates) != 1:
        raise ValueError(
            "Could not auto-detect a single team name common to every match; "
            f"candidates found: {candidates or 'none'}. Pass --team-name."
        )
    return candidates[0]


def compute_rating(
    service: MatchRatingsService,
    performance: JsonObject,
    match_overview: MatchOverviewPayload,
    half_length: int,
    team_name: str,
) -> float | None:
    """Dispatch a single performance payload to the GK or outfield pipeline."""
    typed_performance = cast(PlayerPerformancePayload, performance)
    if performance.get("performance_type") == "GK":
        return service.calculate_gk_rating(
            performance=typed_performance,
            match_overview=match_overview,
            half_length=half_length,
            team_name=team_name,
        )
    return service.calculate_outfield_rating(
        performance=typed_performance,
        match_overview=match_overview,
        half_length=half_length,
        team_name=team_name,
    )


def main() -> int:
    """Run the CLI flow and return an appropriate process exit code."""
    parser = argparse.ArgumentParser(
        description="Run MatchRatingsService against docs/example_matches.json."
    )
    parser.add_argument(
        "--input", default=str(DEFAULT_INPUT), help="Path to example matches JSON"
    )
    parser.add_argument("--team-name", help="Override the club name being rated")
    args = parser.parse_args()

    try:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = (PROJECT_ROOT / input_path).resolve()

        matches = cast(list[JsonObject], load_json(input_path))
        if not isinstance(matches, list) or not matches:
            raise ValueError(f"{input_path} is empty or not a list.")

        weights, means_stds = load_configs()
        service = MatchRatingsService(weights=weights, means_stds=means_stds)
        team_name = resolve_team_name(matches, args.team_name)
        print(f"Rating performances for team: {team_name}\n")

        for match in matches:
            match_overview = cast(MatchOverviewPayload, match.get("data", {}))
            half_length = match_overview.get("half_length")
            if not isinstance(half_length, int):
                half_length = 10

            home_team = match_overview.get("home_team_name", "Unknown")
            away_team = match_overview.get("away_team_name", "Unknown")
            print(f"Match {match.get('id', '?')}: {home_team} vs {away_team}")

            performances = cast(list[JsonObject], match.get("player_performances", []))
            for performance in performances:
                rating = compute_rating(
                    service, performance, match_overview, half_length, team_name
                )
                player_id = performance.get("player_id", "?")
                if performance.get("performance_type") == "GK":
                    label = "GK"
                else:
                    positions = performance.get("positions_played", [])
                    label = "/".join(cast(list[str], positions)) or "?"

                rating_str = (
                    f"{rating:.1f}" if rating is not None else "None (< 10 mins)"
                )
                print(f"  player_id={player_id:<5} pos={label:<6} rating={rating_str}")
            print()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
