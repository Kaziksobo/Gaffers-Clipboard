"""Run ad-hoc OCR experiments against a single image ROI.

Examples:
    uv run python scripts/ocr_workbench.py \
        --image tests/fixtures/screenshots/player_performance_12.png \
        --roi 1238,822,1281,846

    uv run python scripts/ocr_workbench.py \
        --image tests/fixtures/screenshots/match_overview_2.png \
        --roi 890,609,938,634 \
        --debug --erode-iterations 1
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2 as cv

from src import ocr
from src.contracts.ocr import OCRPreprocessArgs
from src.exceptions import (
    InvalidImageError,
    ModelLoadError,
    NoDigitsFoundError,
    OCRError,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_roi(value: str) -> tuple[int, int, int, int]:
    """Parse ROI text in x1,y1,x2,y2 format."""
    values = [part.strip() for part in value.split(",") if part.strip()]
    if len(values) != 4:
        raise argparse.ArgumentTypeError(
            "ROI must contain exactly 4 comma-separated integers: x1,y1,x2,y2"
        )

    try:
        x1, y1, x2, y2 = (int(number) for number in values)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "ROI must contain integers only: x1,y1,x2,y2"
        ) from exc

    if x1 >= x2 or y1 >= y2:
        raise argparse.ArgumentTypeError("ROI bounds must satisfy x1 < x2 and y1 < y2")
    return x1, y1, x2, y2


def parse_kernel(value: str) -> tuple[int, int]:
    """Parse kernel text in width,height format."""
    values = [part.strip() for part in value.split(",") if part.strip()]
    if len(values) != 2:
        raise argparse.ArgumentTypeError(
            "Kernel must contain exactly 2 comma-separated integers: width,height"
        )

    try:
        width, height = (int(number) for number in values)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Kernel must contain integers only: width,height"
        ) from exc

    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("Kernel values must be positive integers")
    return width, height


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for OCR experiments."""
    parser = argparse.ArgumentParser(
        description="Recognise a number from a single screenshot ROI.",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Path to a screenshot image (absolute or project-relative).",
    )
    parser.add_argument(
        "--roi",
        required=True,
        type=parse_roi,
        help="Region of interest as x1,y1,x2,y2.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode and emit OCR debug metadata.",
    )
    parser.add_argument(
        "--scale",
        type=int,
        help="Override ROI upscale factor used in preprocessing.",
    )
    parser.add_argument(
        "--blur-kernel",
        type=parse_kernel,
        help="Override Gaussian blur kernel as width,height.",
    )
    parser.add_argument(
        "--erode-kernel",
        type=parse_kernel,
        help="Override erosion kernel as width,height.",
    )
    parser.add_argument(
        "--erode-iterations",
        type=int,
        help="Override erosion iteration count.",
    )
    parser.add_argument(
        "--min-h",
        type=int,
        help="Override minimum digit contour height.",
    )
    parser.add_argument(
        "--min-w",
        type=int,
        help="Override minimum digit contour width.",
    )
    return parser


def resolve_image_path(image_arg: str) -> Path:
    """Resolve an image path from CLI input to an absolute project path."""
    image_path = Path(image_arg)
    if not image_path.is_absolute():
        image_path = PROJECT_ROOT / image_path
    return image_path


def build_preprocess_args(args: argparse.Namespace) -> OCRPreprocessArgs:
    """Construct preprocess override arguments from CLI options."""
    preprocess_args: OCRPreprocessArgs = {}

    if args.scale is not None:
        preprocess_args["scale"] = args.scale
    if args.blur_kernel is not None:
        preprocess_args["blur_kernel"] = args.blur_kernel
    if args.erode_kernel is not None:
        preprocess_args["erode_kernel"] = args.erode_kernel
    if args.erode_iterations is not None:
        preprocess_args["erode_iterations"] = args.erode_iterations
    if args.min_h is not None:
        preprocess_args["min_h"] = args.min_h
    if args.min_w is not None:
        preprocess_args["min_w"] = args.min_w

    return preprocess_args


def main() -> int:
    """Load a screenshot ROI and run OCR recognition with optional debug mode."""
    parser = build_parser()
    args = parser.parse_args()

    image_path = resolve_image_path(args.image)
    if not image_path.exists() or not image_path.is_file():
        print(f"Image path does not exist or is not a file: {image_path}")
        return 1

    screenshot_image = cv.imread(str(image_path))
    if screenshot_image is None:
        print(f"OpenCV failed to decode image: {image_path}")
        return 1

    try:
        ocr_model = ocr.load_ocr_model()
    except (FileNotFoundError, ModelLoadError) as exc:
        print(f"Unable to load OCR model: {exc}")
        return 1

    preprocess_args = build_preprocess_args(args)

    try:
        recognised = ocr.recognise_number(
            full_screenshot=screenshot_image,
            roi=args.roi,
            ocr_model=ocr_model,
            debug=args.debug,
            preprocess_args=preprocess_args,
        )
    except (InvalidImageError, NoDigitsFoundError, OCRError) as exc:
        print(f"OCR failed: {exc}")
        return 1

    if args.debug:
        recognised_number, debug_data = recognised
        print(f"Recognised number: {recognised_number}")
        print(f"Digit ROI count: {len(debug_data['digit_rois'])}")
        print(f"Debug images saved to: {PROJECT_ROOT / 'logs' / 'ocr_debug'}")
    else:
        print(f"Recognised number: {recognised}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
