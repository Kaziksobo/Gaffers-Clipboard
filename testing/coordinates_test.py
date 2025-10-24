import json
import cv2 as cv
from pathlib import Path

# Load test coordinates from JSON file
PROJECT_ROOT = Path(__file__).parent.parent
coordinates_path = PROJECT_ROOT / "config" / "coordinates.json"
with open(coordinates_path, 'r') as f:
    coordinates = json.load(f)

# Load a cropped fullscreen screenshot for testing
screenshot_path = PROJECT_ROOT / "testing" / "fullscreen_screenshots" / "cropped" / "player_attributes_1_2.png"
screenshot_image = cv.imread(str(screenshot_path))

for screen_name, screen_data in coordinates.items():
    if screen_name == 'player_attributes':
        for position, stats in coordinates['player_attributes'].items():
            if position == "outfield_2":
                for stat_name, roi in stats.items():
                    print(f"Screen: {screen_name}, Stat: {stat_name}, ROI: {roi}")
                    x1 = roi['x1']
                    y1 = roi['y1']
                    x2 = roi['x2']
                    y2 = roi['y2']
                    top_left = (x1, y1)
                    bottom_right = (x2, y2)
                    cv.rectangle(screenshot_image, top_left, bottom_right, (0, 255, 0), 2)
                    
                    label = f"{screen_name}-{stat_name}"
                    label_position = (x1, y1 - 10)
                    cv.putText(screenshot_image, label, label_position, cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

# Save the annotated image to a file
output_path = PROJECT_ROOT / "testing" / "coordinates_test_output.png"
cv.imwrite(str(output_path), screenshot_image)