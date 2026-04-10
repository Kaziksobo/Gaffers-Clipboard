"""Typed contracts for OCR preprocessing and debug payloads."""

from typing import TypedDict

import numpy as np


class OCRPreprocessArgs(TypedDict, total=False):
    """Optional arguments for OCR preprocessing steps."""

    scale: int
    blur_kernel: tuple[int, int]
    erode_kernel: tuple[int, int]
    erode_iterations: int
    min_h: int
    min_w: int


class OCRPreprocessResult(TypedDict):
    """Structured output from ROI preprocessing."""

    resized: np.ndarray
    gray: np.ndarray
    blurred: np.ndarray
    thresh: np.ndarray
    eroded: np.ndarray
    contours: list[np.ndarray]
    candidates: list[tuple[int, int, int, int, int, np.ndarray]]


class OCRDebugData(TypedDict):
    """Debug artifacts returned alongside recognised OCR values."""

    threshold: np.ndarray
    eroded: np.ndarray
    digit_rois: list[np.ndarray]
