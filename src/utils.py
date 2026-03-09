import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union

import pyautogui

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Screen-resolution helpers
# ---------------------------------------------------------------------------


def get_screen_resolution() -> Tuple[int, int]:
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
    coordinates: Dict[str, Any],
    screen_width: int,
    screen_height: int,
) -> Dict[str, Any]:
    """Convert every normalised ROI rectangle in *coordinates* to absolute
    pixel values for the given *screen_width* × *screen_height*.

    The function walks the dictionary tree recursively.  Any ``dict`` that
    contains **all four** keys ``x1, y1, x2, y2`` (with float values between
    0 and 1) is treated as an ROI and its values are multiplied by the
    screen dimensions.  All other nodes are passed through unchanged.

    Args:
        coordinates: The full dictionary loaded from ``coordinates.json``
                     (values are 0–1 scale factors).
        screen_width:  Target screen width in pixels.
        screen_height: Target screen height in pixels.

    Returns:
        A **new** dictionary with all ROI values converted to absolute pixel
        coordinates.
    """
    logger.debug(
        f"Scaling normalised coordinates to {screen_width}x{screen_height}"
    )

    def _scale_node(obj: Any) -> Any:
        """Recursively scale ROI dicts, pass everything else through."""
        if isinstance(obj, dict):
            # Leaf ROI node – contains the four coordinate keys
            if all(k in obj for k in ("x1", "y1", "x2", "y2")):
                return {
                    "x1": round(obj["x1"] * screen_width),
                    "y1": round(obj["y1"] * screen_height),
                    "x2": round(obj["x2"] * screen_width),
                    "y2": round(obj["y2"] * screen_height),
                }
            # Intermediate container – recurse into children
            return {k: _scale_node(v) for k, v in obj.items()}
        return obj

    return {k: _scale_node(v) for k, v in coordinates.items()}


# ---------------------------------------------------------------------------
# Safe type-conversion helpers
# ---------------------------------------------------------------------------

def safe_int_conversion(value: Optional[Union[str, int, float]]) -> Optional[int]:
    """Safely converts a value to an integer, returning None if conversion fails.
    
    Args:
        value (Optional[Union[str, int, float]]): The value to convert.
        
    Returns:
        Optional[int]: The converted integer, or None if the input is empty, invalid, or None.
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


def safe_float_conversion(value: Optional[Union[str, int, float]]) -> Optional[float]:
    """Safely converts a value to a float, returning None if conversion fails.
    
    Args:
        value (Optional[Union[str, int, float]]): The value to convert.
        
    Returns:
        Optional[float]: The converted float, or None if the input is empty, invalid, or None.
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