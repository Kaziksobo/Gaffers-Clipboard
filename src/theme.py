"""Shared UI theme tokens for typography and semantic colors.

This module exposes a single `theme` object (a nested `SimpleNamespace`) used
across view frames and widgets to keep visual styling consistent.

Sections:
- `theme.fonts`: Named font tuples for titles, body text, and button labels.
- `theme.semantic_colors`: Named colors for status feedback and interactive
    hover states.

Keeping these values centralized avoids hard-coded styles in individual UI
components and makes global visual updates straightforward.
"""

from types import SimpleNamespace

theme = SimpleNamespace(
    fonts=SimpleNamespace(
        title=("Segoe UI", 48, "bold"),
        body=("Segoe UI", 24),
        button=("Segoe UI", 28, "bold"),
        sidebar_body=("Segoe UI", 14),
        sidebar_button=("Segoe UI", 14, "bold"),
    ),
    semantic_colors=SimpleNamespace(
        accent="#00bfff",
        error="#ff4c4c",
        warning="#ffcc00",
        success="#4caf50",
        info="#2196f3",
        submit_hover="#4caf50",
        remove_hover="#ff4c4c",
        unsaved_nav_hover="#ffcc00",
    ),
)
