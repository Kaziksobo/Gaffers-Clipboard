"""Automated pytest checks for scaled goalkeeper-performance coordinates."""

import json
from pathlib import Path
from typing import cast

import cv2

from src.utils import scale_coordinates

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COORDINATES_PATH = PROJECT_ROOT / "config" / "coordinates.json"
SCREENSHOT_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "screenshots" / "gk_performance.png"
)
OUTPUT_PATH = PROJECT_ROOT / "tests" / "reports" / "coordinates_test_output.png"


def _load_raw_coordinates() -> dict[str, object]:
    """Return unscaled coordinate JSON loaded from disk."""
    with COORDINATES_PATH.open(encoding="utf-8") as file:
        return cast(dict[str, object], json.load(file))


def test_gk_performance_scaled_rois_are_within_fixture_bounds() -> None:
    """Scaled goalkeeper ROIs should be valid and render to an output image."""
    assert COORDINATES_PATH.exists(), f"Missing coordinates file: {COORDINATES_PATH}"
    assert SCREENSHOT_PATH.exists(), f"Missing screenshot fixture: {SCREENSHOT_PATH}"

    screenshot_image = cv2.imread(str(SCREENSHOT_PATH))
    assert screenshot_image is not None, f"Unable to read screenshot: {SCREENSHOT_PATH}"

    height, width = screenshot_image.shape[:2]
    scaled_coordinates = scale_coordinates(
        cast(dict[str, dict[str, dict[str, float | int]]], _load_raw_coordinates()),
        width,
        height,
    )

    gk_rois = cast(
        dict[str, dict[str, int]],
        scaled_coordinates.get("gk_performance", {}),
    )
    assert gk_rois, "No gk_performance coordinates found after scaling."

    annotated_image = screenshot_image.copy()

    for stat_name, roi in gk_rois.items():
        assert set(roi.keys()) == {"x1", "y1", "x2", "y2"}, (
            f"Unexpected ROI keys for '{stat_name}': {sorted(roi.keys())}"
        )

        x1, y1, x2, y2 = roi["x1"], roi["y1"], roi["x2"], roi["y2"]

        assert 0 <= x1 < x2 <= width, (
            f"Invalid x-bounds for '{stat_name}': x1={x1}, x2={x2}, width={width}"
        )
        assert 0 <= y1 < y2 <= height, (
            f"Invalid y-bounds for '{stat_name}': y1={y1}, y2={y2}, height={height}"
        )

        cv2.rectangle(annotated_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            annotated_image,
            f"gk_performance-{stat_name}",
            (x1, max(y1 - 10, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(OUTPUT_PATH), annotated_image), (
        f"Failed to write annotated output image: {OUTPUT_PATH}"
    )
