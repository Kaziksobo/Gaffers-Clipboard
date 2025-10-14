from pathlib import Path
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
import time
import cv2 as cv
from src import ocr
from collections import Counter

training_data_path = project_root / "model" / "training_data"
training_data_path.mkdir(exist_ok=True)

for i in range(10):
    digit_path = training_data_path / str(i)
    digit_path.mkdir(exist_ok=True)
    
print("Training directories set up.")

templates = ocr.load_templates()

image_path = Path(input("Enter the path to the screenshot image: ").strip().strip('"'))
def collect_data(x1, y1, x2, y2, y_increment, iterations):
    for i in range(iterations):
        recognized_number, debug_rois = ocr.recognise_multiple_digits_from_roi(
            full_screenshot=cv.imread(image_path),
            templates=templates,
            roi=(x1, y1, x2, y2),
        )

        print("\n--- Starting Data Collection ---")
        print("For each contour, press the corresponding digit key (0-9) to save the ROI.")
        print("Press SPACE to skip, or ESC to quit.")

        for i, digit in enumerate(debug_rois):
            cv.imshow(f"Label contour #{i+1}", digit)
            key = cv.waitKey(0)

            if key == 27:  # ESC key
                print("Exiting data collection.")
                return

            if 48 <= key <= 57:
                digit_label = chr(key)
                save_path = training_data_path / digit_label / f"{int(time.time())}.png"
                cv.imwrite(str(save_path), digit)
                print(f"Saved contour #{i+1} as digit '{digit_label}' to {save_path}")
            elif key == 32:  # SPACE key
                print(f"Skipped contour #{i+1}")
            else:
                print(f"Unrecognized key for contour #{i+1}, skipping.")
            cv.destroyWindow(f"Label contour #{i+1}")

        cv.destroyAllWindows()
        print("Data collection complete.")
        saved_counts = Counter()

        for digit_dir in training_data_path.iterdir():
            if digit_dir.is_dir():
                saved_counts[digit_dir.name] = len(list(digit_dir.glob("*.png")))

        y1 += y_increment
        y2 += y_increment
    
    print("\n--- Saved Contours Summary ---")
    for digit, count in sorted(saved_counts.items()):
        print(f"Digit '{digit}': {count} contours")
        

if image_path.name.startswith("match"):
    collect_data(890, 348, 950, 372, 66, 15)
    collect_data(1610, 348, 1670, 372, 66, 15)
else:
    collect_data(2280, 395, 2344, 420, 52, 17)
    collect_data(2350, 395, 2414, 420, 52, 17)
