"""
Standalone migration script to reconcile historical stat discrepancies.

This script scans all saved matches and uses the Largest Remainder Method
to proportionally scale player statistics so their sum perfectly matches
the team overview ground truth.
"""

import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# The stats we care about balancing.
# We explicitly exclude 'passes' if you are keeping your 20-pass GK tolerance.
STATS_TO_RECONCILE = [
    "shots",
    "tackles",
    "fouls_committed",
    "offsides",
    # Add 'goals' here ONLY if you are certain there are no Own Goals in your dataset.
    # Otherwise, it's safer to leave goals alone or handle them manually.
]


def largest_remainder_method(target_total: int, current_values: list[int]) -> list[int]:
    """Proportionally scales a list of integers to match a target sum exactly."""
    current_sum = sum(current_values)

    # Edge Case 1: Perfect match already
    if current_sum == target_total:
        return current_values

    # Edge Case 2: Target is 0, but players have stats (OCR hallucination)
    if target_total == 0:
        return [0] * len(current_values)

    # Edge Case 3: Players have 0 stats, but team has stats (OCR missed a whole column)
    if current_sum == 0:
        base_val, remainder = divmod(target_total, len(current_values))
        new_vals = [base_val] * len(current_values)
        for i in range(remainder):
            new_vals[i] += 1
        return new_vals

    # Calculate exact float proportions
    proportions = [(val / current_sum) * target_total for val in current_values]

    # Take the integer floor
    lower_bounds = [int(p) for p in proportions]
    remainders = [p - lb for p, lb in zip(proportions, lower_bounds, strict=False)]

    # Calculate how many integer points are missing due to rounding down
    difference = target_total - sum(lower_bounds)

    # Distribute the missing points to the players with the highest decimal remainder
    # We sort by remainder descending, keeping track of the original index
    indexed_remainders = sorted(enumerate(remainders), key=lambda x: x[1], reverse=True)

    for i in range(difference):
        original_index = indexed_remainders[i][0]
        lower_bounds[original_index] += 1

    return lower_bounds


def load_club_name(career_dir: Path) -> str | None:
    """Load the club name from the career metadata."""
    metadata_path = career_dir / "metadata.json"
    try:
        with Path.open(metadata_path, encoding="utf-8") as f:
            metadata: dict[str, Any] = json.load(f)
    except FileNotFoundError:
        logger.error(f"Missing metadata.json in {career_dir}")
        return None
    except Exception as e:
        logger.error(f"Failed to read {metadata_path}: {e}")
        return None

    club_name = metadata.get("club_name")
    if not club_name:
        logger.error(f"Missing club_name in {metadata_path}")
        return None

    return club_name


def process_match_file(file_path: Path, club_name: str | None) -> None:  # noqa: C901
    # sourcery skip: low-code-quality
    """Read a matches.json file, apply corrections, and save if modified."""
    if not club_name:
        logger.warning(f"Skipping {file_path} due to missing club name")
        return

    try:
        with Path.open(file_path, encoding="utf-8") as f:
            matches: list[dict[str, Any]] = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return

    file_modified = False

    for match_idx, match in enumerate(matches):
        match_data = match.get("data", {})
        performances = match.get("player_performances", [])

        if not isinstance(match_data, dict):
            logger.warning(
                f"[{file_path.parent.name}] Match {match_idx + 1} - "
                "Invalid match data; skipping."
            )
            continue

        home_team = match_data.get("home_team_name")
        away_team = match_data.get("away_team_name")
        if club_name == home_team:
            team_stats = match_data.get("home_stats", {})
        elif club_name == away_team:
            team_stats = match_data.get("away_stats", {})
        else:
            logger.warning(
                f"[{file_path.parent.name}] Match {match_idx + 1} - "
                f"Club '{club_name}' not found in teams; skipping."
            )
            continue

        if not isinstance(team_stats, dict) or not team_stats:
            logger.warning(
                f"[{file_path.parent.name}] Match {match_idx + 1} - "
                "Missing team stats; skipping."
            )
            continue

        # Only scale outfield players, as GKs usually don't have tackles/shots tracked
        outfielders = [
            p for p in performances if p.get("performance_type") == "Outfield"
        ]

        if not outfielders:
            continue

        for stat in STATS_TO_RECONCILE:
            team_total = team_stats.get(stat, 0)
            player_current_vals = [p.get(stat, 0) for p in outfielders]
            player_sum = sum(player_current_vals)

            if player_sum != team_total:
                logger.info(
                    f"[{file_path.parent.name}] Match {match_idx + 1} - "
                    f"Fixing {stat}: Players({player_sum}) -> Team({team_total})"
                )

                # Calculate the mathematically perfectly scaled new values
                new_vals = largest_remainder_method(team_total, player_current_vals)

                # Apply them back to the outfielder dictionaries
                for player, new_val in zip(outfielders, new_vals, strict=False):
                    player[stat] = new_val

                file_modified = True

    if file_modified:
        # Save the file back to disk
        with Path.open(file_path, "w", encoding="utf-8") as f:
            json.dump(matches, f, indent=4)
        logger.info(f"Successfully saved corrections to {file_path.name}")


def run_migration(data_directory: Path) -> None:
    """Scan the data directory for all matches.json files and process them."""
    logger.info(f"Starting historical data migration in {data_directory}")

    match_files = list(data_directory.rglob("matches.json"))
    if not match_files:
        logger.warning("No matches.json files found.")
        return

    for file_path in match_files:
        club_name = load_club_name(file_path.parent)
        process_match_file(file_path, club_name)

    logger.info("Migration complete.")


if __name__ == "__main__":
    # TARGET YOUR DATA DIRECTORY HERE
    # Ensure this points to where your career saves live
    target_dir = Path("data")  # e.g., Path("tests/fixtures/testing_data/data")

    # WARNING: Architect's Directive
    response = input(
        f"WARNING: This will mutate JSON files in {target_dir}. "
        "Did you make a backup? (y/n): "
    )
    if response.lower() == "y":
        run_migration(target_dir)
    else:
        print(
            "Aborting. Please copy your data folder to a safe location before running."
        )
