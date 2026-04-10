"""Interactive helper for collecting labeled digit images for OCR retraining.

This script is not part of the normal app runtime. Its only job is to help
build or refresh the image dataset stored in model/training_data so the KNN
OCR model can be retrained later.

Workflow:
1. Load a screenshot supplied by the user.
2. Choose a preset that defines where stats appear on that screenshot type.
3. Reuse the current OCR preprocessing pipeline to isolate digit candidates.
4. Show each extracted digit to the user for manual labeling.
5. Save the labeled digit image into the matching training_data/<digit>/ folder.

The important design choice here is that this script uses the live contour-based
OCR preprocessing from src.ocr instead of any old template-matching code. That
keeps the training pipeline aligned with the real inference pipeline.
"""

import time
from collections import Counter
from pathlib import Path
from typing import TypedDict

import cv2 as cv

from src import ocr

project_root = Path(__file__).resolve().parent.parent

# Root folder containing the per-digit training image directories.
training_data_path = project_root / "model" / "training_data"


# Presets describe where repeated stat values appear on a given screenshot type.
# Each pass starts from one ROI and moves downward by y_increment for a fixed
# number of rows. Player attributes use lighter erosion because those digits can
# differ visually from the match overview digits.
class PassConfig(TypedDict):
    """Configuration block describing one OCR sampling pass."""

    name: str
    start_roi: tuple[int, int, int, int]
    y_increment: int
    iterations: int
    preprocess_args: dict[str, int]


PRESETS: dict[str, list[PassConfig]] = {
    "match": [
        {
            "name": "left_column",
            "start_roi": (890, 348, 950, 372),
            "y_increment": 66,
            "iterations": 15,
            "preprocess_args": {},
        },
        {
            "name": "right_column",
            "start_roi": (1610, 348, 1670, 372),
            "y_increment": 66,
            "iterations": 15,
            "preprocess_args": {},
        },
    ],
    "player": [
        {
            "name": "attributes_left",
            "start_roi": (2280, 395, 2344, 420),
            "y_increment": 52,
            "iterations": 17,
            "preprocess_args": {"erode_iterations": 1},
        },
        {
            "name": "attributes_right",
            "start_roi": (2350, 395, 2414, 420),
            "y_increment": 52,
            "iterations": 17,
            "preprocess_args": {"erode_iterations": 1},
        },
    ],
}


def ensure_training_directories() -> None:
    """Create the base training directory structure if it does not exist.

    The KNN training script expects images to be split into folders named
    0 through 9. This helper makes sure those directories are always present.
    """
    training_data_path.mkdir(exist_ok=True)
    for digit in range(10):
        (training_data_path / str(digit)).mkdir(exist_ok=True)


def load_screenshot(image_path: Path) -> cv.typing.MatLike:
    """Load the screenshot that will be mined for digit samples.

    Args:
        image_path: Path to the screenshot file selected by the user.

    Returns:
        The decoded OpenCV image array.

    Raises:
        FileNotFoundError: If OpenCV cannot read the image from disk.
    """
    screenshot = cv.imread(str(image_path))
    if screenshot is None:
        raise FileNotFoundError(f"Could not read screenshot: {image_path}")
    return screenshot


def extract_digit_rois(
    full_screenshot: cv.typing.MatLike,
    roi: tuple[int, int, int, int],
    preprocess_args: dict[str, int] | None = None,
) -> list[cv.typing.MatLike]:
    """Extract normalized digit candidate images from a single ROI.

    This reuses the current OCR preprocessing path from src.ocr:
    crop -> grayscale -> blur -> threshold -> erosion -> contour filtering.

    The returned digit images are resized to ocr.STANDARD_SIZE so the saved
    dataset matches the feature shape expected by the KNN training script.

    Args:
        full_screenshot: Full screenshot image as an OpenCV array.
        roi: Target region as (x1, y1, x2, y2).
        preprocess_args: Optional overrides for OCR preprocessing.

    Returns:
        A list of digit candidate images sorted from left to right.
    """
    preprocess_args = preprocess_args or {}
    preprocessed = ocr.preprocess_roi(full_screenshot, roi, **preprocess_args)

    # Candidates are sorted by center x-coordinate so multi-digit numbers are
    # processed in visual reading order.
    candidates = sorted(preprocessed["candidates"], key=lambda item: item[0])

    digit_rois = []
    for _, _x, _y, _w, _h, roi_img in candidates:
        # Resize each extracted digit to the same dimensions used by the live
        # OCR pipeline and by model/train_knn_model.py.
        digit_resized = cv.resize(
            roi_img, ocr.STANDARD_SIZE, interpolation=cv.INTER_CUBIC
        )
        digit_rois.append(digit_resized)

    return digit_rois


def collect_data_for_pass(
    full_screenshot: cv.typing.MatLike,
    pass_config: PassConfig,
    saved_counts: Counter[str],
) -> bool:
    """Run one configured extraction pass over a screenshot column or section.

    A "pass" means repeatedly sampling a starting ROI and then shifting it
    downward by a fixed vertical increment. This is useful for screens where
    stats are arranged as evenly spaced rows.

    Args:
        full_screenshot: Full screenshot image as an OpenCV array.
        pass_config: One preset block from PRESETS.
        saved_counts: Running counter of how many samples were saved per digit.

    Returns:
        True if the pass completed normally.
        False if the user pressed ESC and chose to stop early.
    """
    x1, y1, x2, y2 = pass_config["start_roi"]
    y_increment = pass_config["y_increment"]
    iterations = pass_config["iterations"]
    preprocess_args = pass_config.get("preprocess_args", {})

    print(f"\nStarting pass: {pass_config['name']}")

    for iteration in range(iterations):
        roi = (x1, y1, x2, y2)
        digit_rois = extract_digit_rois(
            full_screenshot, roi, preprocess_args=preprocess_args
        )

        print(f"\nROI {iteration + 1}/{iterations}: {roi}")

        if not digit_rois:
            # Missing contours are not fatal. This usually means the ROI did not
            # contain visible digits or preprocessing failed to isolate them.
            print("No digit contours found. Skipping.")
            y1 += y_increment
            y2 += y_increment
            continue

        print("For each contour, press the matching digit key 0-9 to save it.")
        print("Press SPACE to skip a contour or ESC to stop the script.")

        for index, digit_image in enumerate(digit_rois, start=1):
            window_name = f"{pass_config['name']} contour #{index}"
            cv.imshow(window_name, digit_image)
            key = cv.waitKey(0)

            if key == 27:
                # ESC stops the entire labeling session immediately.
                cv.destroyWindow(window_name)
                cv.destroyAllWindows()
                print("Exiting data collection.")
                return False

            if 48 <= key <= 57:
                # ASCII 48-57 maps to numeric keys 0-9.
                digit_label = chr(key)
                save_path = training_data_path / digit_label / f"{time.time_ns()}.png"
                cv.imwrite(str(save_path), digit_image)
                saved_counts[digit_label] += 1
                print(f"Saved contour #{index} as {digit_label} to {save_path}")
            elif key == 32:
                # SPACE intentionally skips the current contour without saving it.
                print(f"Skipped contour #{index}")
            else:
                # Any other key is treated as an invalid label input.
                print(f"Unrecognized key for contour #{index}. Skipping.")

            cv.destroyWindow(window_name)

        # Advance the ROI downward to the next row in this pass.
        y1 += y_increment
        y2 += y_increment

    return True


def choose_preset() -> str:
    """Ask the user which screenshot layout should be processed.

    Returns:
        The preset name, either "match" or "player".

    Raises:
        ValueError: If the user provides an unsupported choice.
    """
    print("Choose screenshot preset:")
    print("1. match")
    print("2. player")
    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        return "match"
    if choice == "2":
        return "player"

    raise ValueError("Invalid preset selection.")


def print_summary(saved_counts: Counter[str]) -> None:
    """Print a simple per-digit summary of newly saved samples."""
    print("\nSaved contours summary:")
    for digit in map(str, range(10)):
        print(f"Digit {digit}: {saved_counts[digit]}")


def main():
    """Run the interactive training-data collection workflow."""
    ensure_training_directories()
    print("Training directories set up.")

    image_path = Path(
        input("Enter the path to the screenshot image: ").strip().strip('"')
    )
    screenshot = load_screenshot(image_path)
    preset_name = choose_preset()

    # Counter defaults missing digits to zero, which keeps the final summary
    # simple even if no samples were saved for some classes.
    saved_counts = Counter()

    for pass_config in PRESETS[preset_name]:
        should_continue = collect_data_for_pass(screenshot, pass_config, saved_counts)
        if not should_continue:
            break

    cv.destroyAllWindows()
    print_summary(saved_counts)


if __name__ == "__main__":
    main()
