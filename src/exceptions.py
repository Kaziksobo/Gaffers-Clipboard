"""Application-specific exception hierarchy for Gaffer's Clipboard.

This module defines custom exceptions grouped by subsystem so the app can
signal failures with clear intent instead of relying on generic exceptions.
The hierarchy is organized by concern:

- `GUIError` and subclasses for frame/navigation/configuration issues.
- `OCRError` and subclasses for model/image recognition failures.
- `DataError` and subclasses for validation, duplication, and persistence
    problems.

Design goals:
- Catch broad categories at workflow boundaries while still allowing precise
    handling for specific failure cases.
- Improve log readability by using domain-focused exception names.
- Keep exception classes lightweight and safe to import from any layer.

Typical usage:
- Raise the most specific subclass where the issue is detected.
- Catch category-level base classes (for example, `DataError`) at service or
    controller boundaries to map failures into user-facing alerts or recovery
    flows.
"""


class GUIError(Exception):
    """Base class for GUI-related exceptions."""

    pass


class ScreenshotError(GUIError):
    """Raised when a screenshot operation fails."""

    pass


class FrameNotFoundError(GUIError):
    """Raised when a requested frame is not found."""

    pass


class ConfigurationError(GUIError):
    """Raised when a configuration file is missing or corrupt."""

    pass


class UIPopulationError(GUIError):
    """Raised when a UI frame fails to populate with data."""

    pass


class OCRError(Exception):
    """Base class for OCR-related errors."""

    pass


class ModelLoadError(OCRError):
    """Raised when the OCR model fails to load."""

    pass


class InvalidImageError(OCRError):
    """Raised when the input image is invalid or cannot be processed."""

    pass


class NoDigitsFoundError(OCRError):
    """Raised when no digit-like contours are found in the ROI."""

    pass


class DataError(Exception):
    """Base class for data-related errors."""

    pass


class IncompleteDataError(DataError):
    """Raised when UI buffers are missing required pages or critical context fields."""

    pass


class DataPersistenceError(DataError):
    """Raised when the DataManager fails to save a record due to errors."""

    pass


class DuplicateRecordError(DataError):
    """Raised when attempting to save a record that already exists in the database."""

    pass
