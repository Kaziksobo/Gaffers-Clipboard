"""Shared utility helpers for screen coordinates and value normalization."""

import logging
import string
from datetime import datetime
from typing import TypeGuard

import pyautogui

from src.contracts.coordinates import (
    NormalizedCoordinateNode,
    NormalizedCoordinates,
    NormalizedROIBounds,
    PixelCoordinateNode,
    PixelCoordinates,
)

logger = logging.getLogger(__name__)

COMPETITION_ACRONYMS = frozenset(["UEFA", "FIFA", "MLS", "EFL", "FA", "DFB", "DFL"])


# --------------- Screen-resolution helpers ---------------


def get_screen_resolution() -> tuple[int, int]:
    """Return the primary monitor's resolution in pixels as ``(width, height)``.

    Uses *pyautogui* which respects DPI scaling on Windows, so the value
    returned matches what ``pyautogui.screenshot()`` actually captures.

    Returns:
        Tuple[int, int]: ``(width, height)`` of the primary display.
    """
    size = pyautogui.size()
    logger.debug(f"Detected screen resolution: {size.width}x{size.height}")
    return (size.width, size.height)


def scale_coordinates(
    coordinates: NormalizedCoordinates,
    screen_width: int,
    screen_height: int,
) -> PixelCoordinates:
    """Scale normalised ROI coordinates to absolute pixel coordinates.

    The function walks the dictionary tree recursively. Any ``dict`` that
    contains all four keys ``x1``, ``y1``, ``x2``, ``y2`` (with float values
    between 0 and 1) is treated as an ROI and its values are multiplied by
    the screen dimensions. All other nodes are passed through unchanged.

    Args:
        coordinates: The full dictionary loaded from ``coordinates.json``
                     (values are 0-1 scale factors).
        screen_width:  Target screen width in pixels.
        screen_height: Target screen height in pixels.

    Returns:
        A **new** dictionary with all ROI values converted to absolute pixel
        coordinates.
    """
    logger.debug(f"Scaling normalised coordinates to {screen_width}x{screen_height}")

    roi_keys = ("x1", "y1", "x2", "y2")

    def _is_normalized_roi(
        node: NormalizedCoordinateNode,
    ) -> TypeGuard[NormalizedROIBounds]:
        """Return True when *node* is a leaf ROI with numeric coordinates."""
        if all(key in node for key in roi_keys):
            return all(isinstance(node[key], (float, int)) for key in roi_keys)
        return False

    def _is_coordinate_branch(
        node: NormalizedCoordinateNode,
    ) -> TypeGuard[dict[str, NormalizedCoordinateNode]]:
        """Return True when *node* is an intermediate tree branch."""
        return not _is_normalized_roi(node)

    def _scale_node(node: NormalizedCoordinateNode) -> PixelCoordinateNode:
        """Recursively scale a single coordinate node."""
        if _is_normalized_roi(node):
            return {
                "x1": round(node["x1"] * screen_width),
                "y1": round(node["y1"] * screen_height),
                "x2": round(node["x2"] * screen_width),
                "y2": round(node["y2"] * screen_height),
            }

        if _is_coordinate_branch(node):
            return {key: _scale_node(value) for key, value in node.items()}

        msg = "Unsupported coordinates node encountered while scaling."
        raise TypeError(msg)

    return {k: _scale_node(v) for k, v in coordinates.items()}


# --------------- Safe type-conversion helpers ---------------


def safe_int_conversion(value: str | int | float | None) -> int | None:
    """Safely converts a value to an integer, returning None if conversion fails.

    Args:
        value (Optional[Union[str, int, float]]): The value to convert.

    Returns:
        Optional[int]: The converted integer, or None if the input is
                       empty, invalid, or None.
    """
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    if isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value:
            return None
        try:
            return int(stripped_value)
        except ValueError:
            return None

    return None


def derive_season(date_str: str) -> str:
    """Derive the football season string from a dd/mm/yy date.

    July (month 7) onward starts a new season.
    E.g. 01/07/29 -> '29/30', 15/01/30 -> '29/30'.
    """
    dt = datetime.strptime(date_str.strip(), "%d/%m/%y")
    year = dt.year % 100
    if dt.month >= 7:
        return f"{year:02d}/{(year + 1) % 100:02d}"
    return f"{(year - 1) % 100:02d}/{year:02d}"


def safe_float_conversion(value: str | int | float | None) -> float | None:
    """Safely converts a value to a float, returning None if conversion fails.

    Args:
        value (Optional[Union[str, int, float]]): The value to convert.

    Returns:
        Optional[float]: The converted float, or None if the input is
                         empty, invalid, or None.
    """
    if value is None:
        return None

    if isinstance(value, (float, int)):
        return float(value)

    if isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value:
            return None
        try:
            return float(stripped_value)
        except ValueError:
            return None

    return None


# --------------- Name normalization ---------------


def normalize_team_name(target_name: str, reference_names: list[str]) -> str:
    """Normalize a team name by comparing it to a list of reference names.

    The function attempts to find a close match for *target_name* in
    *reference_names* by normalizing both the target and reference names
    (case-insensitive, whitespace-trimmed) and also stripping common football club
    prefixes/suffixes like "FC" and "CF". If a match is found, the original reference
    name is returned; otherwise, the original target name is returned unchanged.

    Args:
        target_name (str): The team name to normalize.
        reference_names (list[str]): A list of reference team names to compare against.

    Raises:
        ValueError: If the target name is empty or invalid.

    Returns:
        str: The normalized team name from the reference list if a match is found,
             or the original target name if no match is found.
    """
    for name in reference_names:
        # Safe normalise both, then strip FC/CF prefixes/suffixes and compare again
        current_normalized = safe_normalize_name(name)
        if not current_normalized:
            continue
        target_normalized = safe_normalize_name(target_name)
        if not target_normalized:
            raise ValueError("Target name must be a non-empty string")
        current_normalized = (
            current_normalized.removeprefix("fc ")
            .removesuffix(" fc")
            .removeprefix("cf ")
            .removesuffix(" cf")
        )
        target_normalized = (
            target_normalized.removeprefix("fc ")
            .removesuffix(" fc")
            .removeprefix("cf ")
            .removesuffix(" cf")
        )
        if current_normalized == target_normalized:
            return name
    return target_name


def capitalize_competition_name(competition: str) -> str:
    """Normalize competition names with special handling for known acronyms.

    This helper capitalizes known competition acronyms fully while title-casing
    all other words to produce consistent display and storage formatting.

    Parentheses are treated as invalid formatting noise for competition labels
    and removed during normalization.

    Args:
        competition (str): The raw competition name to normalize.

    Returns:
        str: The normalized competition name with acronyms uppercased and
                remaining words title-cased.
    """
    sanitized = competition.replace("(", " ").replace(")", " ").strip()
    if not sanitized:
        return ""

    words = sanitized.split()
    capitalized_words = [
        word.upper() if word.upper() in COMPETITION_ACRONYMS else string.capwords(word)
        for word in words
    ]
    return " ".join(capitalized_words)


# --------------- Misc helpers ---------------


def safe_normalize_name(name: str) -> str | None:
    """Safely normalises a loosely-typed name value into a comparable string.

    Non-string or empty/whitespace-only input is treated as missing and returns None.

    Args:
        name: The value to normalise, typically a name-like string.

    Returns:
        A case-insensitive, whitespace-stripped representation of the name, or
        None if the input is not a string or is empty after stripping.
    """
    if not isinstance(name, str):
        return None
    stripped = name.strip()
    return stripped.casefold() if stripped else None
