"""Custom modal alert dialog used across view frames.

Alert buttons support per-option hover-color overrides in addition to
label-only buttons. See `AlertOption` for accepted option formats.
"""

import contextlib
import logging
import tkinter as tk
from collections.abc import Sequence

import customtkinter as ctk

from src.contracts.ui import AlertOption, BaseViewThemeProtocol

logger = logging.getLogger(__name__)

AUTO_CLOSE_SENTINEL = "__AUTO_CLOSE__"


class CustomAlert(ctk.CTkToplevel):
    """A custom popup designed to show errors, warnings and success messages.

    It should freeze the main window until the popup is destroyed. The
    box should be centred on the screen, have a title, and a message
    showing the warning/error. A button closes the popup and may have
    different actions depending on the alert type.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: BaseViewThemeProtocol,
        fonts: dict[str, ctk.CTkFont],
        title: str,
        message: str,
        alert_type: str = "warning",
        options: Sequence[AlertOption] | None = None,
        success_timeout: int = 0,
    ) -> None:
        """Initialize the custom alert popup.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            theme (BaseViewThemeProtocol): The application theme configuration.
            title (str): The title of the alert popup.
            message (str): The message to display in the alert.
            alert_type (str): The type of alert ("error", "warning", "success", "info").
            options (Sequence[AlertOption] | None): Additional options for the
                alert (e.g., buttons). Supported shapes include:
                `"Close"`, `(label, hover_color)`, and
                `{"label": ..., "hover_color": ...}`.
                If no hover color is supplied for an option, the option
                inherits the alert-type semantic accent color.
            success_timeout (int): The timeout in seconds for success alerts
                (0 means no timeout).
        """
        super().__init__(parent)
        self.parent: ctk.CTkFrame = parent
        self.theme: BaseViewThemeProtocol = theme
        self.fonts: dict[str, ctk.CTkFont] = fonts
        self.title_text: str = title
        self.message_text: str = message
        self.alert_type: str = alert_type
        default_options: list[AlertOption] = ["OK"]
        self.options: list[AlertOption] = list(options) if options else default_options
        self.success_timeout: int = success_timeout

        self._timer_id: str | None = None
        self._poll_id: str | None = None
        self._parent_registered_wrapping_widgets: list[ctk.CTkLabel] = []

        self.user_choice: str | None = None

        self._setup_window()
        self._build_ui()

        if self.alert_type == "success" and self.success_timeout > 0:
            self._timer_id: str | None = self.after(
                self.success_timeout * 1000, self._auto_close
            )

        self._make_modal()

    def _resolve_option_config(
        self,
        option: AlertOption,
        default_hover: str,
    ) -> tuple[str, str]:
        """Normalize supported option shapes into label and hover color.

        The returned hover value is always concrete: either the caller-provided
        value from `option` or `default_hover` when an override is not present.
        """
        if isinstance(option, (list, tuple)):
            if len(option) == 0:
                return "OK", default_hover

            label = str(option[0])
            hover: str = default_hover
            if len(option) >= 2 and option[1]:
                hover = str(option[1])
            return label, hover

        if isinstance(option, dict):
            label = str(option.get("label", "OK"))
            hover: str = str(option.get("hover_color", default_hover))
            return label, hover

        return str(option), default_hover

    def _option_label(self, option: AlertOption) -> str:
        """Return the display label for a normalized option."""
        label, _hover = self._resolve_option_config(option, "")
        return label

    def _get_cancel_option_label(self) -> str | None:
        """Return the first cancel-like option label, if one exists."""
        for option in self.options:
            option_label: str = self._option_label(option)
            if option_label.strip().lower() in {"cancel", "close"}:
                return option_label
        return None

    def _setup_window(self) -> None:
        """Set up the window properties, such as title, size, and modality.

        This method should remove the OS title bar, set the width and
        height of the popup, and center it in the middle of the app.
        """
        self.overrideredirect(True)  # Remove OS title bar
        self.attributes("-toolwindow", True)

        if self.alert_type == "info":
            popup_width = 700
            popup_height = 500
        else:
            popup_width = 600
            popup_height = 400

        def get_screen_center() -> tuple[int, int]:
            screen_width: int = self.winfo_screenwidth()
            screen_height: int = self.winfo_screenheight()
            return (
                (screen_width // 2) - (popup_width // 2),
                (screen_height // 2) - (popup_height // 2),
            )

        try:
            # Ensure parent dimensions are up to date before positioning.
            self.parent.update_idletasks()

            parent_x: int = self.parent.winfo_rootx()
            parent_y: int = self.parent.winfo_rooty()
            parent_width: int = self.parent.winfo_width()
            parent_height: int = self.parent.winfo_height()

            # Fallback to screen centering if parent geometry is not yet laid out
            if parent_width <= 0 or parent_height <= 0:
                center_x, center_y = get_screen_center()
            else:
                # Calculate the position to center the popup relative to the parent
                center_x: int = parent_x + (parent_width // 2) - (popup_width // 2)
                center_y: int = parent_y + (parent_height // 2) - (popup_height // 2)
        except tk.TclError:
            logger.debug(
                "Could not query parent geometry; falling back to screen center",
                exc_info=True,
            )
            center_x, center_y = get_screen_center()

        self.geometry(f"{popup_width}x{popup_height}+{center_x}+{center_y}")

        self.lift()  # Bring the popup to the front
        self.focus_force()  # Focus on the popup window

    def _build_ui(self) -> None:
        """Build the UI elements of the alert popup based on the theme and alert type.

        This method creates a top title label (colored according to the alert type),
        a CTkTextbox to show the message with scrollbar support, and creates CTkButtons
        for each option, placing them dynamically at the bottom of the popup.

        Each button's hover color is resolved per option via
        `_resolve_option_config`, falling back to the alert semantic accent
        color when no explicit override is supplied.
        """
        semantic_colors: dict[str, str] = vars(self.theme.semantic_colors)
        default_accent_color: str = (
            semantic_colors.get(self.alert_type)
            or semantic_colors.get("info")
            or "#2196f3"
        )
        accent_color: str = default_accent_color

        # Default background from CTk theme (will use JSON theme's CTk.fg_color)
        main_container: ctk.CTkFrame = ctk.CTkFrame(
            self,
            border_width=2,  # Thickness of the border
            border_color=accent_color,  # Ties the border to the state color
            corner_radius=0,  # Set to 0 for sharp edges, or match your theme
        )
        main_container.pack(fill="both", expand=True)

        # Thin accent line at the top
        accent_line: ctk.CTkFrame = ctk.CTkFrame(
            main_container, height=5, fg_color=accent_color
        )
        accent_line.pack(fill="x", side="top")

        # Title label
        title: ctk.CTkLabel = ctk.CTkLabel(
            main_container,
            text=self.title_text,
            font=self.fonts["title"],
            text_color=accent_color,
        )
        title.pack(pady=10)

        # Register the title label with the parent view's responsive wrapping
        # so it uses the same dynamic wraplength calculation as other headings.
        with contextlib.suppress(Exception):
            if hasattr(self.parent, "register_wrapping_widget"):
                # Use a high ratio so the heading wraps close to the popup width
                self.parent.register_wrapping_widget(title, width_ratio=0.6)
                self._parent_registered_wrapping_widgets.append(title)
        # Message textbox (uses CTkTextbox's built-in scrollbar)
        message_textbox: ctk.CTkTextbox = ctk.CTkTextbox(
            main_container,
            font=self.fonts["body"],
            border_width=0,
            wrap="word",
        )
        message_textbox.pack(fill="both", expand=True, padx=5, pady=5)

        message_textbox.insert("0.0", self.message_text)
        message_textbox.configure(state="disabled")

        # Hide the built-in scrollbar if all content is visible
        self._message_textbox: ctk.CTkTextbox = message_textbox
        self.after(50, self._toggle_scrollbar)

        # Buttons frame (will use CTk theme default background)
        buttons_frame: ctk.CTkFrame = ctk.CTkFrame(main_container)
        buttons_frame.pack(pady=10)

        self._buttons: dict[str, ctk.CTkButton] = {}

        for index, option in enumerate(self.options):
            opt_label, opt_hover = self._resolve_option_config(option, accent_color)

            button = ctk.CTkButton(
                buttons_frame,
                text=opt_label,
                font=self.fonts["button"],
                hover_color=opt_hover,
                command=lambda opt_text=opt_label: self._button_callback(opt_text),
            )
            button.pack(side="left", padx=10)
            with contextlib.suppress(Exception):
                self._buttons[str(opt_label).lower()] = button
            if index == 0:
                try:
                    button.focus_set()
                except tk.TclError:
                    logger.debug("Could not focus primary alert button", exc_info=True)

        if self.options:
            primary_option: str = self._option_label(self.options[0])
            self.bind(
                "<Return>",
                lambda _event, opt=primary_option: self._button_callback(opt),
            )

        cancel_option: str | None = self._get_cancel_option_label()
        if cancel_option is not None:
            self.bind(
                "<Escape>", lambda _event, opt=cancel_option: self._button_callback(opt)
            )

    def _button_callback(self, choice: str) -> None:
        """Handle button clicks based on the alert type and the specific choice made.

        This method receives a string of the button that the user clicked,
        it then saves that string to self.user_choice, and then calls self.destroy()
        to close the popup. The main window can then call get_result()
        to retrieve the user's choice.
        """
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        self._close_with_choice(choice)

    def _make_modal(self) -> None:
        """Make the popup modal by disabling interaction with the main window."""
        self.transient(self.parent)
        self.grab_set()
        self._start_visibility_poll()
        self.wait_window()

    def _start_visibility_poll(self) -> None:
        """Periodically lift the alert above the main window.

        overrideredirect(True) windows on Windows lose their stacking
        position when the user alt-tabs or an external app overlays them.
        A lightweight poll every 200ms ensures the alert stays visible
        for as long as it exists.
        """
        if self.winfo_exists():
            try:
                self.lift()
            except tk.TclError:
                return
            self._poll_id: int = self.after(200, self._start_visibility_poll)

    def destroy(self) -> None:
        """Destroy the alert and clean up transient bindings/timers."""
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            finally:
                self._timer_id = None

        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            finally:
                self._poll_id = None

        # Remove any wrapping widgets we registered on the parent to avoid
        # leaving stale references in the parent's _wrapping_widgets list.
        with contextlib.suppress(Exception, AttributeError):
            if getattr(self, "_parent_registered_wrapping_widgets", None) and hasattr(
                self.parent, "_wrapping_widgets"
            ):
                self.parent._wrapping_widgets: list[tuple[ctk.CTkLabel, float]] = [
                    (w, r)
                    for (w, r) in self.parent._wrapping_widgets
                    if w not in self._parent_registered_wrapping_widgets
                ]

        super().destroy()

    def _close_with_choice(self, choice: str) -> None:
        """Finalize user choice, close popup, and restore focus to main app window."""
        self.user_choice: str = choice

        with contextlib.suppress(tk.TclError):
            self.grab_release()
        self.destroy()
        try:
            main_app_window: ctk.CTkToplevel = self.parent.winfo_toplevel()
            main_app_window.focus_force()
        except tk.TclError:
            logger.debug("Could not restore focus to main app window", exc_info=True)

    def _toggle_scrollbar(self) -> None:
        """Show the built-in scrollbar only when the text content overflows."""
        with contextlib.suppress(tk.TclError, AttributeError):
            if self._message_textbox.yview() == (0.0, 1.0):
                self._message_textbox._scrollbar.grid_remove()
            else:
                self._message_textbox._scrollbar.grid()

    def _auto_close(self) -> None:
        """Automatically close the popup after a timeout (used for success messages)."""
        self._close_with_choice(AUTO_CLOSE_SENTINEL)

    def get_result(self) -> str | None:
        """Return the user's choice from the alert popup, if applicable."""
        return self.user_choice
