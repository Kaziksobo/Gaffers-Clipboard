import cv2 as cv
import numpy as np
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

STANDARD_SIZE = (30, 35)
CONFIDENCE_THRESHOLD = 0.5

def load_ocr_model() -> cv.ml.KNearest:
    '''
    Loads the KNN OCR model from the model directory.

    This function retrieves a pre-trained KNN model for digit recognition from disk and returns it for use in OCR tasks.

    Raises:
        FileNotFoundError: If the model file does not exist at the expected path.

    Returns:
        knn (cv.ml.KNearest): loaded KNN model that can be used in OCR methods
    '''
    # Specifies the file path of the model
    model_path = PROJECT_ROOT / "model" / "knn_ocr_model.yml"
    if not model_path.exists():
        raise FileNotFoundError(f"OCR model file not found at {model_path}")
    
    knn = cv.ml.KNearest_create()
    fs = cv.FileStorage(str(model_path), cv.FILE_STORAGE_READ)
    knn_node = fs.getFirstTopLevelNode()
    knn.read(knn_node)
    fs.release()
    
    print("KNN OCR model loaded successfully.")
    return knn

def recognise_number(full_screenshot: np.ndarray, roi: tuple[int, int, int, int], ocr_model: cv.ml.KNearest) -> int | None:
    '''
    Recognises a number from a specified region of interest (ROI) in a screenshot using an OCR model.\n
    This function processes the given ROI by resizing, converting to grayscale, applying blurring, 
    thresholding, and contour detection to isolate digit-like regions.\n
    Each detected digit is then classified using the provided OCR model.

    Args:
        full_screenshot (np.ndarray): The full screenshot image as a NumPy array. This should be inputted by cv.imread(str(path_to_image)). Keep it in colour, do not use the grayscale flag.
        roi (tuple[int, int, int, int]): The region of interest in the format (x1, y1, x2, y2).
        ocr_model (cv.ml.KNearest): The OCR model used for digit recognition, supporting the `findNearest` method.

    Returns:
        recognized_number (int | None): The final number the OCR model recognises, or None if no digits are found.
    '''
    # Preprocessing Steps
    # Step 1: Crop and Resize
    roi_image = full_screenshot[roi[1]:roi[3], roi[0]:roi[2]]

    new_width = roi_image.shape[1] * 4
    new_height = roi_image.shape[0] * 4
    resized = cv.resize(roi_image, (new_width, new_height), interpolation=cv.INTER_CUBIC)

    # Step 2: Grayscale
    gray = cv.cvtColor(resized, cv.COLOR_BGR2GRAY)

    # Step 3: Blur
    blurred = cv.GaussianBlur(gray, (5, 5), 0)

    # In the next two steps, I am saving debug images to help with tuning the preprocessing steps. This may be removed later.
    # Step 4: Threshold
    _thresh_val, thresh = cv.threshold(blurred, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
    save_debug_image(
        "debug_threshold_image.png", thresh
    )
    # Step 5: Erode to reduce noise
    kernel = np.ones((3, 3), np.uint8)
    eroded_thresh = cv.erode(thresh, kernel, iterations=2)
    save_debug_image(
        "debug_eroded_image.png", eroded_thresh
    )
    # Step 6: Find contours
    contours, _heirarchy = cv.findContours(eroded_thresh, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)

    # Filter and sort contours
    digit_contours = []
    debug_rois = []
    for contour in contours:
        x, y, w, h = cv.boundingRect(contour)
        # Filtering the contours based on size, using values slightly bigger than the font size of the digits in the game
        # This may need to be adjusted, either to handle different resolutions, or different font sizes in different screens in the game
        if h >= 18 and w >= 8:
            centre_x = x + w // 2
            roi = blurred[y:y+h, x:x+w]
            digit_contours.append((centre_x, x, y, w, h, roi))

    digit_contours.sort(key=lambda item: item[0])

    print("Digit contours found:", len(digit_contours))

    # Recognise digits
    recognised_digits = []
    for _, x, y, w, h, roi in digit_contours:
        # Recognition Steps
        # Step 1: Resize
        digit_resized = cv.resize(roi, (STANDARD_SIZE), interpolation=cv.INTER_CUBIC)
        # Step 2: Prepare sample by flattening and converting to float32
        sample = np.array([digit_resized.flatten().astype(np.float32)])
        # Step 3: Classify using OCR model
        _ret, result, _neighbours, _dist = ocr_model.findNearest(sample, k=5)
        # Step 4: Collect recognised digit
        recognised_digit = str(int(result[0][0]))
        recognised_digits.append(recognised_digit)

    return int(''.join(recognised_digits)) if recognised_digits else None

def save_debug_image(filename: str, image: np.ndarray) -> None:
    '''Saves an image to the debug images directory for inspection and troubleshooting.

    This function writes the provided image to a file in the "testing/debug_images" directory under the project root.

    Args:
        filename (str): Name to save the file under
        image (np.ndarray): Image to be saved
    '''
    result = PROJECT_ROOT / "testing" / "debug_images" / filename
    result.parent.mkdir(parents=True, exist_ok=True)
    cv.imwrite(str(result), image)