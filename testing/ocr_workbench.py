import cv2 as cv
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src import ocr
try:
    ocr_model = ocr.load_ocr_model()
except FileNotFoundError as e:
    print(e)
    sys.exit(1)

screenshot_path = PROJECT_ROOT / "testing" / "fullscreen_screenshots" / "cropped" / "match_overview.png"
screenshot_image = cv.imread(str(screenshot_path))

stat_roi = (890, 609, 938, 634)

recognised_number = ocr.recognise_number(
    full_screenshot=screenshot_image,
    roi=stat_roi,
    ocr_model=ocr_model
)
print("Final recognised number:", recognised_number)