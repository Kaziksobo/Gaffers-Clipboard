"""Coordinate typing contracts shared across OCR and utility modules."""

from typing import TypedDict


class NormalizedROIBounds(TypedDict):
    """Single OCR region bounds normalized to 0-1 screen space."""

    x1: float
    y1: float
    x2: float
    y2: float


class PixelROIBounds(TypedDict):
    """Single OCR region bounds scaled to absolute screen pixels."""

    x1: int
    y1: int
    x2: int
    y2: int


type NormalizedCoordinateNode = (
    NormalizedROIBounds | dict[str, "NormalizedCoordinateNode"]
)
type PixelCoordinateNode = PixelROIBounds | dict[str, "PixelCoordinateNode"]
type NormalizedCoordinates = dict[str, NormalizedCoordinateNode]
type PixelCoordinates = dict[str, PixelCoordinateNode]
