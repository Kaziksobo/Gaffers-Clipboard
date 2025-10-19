import json
from pathlib import Path

# Load test coordinates from JSON file
PROJECT_ROOT = Path(__file__).parent.parent
coordinates_path = PROJECT_ROOT / "config" / "coordinates.json"
with open(coordinates_path, 'r') as f:
    coordinates = json.load(f)

# Define the order of stats as they appear on screen to ensure correct calculation
ORDERED_STATS = [
    "possession", "ball_recovery", "shots", "xG", "passes", "tackles", 
    "tackles_won", "interceptions", "saves", "fouls_comitted", "offsides", 
    "corners", "free_kicks", "penalty_kicks", "yellow_cards"
]

BASE_SPACING = 65
DRIFT_COEFFICIENT = 0.04

for team in coordinates['match_overview'].keys():
    stats_data = coordinates['match_overview'][team]
    
    start_y1 = stats_data[ORDERED_STATS[0]]['y1']
    
    for i, stat in enumerate(ORDERED_STATS):
        y_offset = (i * BASE_SPACING) + (DRIFT_COEFFICIENT * (i ** 2))
        new_y1 = int(start_y1 + y_offset)
        
        box_height = stats_data[stat]['y2'] - stats_data[stat]['y1']
        
        stats_data[stat]['y1'] = round(new_y1)
        stats_data[stat]['y2'] = round(new_y1 + box_height)

with open(coordinates_path, 'w') as f:
    json.dump(coordinates, f, indent=4)
