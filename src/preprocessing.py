import cv2 as cv
import numpy as np

from ocr import STANDARD_SIZE

def get_stat_roi(image_path, coords) -> np.ndarray:
    '''Get the region of interest (ROI) from the image.

    Args:
        image_path (str): The path to the image file
        coords (tuple[int, int, int, int]): The coordinates of the ROI (x1, y1, x2, y2)

    Returns:
        np.ndarray: The extracted and resized ROI
    '''
    source_image = cv.imread(image_path)
    x1, y1, x2, y2 = coords
    roi = source_image[y1:y2, x1:x2]
    resized_roi = cv.resize(roi, STANDARD_SIZE, interpolation=cv.INTER_CUBIC)
    return resized_roi