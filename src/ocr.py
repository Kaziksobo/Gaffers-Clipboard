import cv2 as cv
import numpy as np
from pathlib import Path

STANDARD_SIZE = (30, 35)
CONFIDENCE_THRESHOLD = 0.5

def load_templates() -> dict[int, np.ndarray]:
    '''Load digit templates for recognition.

    Returns:
        dict: A dictionary of digit templates.
    '''
    project_root = Path(__file__).parent.parent
    templates_dir = project_root / "assets" / "template_images"
    templates = {}
    for digit in range(10):
        grey_template = cv.imread(str(templates_dir / f"{digit}.png"), cv.IMREAD_GRAYSCALE)
        resized_template = cv.resize(grey_template, STANDARD_SIZE, interpolation=cv.INTER_CUBIC)
        blurred_template = cv.GaussianBlur(resized_template, (5, 5), 0)
        templates[digit] = blurred_template
    return templates

def get_stat_roi(image_path, coords) -> np.ndarray:
    '''Get the region of interest (ROI) from the image.

    Args:
        image_path (str): The path to the image file
        coords (tuple[int, int, int, int]): The coordinates of the ROI (x1, y1, x2, y2)

    Returns:
        np.ndarray: The extracted and resized ROI
    '''
    source_image = cv.imread(image_path, cv.IMREAD_GRAYSCALE)
    x1, y1, x2, y2 = coords
    roi = source_image[y1:y2, x1:x2]
    blurred_roi = cv.GaussianBlur(roi, (5, 5), 0)
    return cv.resize(blurred_roi, STANDARD_SIZE, interpolation=cv.INTER_CUBIC)

def recognise_digit(roi_image: np.ndarray, templates: dict[int, np.ndarray]) -> int | None:
    '''Recognise a digit from the ROI image using template matching.

    Args:
        roi_image (np.ndarray): The region of interest image, that contains a single digit.
        templates (dict[int, np.ndarray]): A dictionary of digit templates.

    Returns:
        int | None: The recognised digit, or None if no match is found.
    '''
    best_match = None
    best_match_value = -1
    for digit, template in templates.items():
        result = cv.matchTemplate(roi_image, template, cv.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv.minMaxLoc(result)
        print(f'Digit: {digit}, Match Score: {max_val}')
        if max_val > best_match_value:
            best_match_value = max_val
            best_match = digit
    return best_match if best_match_value >= CONFIDENCE_THRESHOLD else None