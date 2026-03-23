from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Colors:
    background: str = "#1e1e1e"
    entry_fg: str = "#1e1e1e"
    button_fg: str = "#3c3c3c"
    button_bg: str = "#1e1e1e"
    dropdown_fg: str = "#3c3c3c"
    primary_text: str = "#f0f0f0"
    secondary_text: str = "#C5C5C5"
    accent: str = "#00bfff"
    error: str = "#ff4c4c"
    warning: str = "#ffcc00"
    success: str = "#4caf50"
    info: str = "#2196f3"


@dataclass(frozen=True)
class Fonts:
    title: Tuple = ("Segoe UI", 48, "bold")
    body: Tuple = ("Segoe UI", 24)
    button: Tuple = ("Segoe UI", 28, "bold")
    sidebar_body: Tuple = ("Segoe UI", 14)
    sidebar_button: Tuple = ("Segoe UI", 14, "bold")


@dataclass(frozen=True)
class Theme:
    colors: Colors = Colors()
    fonts: Fonts = Fonts()


# Instance for attribute access: theme.colors.background
theme = Theme()