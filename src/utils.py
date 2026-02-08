def safe_int_conversion(value: str | int | None) -> int | None:
    """
    Safely converts a value to an integer or returns None when conversion is not possible.

    Args:
        value (str | int | None): The value to convert to an integer.

    Returns:
        int | None: The converted integer, or None if the input is empty, invalid, or None.
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

def safe_float_conversion(value: str | float | None) -> float | None:
    """
    Safely converts a value to a float or returns None when conversion is not possible.

    Args:
        value (str | float | None): The value to convert to a float.

    Returns:
        float | None: The converted float, or None if the input is empty, invalid, or None.
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