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