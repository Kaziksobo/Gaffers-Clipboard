"""Modal delay overlay shown during short in-app processing windows."""

from typing import cast

import customtkinter as ctk

from src.contracts.ui import DelayOverlayHostProtocol


def show_delay_overlay(
    parent: ctk.CTk, seconds: int, message: str = "Please wait..."
) -> None:
    """Display a modal overlay with a spinner message during processing.

    This helper mirrors the previous implementation in `App._non_blocking_delay`.
    It intentionally preserves the same behavior and UI elements.

    Args:
        parent (ctk.CTk): Application window hosting the overlay.
        seconds (int): Duration to keep the overlay visible.
        message (str): Message displayed above the spinner.
    """
    host: DelayOverlayHostProtocol = cast(DelayOverlayHostProtocol, parent)

    # Create a borderless popup window
    overlay: ctk.CTkToplevel = ctk.CTkToplevel(parent)
    overlay.overrideredirect(True)

    # Center the popup over the main app
    width, height = 350, 150
    app_x: int = parent.winfo_rootx()
    app_y: int = parent.winfo_rooty()
    app_width: int = parent.winfo_width()
    app_height: int = parent.winfo_height()

    center_x: int = app_x + (app_width // 2) - (width // 2)
    center_y: int = app_y + (app_height // 2) - (height // 2)
    overlay.geometry(f"{width}x{height}+{center_x}+{center_y}")

    # Add a colored border frame
    border_frame = ctk.CTkFrame(
        overlay,
        border_width=2,
        border_color=host._theme.semantic_colors.info,
        corner_radius=0,
        fg_color="transparent",
    )
    border_frame.pack(fill="both", expand=True)

    # Add the text message
    label = ctk.CTkLabel(
        border_frame,
        text=message,
        font=host.fonts["body"],
    )
    label.pack(pady=(30, 15))

    # Add animated progress bar
    spinner = ctk.CTkProgressBar(
        border_frame,
        mode="indeterminate",
        width=250,
        progress_color=host._theme.semantic_colors.info,
    )
    spinner.pack(pady=(0, 30))
    spinner.start()

    # Lock UI and force popup to the front
    overlay.transient(parent)
    overlay.grab_set()
    parent.update_idletasks()

    # Execute non-blocking delay
    var: ctk.IntVar = ctk.IntVar()
    parent.after(int(seconds * 1000), lambda: var.set(1))
    parent.wait_variable(var)

    # Clean up and restore focus to main app
    spinner.stop()
    overlay.grab_release()
    overlay.destroy()
    parent.focus_force()
