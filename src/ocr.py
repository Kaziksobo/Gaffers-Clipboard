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

def get_stat_roi(image_path: str, coords: tuple[int, int, int, int]) -> np.ndarray:
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
    print("Recognising digit...")
    best_match = None
    best_match_value = -1
    for digit, template in templates.items():
        result = cv.matchTemplate(roi_image, template, cv.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv.minMaxLoc(result)
        print(f'Digit: {digit}, Match Score: {max_val}')
        if max_val > best_match_value:
            best_match_value = max_val
            best_match = digit
    if best_match_value >= CONFIDENCE_THRESHOLD:
        print(f"Match found: {best_match} with confidence {best_match_value}")
        return best_match
    return None


def recognise_multiple_digits_from_roi(full_screenshot: np.ndarray, templates: dict[int, np.ndarray], roi: tuple[int, int, int, int], threshold_value: int = 100) -> tuple[str, np.ndarray]:
    '''This function extracts digit regions from the specified ROI, recognises each digit using template matching,
    and returns the concatenated result along with a visualisation image.

    Args:
        full_screenshot (np.ndarray): The full screenshot image.
        templates (dict[int, np.ndarray]): A dictionary of digit templates.
        roi (tuple[int, int, int, int]): The coordinates of the ROI (x1, y1, x2, y2).
        threshold_value (int, optional): The threshold value for binarization. Defaults to 100.

    Returns:
        str: The recognised digits as a concatenated string.
        np.ndarray: The visualization image with detected digit contours highlighted.
    '''
    roi_image = full_screenshot[roi[1]:roi[3], roi[0]:roi[2]]

    new_width = roi_image.shape[1] * 4
    new_height = roi_image.shape[0] * 4
    resized = cv.resize(roi_image, (new_width, new_height), interpolation=cv.INTER_CUBIC)

    # --- The rest of the steps are applied to the RESIZED image ---

    # Step 2: Grayscale
    gray = cv.cvtColor(resized, cv.COLOR_BGR2GRAY)

    # Step 3: Blur
    blurred = cv.GaussianBlur(gray, (5, 5), 0)

    # Step 4: Threshold
    _thresh_val, thresh = cv.threshold(blurred, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
    cv.imwrite("debug_threshold_image.png", thresh)

    kernel = np.ones((3, 3), np.uint8)
    eroded_thresh = cv.erode(thresh, kernel, iterations=2)
    cv.imwrite("debug_eroded_image.png", eroded_thresh)

    contours, _heirarchy = cv.findContours(eroded_thresh, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)

    # result = cv.drawContours(eroded_thresh, contours, -1, (0xFF, 0, 0))

    # from matplotlib import pyplot as plt
    # plt.figure()
    # # show the first contour
    # for i, contour in enumerate(contours):
    #     contour_image = np.zeros_like(thresh)
    #     cv.drawContours(contour_image, contours, i, (0xFF, 0, 0), 2)
    #     plt.figure()
    #     plt.title(f"Contour #{i}")
    #     plt.imshow(contour_image)
    # # show the original thresh
    # plt.figure()
    # plt.title("Thresholded Image")
    # plt.imshow(eroded_thresh)
    # plt.show()  

    # print("--- Contour Areas ---")
    # for i, c in enumerate(contours):
    #     area = cv.contourArea(c)
    #     print(f"Contour #{i} Area: {area}")
    # print("--------------------")

    digit_contours = []
    debug_rois = []
    for contour in contours:
        x, y, w, h = cv.boundingRect(contour)
        if h >= 18 and w >= 8:
            digit_roi = blurred[y:y+h, x:x+w]
            digit_contours.append(blurred[y:y+h, x:x+w])

    digit_contours.sort(key=lambda c: cv.boundingRect(c)[0])

    print("Digit contours found:", len(digit_contours))

    recognised_digits = []
    for contour in digit_contours:
        digit_roi = cv.resize(contour, (STANDARD_SIZE), interpolation=cv.INTER_CUBIC)
        debug_rois.append(digit_roi)

        if digit_char := recognise_digit(digit_roi, templates):
            recognised_digits.append(str(digit_char))

    recognised_number = ''.join(recognised_digits)
    print("Recognised digits:", recognised_number)
    return recognised_number, debug_rois