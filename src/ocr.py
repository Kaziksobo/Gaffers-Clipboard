import cv2 as cv
import numpy as np
import logging
from pathlib import Path
import sys
from src.exceptions import OCRError, ModelLoadError, InvalidImageError, NoDigitsFoundError

logger = logging.getLogger(__name__)

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
    # Open the model file for reading using OpenCV's FileStorage
    fs = cv.FileStorage(str(model_path), cv.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise ModelLoadError(f"FileStorage failed to open OCR model file at {model_path}")
    # In OpenCV's YML format, the model data is a top-level node
    knn_node = fs.getFirstTopLevelNode()
    if knn_node.empty():
        fs.release()
        raise ModelLoadError("Model file appears to be empty or corrupted.")
    # Read the model data from the node
    knn.read(knn_node)
    fs.release()
    
    logger.debug("KNN OCR model loaded successfully.")
    return knn

def preprocess_roi(
    full_screenshot: np.ndarray,
    roi: tuple[int, int, int, int],
    *,
    scale: int = 4,
    blur_kernel: tuple[int, int] = (5, 5),
    erode_kernel: tuple[int, int] = (3, 3),
    erode_iterations: int = 2,
    min_h: int = 18,
    min_w: int = 8) -> dict:
    '''Preprocesses a region of interest (ROI) from a screenshot for digit recognition.
    This function extracts, resizes, and processes the ROI to enhance digit-like features, 
    returning intermediate images and candidate digit regions.

    Args:
        full_screenshot (np.ndarray): The full screenshot image (BGR color) as returned by
            ``cv.imread``. Do not pass a grayscale image.
        roi (tuple[int, int, int, int]): ROI coordinates as (x1, y1, x2, y2).
        scale (int, optional): Upscaling factor for the ROI. Defaults to 4.
        blur_kernel (tuple[int, int], optional): Kernel size for Gaussian blur. Defaults to (5, 5).
        erode_kernel (tuple[int, int], optional): Kernel size for erosion. Defaults to (3, 3).
        erode_iterations (int, optional): Number of erosion iterations. Defaults to 2.
        min_h (int, optional): Minimum height for candidate digits. Defaults to 18.
        min_w (int, optional): Minimum width for candidate digits. Defaults to 8.

    Raises:
        InvalidImageError: If the input image is empty
        InvalidImageError: If the ROI is out of bounds for the image
        InvalidImageError: If the cropped ROI is empty

    Returns:
        dict: A dictionary containing the processed images and candidate regions. The keys are:
            - 'resized': np.ndarray (the resized ROI image)
            - 'gray': np.ndarray (the grayscale image)
            - 'blurred': np.ndarray (the blurred image)
            - 'thresh': np.ndarray (the thresholded image)
            - 'eroded': np.ndarray (the eroded image)
            - 'contours': list (the contours found in the eroded image)
            - 'candidates': list of tuples (each tuple contains (centre_x, x, y, w, h, roi_image) for each candidate digit)
    '''
    
    if full_screenshot is None:
        raise InvalidImageError("Input image is None")

    x1, y1, x2, y2 = roi
    h_img, w_img = full_screenshot.shape[:2]
    if not (0 <= x1 < x2 <= w_img and 0 <= y1 < y2 <= h_img):
        logger.warning(f"ROI {roi} out of bounds for image {w_img}x{h_img}")
        raise InvalidImageError(f"ROI {roi} out of bounds for image shape {(w_img, h_img)}")

    roi_image = full_screenshot[y1:y2, x1:x2]
    if roi_image.size == 0 or roi_image.shape[0] == 0 or roi_image.shape[1] == 0:
        raise InvalidImageError("Cropped ROI is empty")

    # Step 1: Upscale the image. This makes the digits larger and clearer,
    # improving the accuracy of subsequent steps like contour detection.
    new_width = max(1, int(roi_image.shape[1] * scale))
    new_height = max(1, int(roi_image.shape[0] * scale))
    resized = cv.resize(roi_image, (new_width, new_height), interpolation=cv.INTER_CUBIC)

    # Step 2: Convert to grayscale and apply a Gaussian blur to reduce noise.
    # This helps prevent the thresholding step from creating false artifacts.
    gray = cv.cvtColor(resized, cv.COLOR_BGR2GRAY)
    blurred = cv.GaussianBlur(gray, blur_kernel, 0)
    
    # Step 3: Apply Otsu's thresholding to create a binary (black and white) image.
    # This separates the digits (foreground) from the background.
    _, thresh = cv.threshold(blurred, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
    
    # Step 4: Erode the image to remove small noise and help separate touching digits.
    kernel = np.ones(erode_kernel, np.uint8)
    eroded = cv.erode(thresh, kernel, iterations=erode_iterations)

    # Step 5: Find the external contours of the shapes in the eroded image.
    # These contours represent potential digits.
    contours, _ = cv.findContours(eroded, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)

    candidates: list[tuple[int, int, int, int, int, np.ndarray]] = []
    for contour in contours:
        x, y, w, h = cv.boundingRect(contour)
        if h >= min_h and w >= min_w:
            centre_x = x + w // 2
            roi_img = thresh[y:y+h, x:x+w]
            candidates.append((centre_x, x, y, w, h, roi_img))

    return {
        'resized': resized,
        'gray': gray,
        'blurred': blurred,
        'thresh': thresh,
        'eroded': eroded,
        'contours': contours,
        'candidates': candidates,
    }

def recognise_number(
    full_screenshot: np.ndarray, 
    roi: tuple[int, int, int, int], 
    ocr_model: cv.ml.KNearest, 
    debug: bool = False,
    preprocess_args: dict | None = None) -> int | tuple[int | None, dict]:
    """
    Recognise a number from a screenshot ROI using a KNN OCR model.

    The image is cropped to the supplied ROI, upscaled, converted to grayscale, blurred,
    thresholded and eroded, and contours are detected and filtered to find digit-like
    regions. Each candidate digit is resized to the standard template size and
    classified with the provided KNN model.

    Args:
        full_screenshot (np.ndarray): Full screenshot image (BGR color) as returned by
            ``cv.imread``. Do not pass a grayscale image.
        roi (tuple[int, int, int, int]): ROI coordinates as (x1, y1, x2, y2).
        ocr_model (cv.ml.KNearest): A trained OpenCV KNearest model exposing ``findNearest``.
        debug (bool, optional): When True, return debug artifacts (thresholded and eroded
            images plus the digit ROIs) alongside the recognised value. Defaults to False.
        preprocess_args (dict, optional): Arguments to pass to ``preprocess_roi`` for
            customising preprocessing. Defaults to None.

    Raises:
        InvalidImageError: If the input image is None or ROI is invalid.
        ModelLoadError: If the provided OCR model is not valid.
        OCRError: If classification produces invalid results.
        NoDigitsFoundError: If no digit-like contours were detected in the ROI (when not
            running in debug mode).

    Returns:
        int: The recognised integer when ``debug`` is False.
        tuple[int | None, dict]: When ``debug`` is True, returns a pair ``(value, debug_data)``
            where ``value`` is the recognised integer (or ``None`` if no digits were found) and
            ``debug_data`` is a dict with keys:
                - 'threshold': numpy.ndarray (thresholded image)
                - 'eroded': numpy.ndarray (eroded image)
                - 'digit_rois': list[numpy.ndarray] (resized digit images sent to the model)
    """
    # Validate input image
    if full_screenshot is None:
        raise InvalidImageError("Input image is invalid or cannot be processed - check the image path, format and cv.imread result")

    # Preprocess the ROI and get candidate digit ROIs
    if preprocess_args is None:
        preprocess_args = {}
    pre = preprocess_roi(full_screenshot, roi, **preprocess_args)
    thresh = pre['thresh']
    eroded_thresh = pre['eroded']
    candidates = pre['candidates']

    if debug:
        save_debug_image("debug_threshold_image.png", thresh)
        save_debug_image("debug_eroded_image.png", eroded_thresh)

    # Filter and sort candidates (already filtered in preprocess, but keep API clear)
    digit_contours = sorted(candidates, key=lambda item: item[0])

    # Basic validation: ensure the provided OCR model implements the expected API
    if not hasattr(ocr_model, "findNearest"):
        raise ModelLoadError("ocr_model does not implement findNearest(k) — pass a cv.ml.KNearest instance")

    # Recognise digits
    recognised_digits = []
    debug_rois = []
    for _, x, y, w, h, roi in digit_contours:
        # Step 1: Resize the digit's ROI to the standard size the model was trained on.
        digit_resized = cv.resize(roi, (STANDARD_SIZE), interpolation=cv.INTER_CUBIC)
        
        # Step 2: Prepare the sample. The KNN model expects a 1D array (feature vector)
        # of type float32 for each sample.
        sample = np.array([digit_resized.flatten().astype(np.float32)])
        if debug:
            debug_rois.append(digit_resized.copy())
            
        # Step 3: Classify the digit using the OCR model.
        _ret, result, _neighbours, _dist = ocr_model.findNearest(sample, k=5)
        if result is None or np.isnan(result).any():
            raise OCRError("KNN returned invalid result for a digit")
        
        # Step 4: Convert the classification result (a float) to a string and collect it.
        recognised_digit = str(int(result[0][0]))
        recognised_digits.append(recognised_digit)
        
        logger.debug(f"Recognised digit component: {recognised_digit}")

    if not recognised_digits:
        if debug:
            return None, {'threshold': thresh, 'eroded': eroded_thresh, 'digit_rois': debug_rois}
        raise NoDigitsFoundError("No digit-like contours were found in the ROI.")

    recognized_value = int(''.join(recognised_digits))
    
    logger.debug(f"Final recognised value: {recognized_value}")
    
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
    logger.debug(f"Saved debug image: {result}")