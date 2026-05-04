"""
Backfill Match Ratings Script.

This script traverses all career directories in the data folder, loads historical
match data, and utilizes the MatchRatingsService to append calculated 0-10 match
ratings to existing player performances that currently lack them.
"""

import json
import logging
from pathlib import Path
from typing import cast

from src.contracts.backend import (
    MatchOverviewPayload,
    PerformanceMeansStdsMap,
    PerformanceWeightsMap,
    PlayerPerformancePayload,
)
from src.services.analytics.match_ratings_service import MatchRatingsService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CAREERS_DETAILS_PATH = DATA_DIR / "careers_details.json"
CONFIG_DIR = PROJECT_ROOT / "config"


def load_json_file(filepath: Path) -> dict[str, object] | list[object]:
    """Load and return parsed JSON data from a given filepath.

    Args:
        filepath (Path): The path to the JSON file.

    Returns:
        dict[str, object] | list[object]: The parsed JSON data.
    """
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(filepath: Path, data: list[object] | dict[str, object]) -> None:
    """Save data to a JSON file safely using an atomic write.

    Args:
        filepath (Path): The path to the JSON file.
        data (list[object] | dict[str, object]): The data to save.
    """
    temp_filepath = filepath.with_suffix(".tmp")
    with temp_filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    # Atomically replace the old file with the new one
    temp_filepath.replace(filepath)


def load_analytics_configs() -> tuple[PerformanceWeightsMap, PerformanceMeansStdsMap]:
    """Load the weights and means/standard deviations configurations.

    Returns:
        tuple[PerformanceWeightsMap, PerformanceMeansStdsMap]: The loaded configs.
    """
    weights_path = CONFIG_DIR / "performance_weights.json"
    means_stds_path = CONFIG_DIR / "performance_means_stds.json"

    if not weights_path.exists() or not means_stds_path.exists():
        logger.warning("Analytics config files not found. Using empty dictionaries.")
        return {}, {}

    weights = cast(PerformanceWeightsMap, load_json_file(weights_path))
    means_stds = cast(PerformanceMeansStdsMap, load_json_file(means_stds_path))

    return weights, means_stds


def resolve_career_dirs() -> list[Path]:
    """Resolve career directories from careers_details.json when available."""
    if not DATA_DIR.exists():
        return []

    if not CAREERS_DETAILS_PATH.exists():
        return [path for path in DATA_DIR.iterdir() if path.is_dir()]

    raw_details = load_json_file(CAREERS_DETAILS_PATH)
    if not isinstance(raw_details, list):
        logger.warning("Unexpected careers_details.json structure; scanning data dir.")
        return [path for path in DATA_DIR.iterdir() if path.is_dir()]

    career_dirs: list[Path] = []
    for entry in raw_details:
        if not isinstance(entry, dict):
            continue
        folder_name = entry.get("folder_name")
        if not isinstance(folder_name, str) or not folder_name.strip():
            continue
        candidate = DATA_DIR / folder_name
        if candidate.is_dir():
            career_dirs.append(candidate)
        else:
            logger.warning("Career folder missing: %s", candidate)

    return career_dirs


def coerce_half_length(value: object, fallback: int) -> int:
    """Normalize a half-length value into an int with a fallback."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return fallback
    return fallback


def resolve_match_overview(match: dict[str, object]) -> MatchOverviewPayload:
    """Return the match overview payload from known legacy keys."""
    for key in ("data", "overview", "match_overview"):
        candidate = match.get(key)
        if isinstance(candidate, dict):
            return cast(MatchOverviewPayload, candidate)
    return {}


def resolve_match_performances(match: dict[str, object]) -> list[dict[str, object]]:
    """Return the performance list from known legacy keys."""
    for key in ("player_performances", "performances"):
        candidate = match.get(key)
        if isinstance(candidate, list):
            return cast(list[dict[str, object]], candidate)
    return []


def backfill_career(career_dir: Path, ratings_service: MatchRatingsService) -> None:  # noqa: C901
    # sourcery skip: low-code-quality
    """Process a single career directory to backfill match ratings.

    Args:
        career_dir (Path): The path to the specific career directory.
        ratings_service (MatchRatingsService): The initialized ratings service.
    """
    meta_path = career_dir / "metadata.json"
    matches_path = career_dir / "matches.json"

    if not meta_path.exists() or not matches_path.exists():
        logger.warning(
            "Skipping %s: Missing metadata.json or matches.json",
            career_dir.name,
        )
        return

    meta_data = cast(dict[str, object], load_json_file(meta_path))
    team_name_raw = meta_data.get("club_name") or meta_data.get("team_name")
    team_name = str(team_name_raw).strip() if team_name_raw is not None else ""
    half_length = coerce_half_length(meta_data.get("half_length"), 10)

    if not team_name:
        logger.error(
            "Skipping %s: No club_name found in metadata.json",
            career_dir.name,
        )
        return

    matches_json = load_json_file(matches_path)
    if isinstance(matches_json, dict) and isinstance(matches_json.get("matches"), list):
        matches = cast(list[dict[str, object]], matches_json["matches"])
        matches_container: list[dict[str, object]] | dict[str, object] = matches_json
    elif isinstance(matches_json, list):
        matches = cast(list[dict[str, object]], matches_json)
        matches_container = matches_json
    else:
        logger.error("Skipping %s: Unexpected matches.json structure", career_dir)
        return
    updates_made = 0

    for match in matches:
        if not isinstance(match, dict):
            continue

        match_overview = resolve_match_overview(match)
        performances = resolve_match_performances(match)
        match_half_length = coerce_half_length(
            match_overview.get("half_length"), half_length
        )

        for perf in performances:
            if not isinstance(perf, dict):
                continue

            if "match_rating" in perf:
                continue

            if "rating" in perf:
                perf["match_rating"] = perf.get("rating")
                perf.pop("rating", None)
                updates_made += 1
                continue

            performance_type = perf.get("performance_type")
            rating = None

            perf_payload = cast(PlayerPerformancePayload, perf)

            if performance_type == "GK":
                rating = ratings_service.calculate_gk_rating(
                    performance=perf_payload,
                    match_overview=match_overview,
                    half_length=match_half_length,
                    team_name=team_name,
                )
            elif performance_type == "Outfield":
                rating = ratings_service.calculate_outfield_rating(
                    performance=perf_payload,
                    match_overview=match_overview,
                    half_length=match_half_length,
                    team_name=team_name,
                )
            else:
                logger.warning(
                    "Skipping performance without valid type in %s",
                    career_dir.name,
                )
                continue

            perf["match_rating"] = rating if rating is not None else None
            updates_made += 1

    if updates_made > 0:
        save_json_file(matches_path, matches_container)
        logger.info(
            "Updated %s ratings for career: %s",
            updates_made,
            career_dir.name,
        )
    else:
        logger.info("No missing ratings found for career: %s", career_dir.name)


def main() -> None:
    """Orchestrate the backfill process across all saved careers."""
    logger.info("Starting Match Ratings Backfill Migration...")

    career_dirs = resolve_career_dirs()
    if not career_dirs:
        logger.error("No career directories found in %s", DATA_DIR)
        return

    weights, means_stds = load_analytics_configs()
    ratings_service = MatchRatingsService(weights=weights, means_stds=means_stds)

    for career_dir in career_dirs:
        backfill_career(career_dir, ratings_service)

    logger.info("Match Ratings Backfill Migration Complete.")


if __name__ == "__main__":
    main()
