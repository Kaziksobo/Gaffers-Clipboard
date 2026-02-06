"""
One-time migration script to convert human-readable keys to snake_case in existing data files.
Run this from the project root: python migrate_data_keys.py
"""

import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Mapping of human-readable keys to snake_case keys
KEY_MAPPINGS = {
    # Match stats
    "Possession (%)": "possession",
    "Ball Recovery Time (seconds)": "ball_recovery",
    "Shots": "shots",
    "xG": "xG",
    "Passes": "passes",
    "Tackles": "tackles",
    "Tackles Won": "tackles_won",
    "Interceptions": "interceptions",
    "Saves": "saves",
    "Fouls Committed": "fouls_committed",
    "Offsides": "offsides",
    "Corners": "corners",
    "Free Kicks": "free_kicks",
    "Penalty Kicks": "penalty_kicks",
    "Yellow Cards": "yellow_cards",
    "Red Cards": "red_cards",
    
    # Player performance stats
    "Goals": "goals",
    "Assists": "assists",
    "Shot Accuracy (%)": "shot_accuracy",
    "Pass Accuracy (%)": "pass_accuracy",
    "Dribbles": "dribbles",
    "Dribbles Success Rate (%)": "dribbles_success_rate",
    "Tackles Success Rate (%)": "tackles_success_rate",
    "Possession Won": "possession_won",
    "Possession Lost": "possession_lost",
    "Minutes Played": "minutes_played",
    "Distance Covered (km)": "distance_covered",
    "Distance Sprinted (km)": "distance_sprinted",
    
    # GK stats
    "Shots Against": "shots_against",
    "Shots on Target": "shots_on_target",
    "Goals Conceded": "goals_conceded",
    "Save Success Rate (%)": "save_success_rate",
    "Punch Saves": "punch_saves",
    "Rush Saves": "rush_saves",
    "Penalty Saves": "penalty_saves",
    "Penalty Goals Conceded": "penalty_goals_conceded",
    "Shoot-out Saves": "shoot_out_saves",
    "Shoot-out Goals Conceded": "shoot_out_goals_conceded",
    
    # Player attributes - GK
    "Diving": "diving",
    "Handling": "handling",
    "Kicking": "kicking",
    "Reflexes": "reflexes",
    "Positioning": "positioning",
    
    # Player attributes - Outfield Physical
    "Acceleration": "acceleration",
    "Agility": "agility",
    "Balance": "balance",
    "Jumping": "jumping",
    "Sprint Speed": "sprint_speed",
    "Stamina": "stamina",
    "Strength": "strength",
    
    # Player attributes - Outfield Mental
    "Aggression": "aggression",
    "Att. Position": "att_position",
    "Composure": "composure",
    "Reactions": "reactions",
    "Vision": "vision",
    
    # Player attributes - Outfield Technical
    "Ball Control": "ball_control",
    "Crossing": "crossing",
    "Curve": "curve",
    "Def. Awareness": "defensive_awareness",
    "Dribbling": "dribbling",
    "FK Accuracy": "fk_accuracy",
    "Finishing": "finishing",
    "Heading Acc.": "heading_accuracy",
    "Long Pass": "long_pass",
    "Long Shots": "long_shots",
    "Penalties": "penalties",
    "Short Pass": "short_pass",
    "Shot Power": "shot_power",
    "Slide Tackle": "slide_tackle",
    "Stand Tackle": "stand_tackle",
    "Volleys": "volleys",
}


def normalize_keys(data: Any) -> Any:
    """Recursively normalize dictionary keys to snake_case.
    
    Args:
        data: The data structure to normalize (dict, list, or primitive).
        
    Returns:
        The data structure with normalized keys.
    """
    if isinstance(data, dict):
        normalized = {}
        for key, value in data.items():
            # Convert key if mapping exists, otherwise keep original
            new_key = KEY_MAPPINGS.get(key, key)
            normalized[new_key] = normalize_keys(value)
        return normalized
    elif isinstance(data, list):
        return [normalize_keys(item) for item in data]
    else:
        return data


def migrate_file(file_path: Path, backup: bool = True) -> None:
    """Migrate a single JSON file to use snake_case keys.
    
    Args:
        file_path: Path to the JSON file.
        backup: Whether to create a backup before migration.
    """
    logger.info(f"Processing: {file_path}")
    
    try:
        # Load existing data
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create backup if requested
        if backup:
            backup_path = file_path.with_suffix('.json.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info(f"  ✓ Backup created: {backup_path}")
        
        # Normalize keys
        normalized_data = normalize_keys(data)
        
        # Save normalized data
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, indent=4)
        
        logger.info("  ✓ Migrated successfully")
        
    except json.JSONDecodeError as e:
        logger.error(f"  ✗ JSON decode error: {e}")
    except Exception as e:
        logger.error(f"  ✗ Error: {e}")


def migrate_data_folder(data_folder: Path, backup: bool = True) -> None:
    """Migrate all JSON files in the data folder structure.
    
    Args:
        data_folder: Path to the data folder.
        backup: Whether to create backups before migration.
    """
    if not data_folder.exists():
        logger.error(f"Data folder not found: {data_folder}")
        return
    
    logger.info(f"Starting migration of data folder: {data_folder}")
    logger.info(f"Backup enabled: {backup}\n")
    
    # Find all JSON files recursively
    json_files = list(data_folder.rglob("*.json"))
    
    if not json_files:
        logger.warning("No JSON files found to migrate")
        return
    
    logger.info(f"Found {len(json_files)} JSON file(s) to migrate\n")
    
    # Migrate each file
    for json_file in json_files:
        # Skip backup files
        if json_file.suffix == '.backup':
            continue
        migrate_file(json_file, backup=backup)
    
    logger.info(f"\n✓ Migration complete! Processed {len(json_files)} file(s)")
    if backup:
        logger.info("  Backups saved with .json.backup extension")
        logger.info("  Review changes and delete backups when satisfied")


if __name__ == "__main__":
    # Get project root and data folder
    project_root = Path(__file__).parent
    data_folder = project_root / "data"
    
    # Run migration with backups enabled
    migrate_data_folder(data_folder, backup=True)
    
    logger.info("\n" + "="*60)
    logger.info("IMPORTANT: Review the migrated files before using them!")
    logger.info("If something went wrong, restore from .json.backup files")
    logger.info("="*60)