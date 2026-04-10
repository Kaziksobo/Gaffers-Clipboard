"""OCR primitives for numeric stat extraction from screenshots.

This module provides the low-level OCR pipeline used across the application.
It focuses on model loading, image-region preprocessing, digit recognition,
and optional debug artifact persistence.

Processing flow:
- ``load_ocr_model`` loads the trained OpenCV KNN model from disk.
- ``preprocess_roi`` validates and transforms a region of interest into
    thresholded contour candidates.
- ``recognise_number`` classifies ordered digit candidates and returns the
    assembled numeric string.
- ``save_debug_image`` writes intermediate images for troubleshooting.

Typed contracts for preprocessing options and debug payloads are defined in
``src.contracts.ocr``.

Error behavior is explicit and domain-specific:
- ``InvalidImageError`` for invalid images or ROI bounds.
- ``ModelLoadError`` for missing or malformed OCR model usage.
- ``NoDigitsFoundError`` when no candidate digits are detected.
- ``OCRError`` for invalid model inference outputs.
"""

import logging
from pathlib import Path

import cv2 as cv
import numpy as np

from src.contracts.ocr import OCRDebugData, OCRPreprocessArgs, OCRPreprocessResult
from src.exceptions import (
    InvalidImageError,
    ModelLoadError,
    NoDigitsFoundError,
    OCRError,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent

STANDARD_SIZE = (30, 35)


def load_ocr_model() -> cv.ml.KNearest:
    """Load the trained KNN OCR model from the project model directory.

    The model is expected at ``model/knn_ocr_model.yml`` and is loaded through
    OpenCV ``FileStorage`` into a ``cv.ml.KNearest`` instance.

    Raises:
        FileNotFoundError: If the model file does not exist.
        ModelLoadError: If the file cannot be opened, is empty, or cannot be
            parsed into a usable KNN model.

    Returns:
        cv.ml.KNearest: Loaded OpenCV KNN model ready for inference.
    """
    # Specifies the file path of the model
    model_path = PROJECT_ROOT / "model" / "knn_ocr_model.yml"
    if not model_path.exists():
        raise FileNotFoundError(f"OCR model file not found at {model_path}")

    knn = cv.ml.KNearest_create()
    # Open the model file for reading using OpenCV's FileStorage
    fs = cv.FileStorage(str(model_path), cv.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise ModelLoadError(
            f"FileStorage failed to open OCR model file at {model_path}"
        )
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
    min_w: int = 8,
) -> OCRPreprocessResult:
    """Extract and preprocess an ROI for digit contour detection.

    The ROI is validated, upscaled, converted to grayscale, blurred, thresholded,
    and eroded before contour extraction. Candidate digit regions are filtered by
    minimum width and height thresholds.

    Args:
        full_screenshot (np.ndarray): Full screenshot image in BGR format.
        roi (tuple[int, int, int, int]): Region bounds as ``(x1, y1, x2, y2)``.
        scale (int, optional): Upscaling factor applied before preprocessing.
            Defaults to 4.
        blur_kernel (tuple[int, int], optional): Gaussian blur kernel size.
            Defaults to ``(5, 5)``.
        erode_kernel (tuple[int, int], optional): Erosion kernel size.
            Defaults to ``(3, 3)``.
        erode_iterations (int, optional): Number of erosion passes.
            Defaults to 2.
        min_h (int, optional): Minimum candidate contour height in pixels.
            Defaults to 18.
        min_w (int, optional): Minimum candidate contour width in pixels.
            Defaults to 8.

    Raises:
        InvalidImageError: If the source image is missing, ROI bounds are invalid,
            or the cropped ROI is empty.

    Returns:
        OCRPreprocessResult: Intermediate images, detected contours, and filtered
        digit candidates used by OCR recognition.
    """
    if full_screenshot is None:
        raise InvalidImageError("Input image is None")

    x1, y1, x2, y2 = roi
    h_img, w_img = full_screenshot.shape[:2]
    if not (0 <= x1 < x2 <= w_img and 0 <= y1 < y2 <= h_img):
        logger.warning(f"ROI {roi} out of bounds for image {h_img}x{w_img}")
        raise InvalidImageError(
            f"ROI {roi} out of bounds for image shape {(h_img, w_img)}"
        )

    roi_image = full_screenshot[y1:y2, x1:x2]
    if roi_image.size == 0 or roi_image.shape[0] == 0 or roi_image.shape[1] == 0:
        raise InvalidImageError("Cropped ROI is empty")

    # Step 1: Upscale the image. This makes the digits larger and clearer,
    # improving the accuracy of subsequent steps like contour detection.
    new_width = max(1, int(roi_image.shape[1] * scale))
    new_height = max(1, int(roi_image.shape[0] * scale))
    resized = cv.resize(
        roi_image, (new_width, new_height), interpolation=cv.INTER_CUBIC
    )

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
            roi_img = thresh[y : y + h, x : x + w]
            candidates.append((centre_x, x, y, w, h, roi_img))

    return {
        "resized": resized,
        "gray": gray,
        "blurred": blurred,
        "thresh": thresh,
        "eroded": eroded,
        "contours": contours,
        "candidates": candidates,
    }


def recognise_number(
    full_screenshot: np.ndarray,
    roi: tuple[int, int, int, int],
    ocr_model: cv.ml.KNearest,
    debug: bool = False,
    preprocess_args: OCRPreprocessArgs | None = None,
) -> str | tuple[str | None, OCRDebugData]:
    """Recognise a numeric string from a screenshot ROI using the KNN OCR model.

    The function preprocesses the ROI, sorts candidate digit contours from left to
    right, resizes each candidate to the training template size, and classifies
    each digit with ``findNearest``.

    Args:
        full_screenshot (np.ndarray): Full screenshot image in BGR format.
        roi (tuple[int, int, int, int]): Region bounds as ``(x1, y1, x2, y2)``.
        ocr_model (cv.ml.KNearest): Trained OpenCV KNN model used for digit
            classification.
        debug (bool, optional): When True, returns debug artifacts alongside the
            recognised value. Defaults to False.
        preprocess_args (OCRPreprocessArgs | None, optional): Optional keyword
            overrides forwarded to ``preprocess_roi``. Defaults to None.

    Raises:
        InvalidImageError: If the input image is invalid.
        ModelLoadError: If ``ocr_model`` does not expose the expected API.
        OCRError: If model inference returns invalid classification output.
        NoDigitsFoundError: If no digit candidates are found and debug mode is
            disabled.

    Returns:
        str | tuple[str | None, OCRDebugData]: Recognised numeric text. In debug
        mode returns ``(value, debug_data)``, where ``value`` can be ``None`` when
        no digits are found.
    """
    # Validate input image
    if full_screenshot is None:
        raise InvalidImageError(
            "Input image is invalid or cannot be processed - "
            "check the image path, format, and cv.imread result"
        )

    # Preprocess the ROI and get candidate digit ROIs
    scale = preprocess_args.get("scale", 4) if preprocess_args is not None else 4
    blur_kernel = (
        preprocess_args.get("blur_kernel", (5, 5))
        if preprocess_args is not None
        else (5, 5)
    )
    erode_kernel = (
        preprocess_args.get("erode_kernel", (3, 3))
        if preprocess_args is not None
        else (3, 3)
    )
    erode_iterations = (
        preprocess_args.get("erode_iterations", 2) if preprocess_args is not None else 2
    )
    min_h = preprocess_args.get("min_h", 18) if preprocess_args is not None else 18
    min_w = preprocess_args.get("min_w", 8) if preprocess_args is not None else 8

    pre = preprocess_roi(
        full_screenshot,
        roi,
        scale=scale,
        blur_kernel=blur_kernel,
        erode_kernel=erode_kernel,
        erode_iterations=erode_iterations,
        min_h=min_h,
        min_w=min_w,
    )
    thresh = pre["thresh"]
    eroded_thresh = pre["eroded"]
    candidates = pre["candidates"]

    if debug:
        save_debug_image("debug_threshold_image.png", thresh)
        save_debug_image("debug_eroded_image.png", eroded_thresh)

    # Filter and sort candidates (already filtered in preprocess, but keep API clear)
    digit_contours = sorted(candidates, key=lambda item: item[0])

    # Basic validation: ensure the provided OCR model implements the expected API
    if not hasattr(ocr_model, "findNearest"):
        raise ModelLoadError(
            "ocr_model does not implement findNearest(k) - "
            "pass a cv.ml.KNearest instance"
        )

    # Recognise digits
    recognised_digits = []
    debug_rois = []
    for _, _x, _y, _w, _h, digit_roi in digit_contours:
        # Step 1: Resize the digit's ROI to the standard size the model was trained on.
        digit_resized = cv.resize(
            digit_roi, (STANDARD_SIZE), interpolation=cv.INTER_CUBIC
        )

        # Step 2: Prepare the sample. The KNN model expects a 1D array (feature vector)
        # of type float32 for each sample.
        sample = np.array([digit_resized.flatten().astype(np.float32)])
        if debug:
            debug_rois.append(digit_resized.copy())

        # Step 3: Classify the digit using the OCR model.
        _ret, result, _neighbours, _dist = ocr_model.findNearest(sample, k=5)
        if result is None or np.isnan(result).any():
            raise OCRError("KNN returned invalid result for a digit")

        # Step 4: Convert the classification result (a float) to a string
        # and collect it.
        recognised_digit = str(int(result[0][0]))
        recognised_digits.append(recognised_digit)

        logger.debug(f"Recognised digit component: {recognised_digit}")

    if not recognised_digits:
        if debug:
            return None, {
                "threshold": thresh,
                "eroded": eroded_thresh,
                "digit_rois": debug_rois,
            }
        raise NoDigitsFoundError("No digit-like contours were found in the ROI.")

    recognized_value = "".join(recognised_digits)

    logger.debug(f"Final recognised value: {recognized_value}")

    if debug:
        return recognized_value, {
            "threshold": thresh,
            "eroded": eroded_thresh,
            "digit_rois": debug_rois,
        }
    return recognized_value


def save_debug_image(filename: str, image: np.ndarray) -> None:
    """Persist a debug image to the project-level debug images directory.

    Creates ``debug_images`` under the project root if needed and attempts to
    write the provided image file, logging success or failure.

    Args:
        filename (str): Output file name, including extension.
        image (np.ndarray): Image array to write to disk.
    """
    debug_dir = PROJECT_ROOT / "debug_images"
    debug_dir.mkdir(parents=True, exist_ok=True)

    filepath = debug_dir / filename
    try:
        cv.imwrite(str(filepath), image)
        logger.debug(f"Saved debug image: {filepath}")
    except Exception as e:
        logger.error(f"Failed to save debug image {filepath}: {e}")
