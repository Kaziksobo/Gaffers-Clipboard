import json
import cv2 as cv
from pathlib import Path

# Load test coordinates from JSON file
PROJECT_ROOT = Path(__file__).parent.parent
coordinates_path = PROJECT_ROOT / "config" / "coordinates.json"
with open(coordinates_path, 'r') as f:
    coordinates = json.load(f)

# Load a cropped fullscreen screenshot for testing
screenshot_path = PROJECT_ROOT / "testing" / "fullscreen_screenshots" / "cropped" / "match_overview.png"
screenshot_image = cv.imread(str(screenshot_path))

for screen_name, screen_data in coordinates.items():
    for team_name, team_data in screen_data.items():
        for stat_name, roi in team_data.items():
            print(f"Screen: {screen_name}, Team: {team_name}, Stat: {stat_name}, ROI: {roi}")
            x1 = roi['x1']
            y1 = roi['y1']
            x2 = roi['x2']
            y2 = roi['y2']
            top_left = (x1, y1)
            bottom_right = (x2, y2)
            cv.rectangle(screenshot_image, top_left, bottom_right, (0, 255, 0), 2)
            
            label = f"{screen_name}-{team_name}-{stat_name}"
            label_position = (x1, y1 - 10)
            cv.putText(screenshot_image, label, label_position, cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

# Save the annotated image to a file
output_path = PROJECT_ROOT / "testing" / "coordinates_test_output.png"
cv.imwrite(str(output_path), screenshot_image)