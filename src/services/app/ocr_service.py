"""
OCRService - screenshot-to-stats OCR orchestration.

This module defines `OCRService`, a UI-agnostic service that loads and caches
the OCR model, reads coordinate configuration, scales ROIs to the active screen
resolution, and extracts match/player statistics from screenshots.

Responsibilities:
- Lazily load and cache the OCR model for reuse.
- Load and validate ROI coordinates from `config/coordinates.json`.
- Run OCR over match overview, player performance, and player-attribute regions.
- Normalize OCR outputs into numeric values (`int`/`float`), falling back to `None`.
- Raise domain-specific errors for missing/corrupt configuration and screenshots.

The service focuses on extraction orchestration and error boundaries; persistence
and UI presentation are handled by higher-level services/controllers.
"""

import json
import logging
from pathlib import Path
from typing import TypeGuard, cast

import cv2 as cv
import numpy as np

from src import ocr
from src.contracts.backend import (
    OCRFlatStats,
    OCRStatsResult,
    ROIBounds,
    ROIMap,
)
from src.contracts.coordinates import (
    NormalizedCoordinates,
    PixelCoordinateNode,
    PixelCoordinates,
)
from src.contracts.ocr import OCRPreprocessArgs
from src.exceptions import ConfigurationError, ScreenshotError
from src.utils import get_screen_resolution, scale_coordinates

logger = logging.getLogger(__name__)


class OCRService:
    """Provide OCR-driven stat and attribute extraction services for screenshots.

    OCRService loads shared configuration and OCR models, then exposes focused
    helpers for turning game screenshots into structured statistic dictionaries.
    """

    def __init__(self, project_root: Path) -> None:
        """Initialize the OCR service with the project root for config access.

        Args:
            project_root (Path): Root directory of the project used to locate
                OCR-related configuration files and resources.
        """
        self.project_root: Path = project_root
        self._ocr_model: cv.ml.KNearest | None = None

    # ----------------- Public OCR Entry Points -----------------

    def detect_stats(
        self, latest_screenshot_path: Path, is_player: bool, is_goalkeeper: bool = False
    ) -> OCRStatsResult:
        """Run OCR over a screenshot and return parsed match or player statistics.

        Load and scale ROI coordinates from configuration, read the provided screenshot,
        resolve the target stat screen (match overview, outfield performance, or
        goalkeeper performance), and execute OCR for each configured ROI.

        Args:
            latest_screenshot_path (Path): Path to the screenshot image to process.
            is_player (bool): True to process player-performance stats; False to
                process match-overview stats.
            is_goalkeeper (bool, optional): When `is_player` is True, selects
                goalkeeper-performance coordinates. Defaults to False.

        Raises:
            ConfigurationError: If coordinates configuration is missing or invalid.
            ScreenshotError: If OpenCV cannot read or decode the screenshot file.
            FileNotFoundError: If the specified screenshot file does not exist.
            ModelLoadError: If the OCR model fails to load properly.
            OSError: For other I/O related issues when accessing the screenshot file.
            TypeError: If the loaded screenshot is not a valid image format that
                       OpenCV can process.

        Returns:
            OCRStatsResult: Parsed statistics mapping. Returns nested team mappings for
                            match overview and a flat stat mapping for player modes.
                            Unreadable/missing stats are returned as None.
        """
        logger.info("Starting OCR (player mode: %s)", is_player)

        # --- Load Configurations ---
        coordinates = self._load_scaled_coordinates()

        # --- Initialize Engine & Load Image ---
        ocr_model = self._get_ocr_model()
        screenshot_image = cv.imread(str(latest_screenshot_path))

        if screenshot_image is None:
            raise ScreenshotError(
                f"OpenCV failed to decode image at {latest_screenshot_path}. "
                "File may be corrupted or locked."
            )

        decimal_stats = ["xg", "distance_covered", "distance_sprinted"]
        debug = False
        results: OCRStatsResult = {}

        # --- Determine Target Screen ---
        if not is_player:
            target_screen = "match_overview"
        elif is_goalkeeper:
            target_screen = "gk_performance"
        else:
            target_screen = "player_performance"

        screen_data = coordinates.get(target_screen)
        if not screen_data:
            logger.warning(
                "No coordinates found in JSON for screen: '%s'",
                target_screen,
            )
            return results

        logger.debug("Processing target screen: %s", target_screen)

        # --- Route and Execute ---
        # Match overview has nested dictionaries, while player stats are flat
        if target_screen == "match_overview":
            if not self._is_coordinate_branch(screen_data):
                logger.warning(
                    "Invalid coordinates structure for screen '%s'.",
                    target_screen,
                )
                return results

            for team_name, team_data in screen_data.items():
                logger.debug("Processing team: %s", team_name)

                if not self._is_roi_map(team_data):
                    logger.warning(
                        "Invalid ROI map for team '%s'. Skipping.",
                        team_name,
                    )
                    continue

                results[team_name] = self._process_roi_dict(
                    team_data,
                    decimal_stats,
                    screenshot_image,
                    ocr_model,
                    debug,
                )
        else:
            if not self._is_roi_map(screen_data):
                logger.warning(
                    "Invalid ROI map for screen '%s'.",
                    target_screen,
                )
                return results

            results = self._process_roi_dict(
                screen_data,
                decimal_stats,
                screenshot_image,
                ocr_model,
                debug,
            )

        return results

    def detect_player_attributes(
        self,
        latest_screenshot_path: Path,
        is_goalkeeper: bool = False,
        is_first_page: bool = True,
    ) -> OCRFlatStats:
        """Detect and extract player attribute values from a screenshot.

        Load player-attribute coordinates, choose the correct coordinate subset
        (goalkeeper or outfield page), and run OCR over each configured ROI.
        Attribute values are parsed as integers; unreadable values are returned
        as None.

        Args:
            latest_screenshot_path (Path): Path to the screenshot to process.
            is_goalkeeper (bool, optional): True for goalkeeper attributes.
                Defaults to False.
            is_first_page (bool, optional): For outfield attributes, True for
                page one and False for page two. Defaults to True.

        Raises:
            ConfigurationError: If coordinates configuration is missing or invalid.
            ScreenshotError: If OpenCV cannot read or decode the screenshot file.
            FileNotFoundError: If the specified screenshot file does not exist.
            ModelLoadError: If the OCR model fails to load properly.
            OSError: For other I/O related issues when accessing the screenshot file.
            TypeError: If the loaded screenshot is not a valid image format that
                       OpenCV can process.

        Returns:
            OCRFlatStats: Parsed attribute values keyed by attribute name.
        """
        logger.info(
            "Starting Attribute OCR (GK: %s, First Page: %s)",
            is_goalkeeper,
            is_first_page,
        )

        # --- Load Configurations ---
        coordinates = self._load_scaled_coordinates()

        # --- Initialize Engine & Load Image ---
        ocr_model = self._get_ocr_model()
        screenshot_image = cv.imread(str(latest_screenshot_path))

        if screenshot_image is None:
            raise ScreenshotError(
                f"OpenCV failed to decode image at {latest_screenshot_path}. "
                "File may be corrupted."
            )

        debug = False
        results: OCRFlatStats = {}

        # --- O(1) Dictionary Targeting ---
        # Navigate directly to the required node instead of looping through items
        target_position = (
            "gk" if is_goalkeeper else "outfield_1" if is_first_page else "outfield_2"
        )

        player_attributes_data = coordinates.get("player_attributes")
        if not self._is_coordinate_branch(player_attributes_data):
            logger.warning("No OCR coordinates found for player_attributes node.")
            return results

        target_stats = player_attributes_data.get(target_position)
        if not self._is_roi_map(target_stats):
            logger.warning(
                "No OCR coordinates found for player attributes -> %s",
                target_position,
            )
            return results

        # --- Execute OCR and Safe Casting ---
        return self._process_roi_dict(
            data_dict=target_stats,
            decimal_stats=[],
            screenshot_image=screenshot_image,
            ocr_model=ocr_model,
            debug=debug,
            preprocess_args={"erode_iterations": 1},
        )

    # ----------------- Configuration and Model Loading -----------------

    def _load_scaled_coordinates(self) -> PixelCoordinates:
        """Load and scale ROI coordinates from the JSON configuration file.

        Resolve the configured coordinates path, validate and parse the JSON, then
        scale normalized values to the current screen resolution for OCR use.

        Raises:
            ConfigurationError: If the coordinates file is missing or contains
                invalid JSON.
            OSError: If there are issues accessing the coordinates file.
            TypeError: If the loaded JSON structure does not match expected formats for
                       coordinates.
            FileNotFoundError: If the coordinates file does not exist.
            ModelLoadError: If the OCR model fails to load properly,
                            which may be necessary for validating coordinate structures
                            that depend on model-specific formats.

        Returns:
            PixelCoordinates: A dictionary of screen-specific, pixel-scaled ROI
                coordinates ready for OCR operations.
        """
        coordinates_path = self.project_root / "config" / "coordinates.json"
        if not coordinates_path.exists():
            raise ConfigurationError("Coordinates configuration file is missing.")

        try:
            with Path.open(coordinates_path) as f:
                raw_coordinates = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                "Coordinates configuration file is corrupt."
            ) from e

        # Scale normalised 0-1 coordinates to absolute pixels for the current screen
        screen_w, screen_h = get_screen_resolution()
        normalized_coordinates = cast(NormalizedCoordinates, raw_coordinates)
        return scale_coordinates(normalized_coordinates, screen_w, screen_h)

    def _get_ocr_model(self) -> cv.ml.KNearest:
        """Return a cached OCR model instance, loading it on first use.

        Lazily initializes the underlying OCR model to avoid repeated load
        costs across multiple stat or attribute extraction calls.

        Returns:
            cv.ml.KNearest: The shared KNearest OCR model instance.
        """
        if self._ocr_model is None:
            logger.info("Loading OCR model into OCRService cache")
            self._ocr_model = ocr.load_ocr_model()
        return self._ocr_model

    # ----------------- Coordinate Shape Guards -----------------

    @staticmethod
    def _is_roi_bounds(node: object) -> TypeGuard[ROIBounds]:
        """Validate that *node* represents a single ROI bounds mapping.

        This helper checks for a dictionary with integer ``x1``, ``y1``, ``x2``,
        and ``y2`` keys and is used to distinguish leaf ROI nodes from branches.
        """
        if not isinstance(node, dict):
            return False

        node_map = cast(dict[str, object], node)
        x1 = node_map.get("x1")
        y1 = node_map.get("y1")
        x2 = node_map.get("x2")
        y2 = node_map.get("y2")
        return all(isinstance(value, int) for value in (x1, y1, x2, y2))

    @staticmethod
    def _is_coordinate_branch(
        node: object,
    ) -> TypeGuard[dict[str, PixelCoordinateNode]]:
        """Identify coordinate-branch nodes that contain nested ROI mappings.

        A coordinate branch is any dictionary that is not a single ROI bounds
        mapping, and typically represents groupings such as teams or screens.
        """
        return isinstance(node, dict) and not OCRService._is_roi_bounds(node)

    @staticmethod
    def _is_roi_map(node: object) -> TypeGuard[ROIMap]:
        """Determine whether a node is a mapping of stat keys to ROI bounds.

        An ROI map is a coordinate-branch dictionary in which every value is a
        valid ROI bounds mapping for a single region of interest.
        """
        if not OCRService._is_coordinate_branch(node):
            return False
        return all(OCRService._is_roi_bounds(value) for value in node.values())

    # ----------------- OCR Processing Helpers -----------------

    @staticmethod
    def _process_roi_dict(
        data_dict: ROIMap,
        decimal_stats: list[str],
        screenshot_image: np.ndarray,
        ocr_model: cv.ml.KNearest,
        debug: bool = False,
        preprocess_args: OCRPreprocessArgs | None = None,
    ) -> OCRFlatStats:
        """Run OCR for a set of ROIs and convert recognised values into numeric stats.

        Iterates over each configured region, handles OCR failures gracefully, and
        normalizes recognised strings into integers or one-decimal-place floats.

        Args:
            data_dict (ROIMap): Mapping of stat names to ROI coordinate
                dictionaries containing "x1", "y1", "x2", and "y2" keys.
            decimal_stats (list[str]): Names of stats that should be treated as
                one-decimal-place floats instead of integers.
            screenshot_image (np.ndarray): Screenshot image array used as the
                source for region extraction and OCR.
            ocr_model (cv.ml.KNearest): OCR model used to recognise numeric text
                inside each ROI.
            debug (bool, optional): When True, expects debug-style OCR outputs and
                extracts the primary value from a tuple. Defaults to False.
            preprocess_args (OCRPreprocessArgs | None, optional): Additional
                preprocessing options forwarded to ``ocr.recognise_number``.
                Defaults to None.

        Returns:
            OCRFlatStats: Dictionary mapping stat names to parsed numeric values,
            or None when OCR fails, ROIs are invalid, or parsing is not possible.
        """
        if preprocess_args is None:
            preprocess_args = {}

        parsed_data: OCRFlatStats = {}
        for stat_name, roi in data_dict.items():
            try:
                stat_roi = (roi["x1"], roi["y1"], roi["x2"], roi["y2"])
            except KeyError as e:
                logger.warning(
                    "Invalid ROI for stat '%s': missing key %s. "
                    "Defaulting to empty field.",
                    stat_name,
                    e,
                )
                parsed_data[stat_name] = None
                continue

            logger.debug("OCRing %s at %s", stat_name, stat_roi)

            try:
                recognised_data = ocr.recognise_number(
                    full_screenshot=screenshot_image,
                    roi=stat_roi,
                    ocr_model=ocr_model,
                    preprocess_args=preprocess_args,
                    debug=debug,
                )
            except Exception as e:
                logger.warning(
                    "OCR failed for stat '%s' at %s: %s. Defaulting to empty field.",
                    stat_name,
                    stat_roi,
                    e,
                )
                parsed_data[stat_name] = None
                continue

            recognised_number = recognised_data[0] if debug else recognised_data

            if recognised_number is None:
                parsed_data[stat_name] = None
                continue

            # ocr.recognise_number returns number as a string with no decimal point,
            # e.g. 0.5 is returned as 05, convert it to a float if in decimal stats
            # otherwise convert to int.
            if stat_name in decimal_stats:
                try:
                    parsed_data[stat_name] = float(str(recognised_number)) / 10
                except (TypeError, ValueError):
                    logger.warning(
                        "Failed to parse decimal stat '%s' from OCR output "
                        "'%s'. Defaulting to empty field.",
                        stat_name,
                        recognised_number,
                    )
                    parsed_data[stat_name] = None
            else:
                try:
                    parsed_data[stat_name] = int(str(recognised_number))
                except (TypeError, ValueError):
                    logger.warning(
                        "Failed to parse integer stat '%s' from OCR output "
                        "'%s'. Defaulting to empty field.",
                        stat_name,
                        recognised_number,
                    )
                    parsed_data[stat_name] = None

        return parsed_data
