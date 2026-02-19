from typing import Optional, Union

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