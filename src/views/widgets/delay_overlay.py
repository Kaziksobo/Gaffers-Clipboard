import customtkinter as ctk
from typing import Any

def show_delay_overlay(parent: Any, seconds: int, message: str = "Please wait...") -> None:
    """Display a modal overlay with a spinner message while the application processes events.

    This helper mirrors the previous implementation in `App._non_blocking_delay`.
    It intentionally preserves the same behavior and UI elements.
    """
    # Create a borderless popup window
    overlay = ctk.CTkToplevel(parent, fg_color=parent.theme["colors"]["background"])
    overlay.overrideredirect(True)

    # Center the popup over the main app
    width, height = 350, 150
    app_x = parent.winfo_rootx()
    app_y = parent.winfo_rooty()
    app_width = parent.winfo_width()
    app_height = parent.winfo_height()

    center_x = app_x + (app_width // 2) - (width // 2)
    center_y = app_y + (app_height // 2) - (height // 2)
    overlay.geometry(f"{width}x{height}+{center_x}+{center_y}")

    # Add a colored border frame
    border_frame = ctk.CTkFrame(
        overlay,
        border_width=2,
        border_color=parent.theme["colors"]["accent"],
        corner_radius=0,
        fg_color="transparent",
    )
    border_frame.pack(fill="both", expand=True)

    # Add the text message
    label = ctk.CTkLabel(
        border_frame,
        text=message,
        font=parent.fonts["body"],
        text_color=parent.theme["colors"]["primary_text"],
    )
    label.pack(pady=(30, 15))

    # Add animated progress bar
    spinner = ctk.CTkProgressBar(
        border_frame,
        mode="indeterminate",
        width=250,
        progress_color=parent.theme["colors"]["accent"],
    )
    spinner.pack(pady=(0, 30))
    spinner.start()

    # Lock UI and force popup to the front
    overlay.transient(parent)
    overlay.grab_set()
    parent.update_idletasks()

    # Execute non-blocking delay
    var = ctk.IntVar()
    parent.after(int(seconds * 1000), lambda: var.set(1))
    parent.wait_variable(var)

    # Clean up and restore focus to main app
    spinner.stop()
    overlay.grab_release()
    overlay.destroy()
    parent.focus_force()
