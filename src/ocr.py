import cv2 as cv
import numpy as np
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

STANDARD_SIZE = (30, 35)
CONFIDENCE_THRESHOLD = 0.5

# Error handling timeee
class OCRError(Exception):
    '''Base class for OCR-related errors.'''
    pass

class ModelLoadError(OCRError):
    '''Raised when the OCR model fails to load.'''
    pass

class InvalidImageError(OCRError):
    '''Raised when the input image is invalid or cannot be processed.'''
    pass

class NoDigitsFoundError(OCRError):
    '''Raised when no digit-like contours are found in the ROI.'''
    pass

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
    if not fs.isOpened():
        raise ModelLoadError(f"FileStorage failed to open OCR model file at {model_path}")
    knn_node = fs.getFirstTopLevelNode()
    if knn_node.empty():
        fs.release()
        raise ModelLoadError("Model file appears to be empty or corrupted.")
    knn.read(knn_node)
    fs.release()
    
    print("KNN OCR model loaded successfully.")
    return knn

def recognise_number(full_screenshot: np.ndarray, roi: tuple[int, int, int, int], ocr_model: cv.ml.KNearest, debug: bool = False) -> int | tuple[int | None, dict]:
    '''Recognises a number from a specified region of interest (ROI) in a screenshot using an OCR model.
    This function processes the given ROI by resizing, converting to grayscale, applying blurring, 
    thresholding, and contour detection to isolate digit-like regions. Each detected digit is then 
    classified using the provided OCR model.

    Args:
        full_screenshot (np.ndarray): The full screenshot image as a NumPy array. This should be 
            inputted by cv.imread(str(path_to_image)). Keep it in colour, do not use the grayscale flag.
        roi (tuple[int, int, int, int]): The region of interest in the format (x1, y1, x2, y2).
        ocr_model (cv.ml.KNearest): The OCR model used for digit recognition, supporting the `findNearest` method.
        debug (bool, optional): If True, returns additional debug data. Defaults to False.

    Raises:
        InvalidImageError: If the input image is invalid or cannot be processed.
        ModelLoadError: If the OCR model fails to load or is invalid.
        OCRError: If the OCR process fails for any reason.
        NoDigitsFoundError: If no digit-like contours are found in the ROI.

    Returns:
        int | tuple[int | None, dict]: The recognized number, and optionally debug information if debug is True.
            The debug information dict is in the following format:
                {
                    'threshold': thresh,
                    'eroded': eroded_thresh,
                    'digit_rois': list of digit ROI images (numpy arrays)
                }
    '''
    
    
    # """
    # Recognises a number from a specified region of interest (ROI) in a screenshot using an OCR model.

    # This function processes the given ROI by resizing, converting to grayscale, applying blurring, 
    # thresholding, and contour detection to isolate digit-like regions. Each detected digit is then 
    # classified using the provided OCR model.

    # Args:
    #     full_screenshot (np.ndarray): The full screenshot image as a NumPy array. This should be 
    #         inputted by cv.imread(str(path_to_image)). Keep it in colour, do not use the grayscale flag.
    #     roi (tuple[int, int, int, int]): The region of interest in the format (x1, y1, x2, y2).
    #     ocr_model (cv.ml.KNearest): The OCR model used for digit recognition, supporting the `findNearest` method.
    #     debug (bool, optional): If True, returns additional debug data. Defaults to False.

    # Returns:
    #     int | tuple[int | None, dict]: 
    #         If debug is False:
    #             recognized_number (int | None): The final number the OCR model recognises.
    #         If debug is True:
    #             tuple[int | None, dict]: (recognized_number, debug_data)
    #             where debug_data contains intermediate images for inspection:
    #                 {
    #                     'threshold': thresh,
    #                     'eroded': eroded_thresh,
    #                     'digit_rois': list of digit ROI images (numpy arrays)
    #                 }
    # Returns:
    # """
    if full_screenshot is None:
        raise InvalidImageError("Input image is invalid or cannot be processed - check the image path, format and cv.imread result")

    # Preprocessing Steps
    # Step 1: Crop and Resize
    try:
        roi_image = full_screenshot[roi[1]:roi[3], roi[0]:roi[2]]
    except:
        raise InvalidImageError("ROI coordinates are out of bounds for the provided image.")

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
    if debug:
        save_debug_image("debug_threshold_image.png", thresh)
    # Step 5: Erode to reduce noise
    kernel = np.ones((3, 3), np.uint8)
    eroded_thresh = cv.erode(thresh, kernel, iterations=2)
    if debug:
        save_debug_image("debug_eroded_image.png", eroded_thresh)
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

    # Basic validation: ensure the provided OCR model implements the expected API
    if not hasattr(ocr_model, "findNearest"):
        raise ModelLoadError("ocr_model does not implement findNearest(k) — pass a cv.ml.KNearest instance")

    # Recognise digits
    recognised_digits = []
    for _, x, y, w, h, roi in digit_contours:
        # Recognition Steps
        # Step 1: Resize
        digit_resized = cv.resize(roi, (STANDARD_SIZE), interpolation=cv.INTER_CUBIC)
        # Step 2: Prepare sample by flattening and converting to float32
        sample = np.array([digit_resized.flatten().astype(np.float32)])
        if debug:
            debug_rois.append(digit_resized.copy())
        # Step 3: Classify using OCR model
        _ret, result, _neighbours, _dist = ocr_model.findNearest(sample, k=5)
        if result is None or np.isnan(result).any():
            raise OCRError("KNN returned invalid result for a digit")
        # Step 4: Collect recognised digit
        recognised_digit = str(int(result[0][0]))
        recognised_digits.append(recognised_digit)

    if not recognised_digits:
        if debug:
            return None, {'threshold': thresh, 'eroded': eroded_thresh, 'digit_rois': debug_rois}
        raise NoDigitsFoundError("No digit-like contours were found in the ROI.")

    recognized_value = int(''.join(recognised_digits))
    if debug:
        return recognized_value, {'threshold': thresh, 'eroded': eroded_thresh, 'digit_rois': debug_rois}
    return recognized_value

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