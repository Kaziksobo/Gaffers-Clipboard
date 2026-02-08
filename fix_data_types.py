"""
One-time script to convert stringified numbers to actual integers/floats in existing data files.
Run this from the project root: python fix_data_types.py
"""

import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Keys that should always be converted to integers
INT_KEYS = {
    # Match Overview
    "home_score", "away_score", "half_length",
    
    # Match Stats
    "goals_scored", "goals_conceded", "possession", "ball_recovery", 
    "shots", "passes", "tackles", "tackles_won", "interceptions", "saves", 
    "fouls_committed", "offsides", "corners", "free_kicks", "penalty_kicks", 
    "yellow_cards",

    # Player Performance
    "goals", "assists", "shot_accuracy", "pass_accuracy", "dribbles", 
    "dribbles_success_rate", "tackles_success_rate", "possession_won", 
    "possession_lost", "minutes_played",
    
    # GK Specific Performance
    "shots_against", "shots_on_target", "save_success_rate", "punch_saves", 
    "rush_saves", "penalty_saves", "penalty_goals_conceded", 
    "shoot_out_saves", "shoot_out_goals_conceded",

    # Player Bio
    "age", "weight",

    # Attributes (Physical/Mental/Technical/GK)
    "acceleration", "agility", "balance", "jumping", "sprint_speed", 
    "stamina", "strength", "aggression", "att_position", "composure", 
    "reactions", "vision", "ball_control", "crossing", "curve", 
    "defensive_awareness", "fk_accuracy", "finishing", "heading_accuracy", 
    "long_pass", "long_shots", "penalties", "short_pass", "shot_power", 
    "slide_tackle", "stand_tackle", "volleys", "diving", "handling", 
    "kicking", "reflexes", "positioning",

    # Financials (These might not be snake_case yet depending on your migration)
    "Wage", "Market Value", "Contract Length (years)", "Release Clause", "Sell On Clause (%)"
}

# Keys that should always be converted to floats
FLOAT_KEYS = {
    "xG", "xg", 
    "distance_covered", 
    "distance_sprinted"
}

def safe_to_int(value: Any) -> int | None | Any:
    if isinstance(value, int): return value
    if isinstance(value, float): return int(value)
    if value is None: return None
    if isinstance(value, str):
        if not value.strip(): return None
        try: return int(float(value)) # Handle "75.0" -> 75
        except ValueError: return value # Keep original if parse fails
    return value

def safe_to_float(value: Any) -> float | None | Any:
    if isinstance(value, float): return value
    if isinstance(value, int): return float(value)
    if value is None: return None
    if isinstance(value, str):
        if not value.strip(): return None
        try: return float(value)
        except ValueError: return value
    return value

def fix_types(data: Any) -> Any:
    """Recursively traverse list/dict and fix types."""
    if isinstance(data, dict):
        # We modify the dict in place or create new? Let's modify in place strictly for known keys
        for key, value in data.items():
            # Check INT keys
            if key in INT_KEYS:
                data[key] = safe_to_int(value)
            # Check FLOAT keys
            elif key in FLOAT_KEYS:
                data[key] = safe_to_float(value)
            # Recurse
            else:
                fix_types(value)
    elif isinstance(data, list):
        for item in data:
            fix_types(item)
    return data

def process_file(file_path: Path, backup: bool = True) -> None:
    """Fix types in a single JSON file.
    
    Args:
        file_path: Path to the JSON file.
        backup: Whether to create a backup before modification.
    """
    logger.info(f"Processing: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create backup if requested
        if backup:
            backup_path = file_path.with_suffix('.json.types_backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        
        # Modify data
        fixed_data = fix_types(data)
        
        # Save
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, indent=4)
            
        logger.info("  ✓ Types fixed successfully")
            
    except Exception as e:
        logger.error(f"  ✗ Error processing {file_path}: {e}")

def fix_data_folder(data_folder: Path, backup: bool = True) -> None:
    """Run type fixing on all JSON files in data folder."""
    if not data_folder.exists():
        logger.error(f"Data folder not found: {data_folder}")
        return

    logger.info(f"Starting type repair on data folder: {data_folder}")
    
    # Find all JSON files recursively
    json_files = list(data_folder.rglob("*.json"))
    
    if not json_files:
        logger.warning("No JSON files found to process")
        return

    logger.info(f"Found {len(json_files)} JSON file(s) to process\n")
    
    for json_file in json_files:
        if "backup" in json_file.name:
            continue
        process_file(json_file, backup=backup)

    logger.info(f"\n✓ Type fix complete! Processed {len(json_files)} file(s)")

if __name__ == "__main__":
    # Get project root and data folder
    project_root = Path(__file__).parent
    data_folder = project_root / "data"
    
    # Run migration with backups enabled
    fix_data_folder(data_folder, backup=True)