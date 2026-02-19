class GUIError(Exception):
    '''Base class for GUI-related exceptions.'''
    pass

class ScreenshotError(GUIError):
    '''Raised when a screenshot operation fails.'''
    pass

class FrameNotFoundError(GUIError):
    '''Raised when a requested frame is not found.'''
    pass

class ConfigurationError(GUIError):
    """Raised when a configuration file is missing or corrupt."""
    pass

class UIPopulationError(GUIError):
    """Raised when a UI frame fails to populate with data."""
    pass


class OCRError(Exception):
    '''Base class for OCR-related errors.'''
    pass

class ModelLoadError(OCRError):
    '''Raised when the OCR model fails to load.'''
    pass

class InvalidImageError(OCRError):
    '''Raised when the input image is invalid or cannot be processed.'''
    pass

class NoDigitsFoundError(OCRError):
    '''Raised when no digit-like contours are found in the ROI.'''
    pass


class DataError(Exception):
    '''Base class for data-related errors.'''
    pass

class IncompleteDataError(DataError):
    """Raised when attempting to save a record but the UI buffers are missing required 
    pages (e.g., page 2 of outfield stats) or critical context fields (name, position)."""
    pass

class DataPersistenceError(DataError):
    """Raised when the DataManager fails to save a record, usually wrapping a 
    Pydantic ValidationError or a file I/O issue."""
    pass