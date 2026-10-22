"""Backfill Match Ratings Script.

This script traverses career folders under ``data/`` (either from
``data/careers_details.json`` when available or by scanning the directory), loads
each career's ``metadata.json`` and ``matches.json`` files, and calculates
match ratings using ``MatchRatingsService``. Ratings are written into each
player performance entry in ``matches.json`` as ``match_rating``.

By default, only performances missing a rating are updated. Use ``--overwrite``
to recalculate ratings and replace existing values after tweaking the ratings
logic. The script also normalizes legacy structures (e.g., ``rating`` keys or
alternative match/performance containers) and preserves the overall JSON
shape when saving.

Usage:
    python scripts/backfill_match_ratings.py
    python scripts/backfill_match_ratings.py --overwrite
    python scripts/backfill_match_ratings.py --overwrite --dry-run
    python scripts/backfill_match_ratings.py --career arsenal_2 ipswich_3
"""

import argparse
import json
import logging
from pathlib import Path
from typing import NamedTuple, cast

from src.contracts.analytics import PerformanceMeansStdsMap, PerformanceWeightsMap
from src.contracts.backend import MatchOverviewPayload, PlayerPerformancePayload
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


def resolve_career_context(career_dir: Path) -> tuple[str, int] | None:
    """Resolve team name and half length from a career's metadata."""
    meta_path = career_dir / "metadata.json"
    if not meta_path.exists():
        logger.warning("Skipping %s: Missing metadata.json", career_dir.name)
        return None

    meta_data = cast(dict[str, object], load_json_file(meta_path))
    team_name_raw = meta_data.get("club_name") or meta_data.get("team_name")
    team_name = str(team_name_raw).strip() if team_name_raw is not None else ""
    if not team_name:
        logger.error(
            "Skipping %s: No club_name found in metadata.json",
            career_dir.name,
        )
        return None

    half_length = coerce_half_length(meta_data.get("half_length"), 10)
    return team_name, half_length


def load_matches_container(
    matches_path: Path,
    career_dir: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]] | dict[str, object]] | None:
    """Load matches and return (matches, container) for saving."""
    if not matches_path.exists():
        logger.warning("Skipping %s: Missing matches.json", career_dir.name)
        return None

    matches_json = load_json_file(matches_path)
    if isinstance(matches_json, dict) and isinstance(matches_json.get("matches"), list):
        matches = cast(list[dict[str, object]], matches_json["matches"])
        return matches, matches_json
    if isinstance(matches_json, list):
        matches = cast(list[dict[str, object]], matches_json)
        return matches, matches_json

    logger.error("Skipping %s: Unexpected matches.json structure", career_dir)
    return None


class RatingChange(NamedTuple):
    """A single edit to a performance's rating (``None`` means no value)."""

    old: object
    new: object

    @property
    def is_value_change(self) -> bool:
        """Whether the stored rating value actually differs."""
        return self.old != self.new


def format_rating(value: object) -> str:
    """Format a rating for log output."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.4f}"
    return "none" if value is None else str(value)


def copy_legacy_rating_if_present(
    perf: dict[str, object],
    overwrite_existing: bool,
) -> RatingChange | None:
    """Copy legacy rating into match_rating when appropriate."""
    if not overwrite_existing and "rating" in perf:
        change = RatingChange(perf.get("match_rating"), perf.get("rating"))
        perf["match_rating"] = perf.get("rating")
        perf.pop("rating", None)
        return change

    if overwrite_existing and "rating" in perf:
        perf.pop("rating", None)

    return None


def calculate_match_rating(
    performance_type: object,
    perf_payload: PlayerPerformancePayload,
    ratings_service: MatchRatingsService,
    match_overview: MatchOverviewPayload,
    match_half_length: int,
    team_name: str,
    career_name: str,
) -> float | None:
    """Calculate rating for a performance type or return None."""
    if performance_type == "GK":
        return ratings_service.calculate_gk_rating(
            performance=perf_payload,
            match_overview=match_overview,
            half_length=match_half_length,
            team_name=team_name,
        )
    if performance_type == "Outfield":
        return ratings_service.calculate_outfield_rating(
            performance=perf_payload,
            match_overview=match_overview,
            half_length=match_half_length,
            team_name=team_name,
        )

    logger.warning("Skipping performance without valid type in %s", career_name)
    return None


def update_performance_rating(
    perf: dict[str, object],
    ratings_service: MatchRatingsService,
    match_overview: MatchOverviewPayload,
    match_half_length: int,
    team_name: str,
    career_name: str,
    overwrite_existing: bool,
) -> RatingChange | None:
    """Update a single performance entry and return the change made, if any."""
    if not overwrite_existing and "match_rating" in perf:
        return None

    legacy_change = copy_legacy_rating_if_present(perf, overwrite_existing)
    if legacy_change is not None:
        return legacy_change

    performance_type = perf.get("performance_type")
    perf_payload = cast(PlayerPerformancePayload, perf)
    rating = calculate_match_rating(
        performance_type=performance_type,
        perf_payload=perf_payload,
        ratings_service=ratings_service,
        match_overview=match_overview,
        match_half_length=match_half_length,
        team_name=team_name,
        career_name=career_name,
    )
    if rating is None:
        return None

    change = RatingChange(perf.get("match_rating"), rating)
    perf["match_rating"] = rating
    return change


def change_verb(overwrite_existing: bool, dry_run: bool) -> str:
    """Return the log verb describing a change for the current run mode."""
    if dry_run:
        return "Would change" if overwrite_existing else "Would set"
    return "Changed" if overwrite_existing else "Set"


def log_rating_change(
    verb: str,
    match: dict[str, object],
    match_overview: MatchOverviewPayload,
    perf: dict[str, object],
    change: RatingChange,
) -> None:
    """Log a single old -> new rating change with its match and player."""
    logger.info(
        "  %s | match %s (%s) | player %s: %s -> %s",
        verb,
        match.get("id"),
        match_overview.get("in_game_date"),
        perf.get("player_id"),
        format_rating(change.old),
        format_rating(change.new),
    )


def log_career_summary(
    career_dir: Path,
    value_changes: int,
    updates_made: int,
    dry_run: bool,
) -> None:
    """Log how many ratings changed in value versus structure-only edits."""
    logger.info(
        "%s %s ratings for career: %s (%s unchanged in value)",
        "Would update" if dry_run else "Updated",
        value_changes,
        career_dir.name,
        updates_made - value_changes,
    )


def backfill_match(
    match: dict[str, object],
    ratings_service: MatchRatingsService,
    team_name: str,
    default_half_length: int,
    career_name: str,
    overwrite_existing: bool,
    verb: str,
) -> tuple[int, int]:
    """Update every performance in a match; return (edits, value changes)."""
    match_overview = resolve_match_overview(match)
    match_half_length = coerce_half_length(
        match_overview.get("half_length"), default_half_length
    )
    updates_made = 0
    value_changes = 0

    for perf in resolve_match_performances(match):
        if not isinstance(perf, dict):
            continue

        change = update_performance_rating(
            perf=perf,
            ratings_service=ratings_service,
            match_overview=match_overview,
            match_half_length=match_half_length,
            team_name=team_name,
            career_name=career_name,
            overwrite_existing=overwrite_existing,
        )
        if change is None:
            continue

        updates_made += 1
        if change.is_value_change:
            value_changes += 1
            log_rating_change(verb, match, match_overview, perf, change)

    return updates_made, value_changes


def backfill_career(
    career_dir: Path,
    ratings_service: MatchRatingsService,
    overwrite_existing: bool,
    dry_run: bool = False,
) -> None:
    # sourcery skip: low-code-quality
    """Process a single career directory to backfill match ratings.

    Args:
        career_dir (Path): The path to the specific career directory.
        ratings_service (MatchRatingsService): The initialized ratings service.
        overwrite_existing (bool): Recalculate ratings that already exist.
        dry_run (bool): Report changes without writing them to disk.
    """
    context = resolve_career_context(career_dir)
    if context is None:
        return
    team_name, half_length = context

    matches_path = career_dir / "matches.json"
    matches_result = load_matches_container(matches_path, career_dir)
    if matches_result is None:
        return
    matches, matches_container = matches_result
    verb = change_verb(overwrite_existing, dry_run)
    updates_made = 0
    value_changes = 0

    for match in matches:
        if not isinstance(match, dict):
            continue

        match_updates, match_value_changes = backfill_match(
            match=match,
            ratings_service=ratings_service,
            team_name=team_name,
            default_half_length=half_length,
            career_name=career_dir.name,
            overwrite_existing=overwrite_existing,
            verb=verb,
        )
        updates_made += match_updates
        value_changes += match_value_changes

    if updates_made == 0:
        logger.info("No missing ratings found for career: %s", career_dir.name)
        return

    if not dry_run:
        save_json_file(matches_path, matches_container)
    log_career_summary(career_dir, value_changes, updates_made, dry_run)


def parse_args() -> argparse.Namespace:
    """Parse CLI args for the backfill process."""
    parser = argparse.ArgumentParser(
        description="Backfill match ratings across all careers.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recalculate and overwrite existing match ratings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the changes that would be made without writing any files.",
    )
    parser.add_argument(
        "--career",
        nargs="+",
        metavar="FOLDER",
        help="Only process these career folder names (e.g. arsenal_2).",
    )
    return parser.parse_args()


def main() -> None:
    """Orchestrate the backfill process across all saved careers."""
    args = parse_args()
    logger.info(
        "Starting Match Ratings Backfill Migration (overwrite=%s, dry_run=%s)...",
        args.overwrite,
        args.dry_run,
    )

    career_dirs = resolve_career_dirs()
    if not career_dirs:
        logger.error("No career directories found in %s", DATA_DIR)
        return

    if args.career:
        available = {path.name: path for path in career_dirs}
        if unknown := [name for name in args.career if name not in available]:
            logger.error(
                "Unknown career(s): %s. Available: %s",
                ", ".join(unknown),
                ", ".join(sorted(available)),
            )
            return
        career_dirs = [available[name] for name in dict.fromkeys(args.career)]

    weights, means_stds = load_analytics_configs()
    ratings_service = MatchRatingsService(weights=weights, means_stds=means_stds)

    for career_dir in career_dirs:
        backfill_career(career_dir, ratings_service, args.overwrite, args.dry_run)

    logger.info("Match Ratings Backfill Migration Complete.")


if __name__ == "__main__":
    main()
