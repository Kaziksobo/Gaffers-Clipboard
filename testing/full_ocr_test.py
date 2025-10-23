import cv2 as cv
from pathlib import Path
import sys, json

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src import ocr

# Load coordinates from JSON file
coordinates_path = PROJECT_ROOT / "config" / "coordinates.json"
with open(coordinates_path, 'r') as f:
    coordinates = json.load(f)

# Import OCR model
ocr_model = ocr.load_ocr_model()

# Load a cropped fullscreen screenshot for testing
screenshot_path = PROJECT_ROOT / "testing" / "fullscreen_screenshots" / "cropped" / "match_overview_2.png"
screenshot_image = cv.imread(str(screenshot_path))

decimal_stats = ['xG']

results = {}

for screen_name, screen_data in coordinates.items():
    for team_name, team_data in screen_data.items():
        results[team_name] = {}
        for stat_name, roi in team_data.items():
            x1 = roi['x1']
            y1 = roi['y1']
            x2 = roi['x2']
            y2 = roi['y2']
            stat_roi = (x1, y1, x2, y2)

            recognised_number = ocr.recognise_number(
                full_screenshot=screenshot_image,
                roi=stat_roi,
                ocr_model=ocr_model
            )
            
            if stat_name in decimal_stats:
                recognised_number = str(recognised_number)
                if len(recognised_number) > 1:
                    recognised_number = recognised_number[:-1] + '.' + recognised_number[-1]
                recognised_number = float(recognised_number)
            
            results[team_name][stat_name] = recognised_number

# Print the final recognised numbers for each team and stat
for team, stats in results.items():
    print(f"Team: {team}")
    for stat, number in stats.items():
        print(f"  {stat}: {number}")