import customtkinter as ctk
import logging
import tkinter as tk
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

AUTO_CLOSE_SENTINEL = "__AUTO_CLOSE__"

class CustomAlert(ctk.CTkToplevel):
    """A custom popup designed to show errors, warnings and success messages
    
    It should freeze the main window until the popup is destroyed,
    The box should be centred on the screen, have a title, a message showing the warning/error
    and a button to close the popup. The button should have different actions depending on the type of message.
    """
    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: Dict[str, Any],
        title: str,
        message: str,
        alert_type: str = "warning",
        options: Optional[List[str]] = None,
        success_timeout: int = 0
    ) -> None:
        """Initialize the custom alert popup.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            theme (Dict[str, Any]): The application theme configuration.
            title (str): The title of the alert popup.
            message (str): The message to display in the alert.
            alert_type (str): The type of alert ("error", "warning", "success").
            options (Optional[List[str]]): Additional options for the alert (e.g., buttons).
            success_timeout (int): The timeout in seconds for success alerts (0 means no timeout).
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.parent = parent
        self.theme = theme
        self.title_text = title
        self.message_text = message
        self.alert_type = alert_type
        self.options = ["OK"] if options is None or len(options) == 0 else options
        self.success_timeout = success_timeout

        self._timer_id = None
        self._focus_bindtag = f"CustomAlertFocus_{id(self)}"

        self.user_choice: Optional[str] = None

        self._setup_window()
        self._build_ui()

        if self.alert_type == "success" and self.success_timeout > 0:
            self._timer_id = self.after(self.success_timeout * 1000, self._auto_close)

        self._make_modal()
    
    def _setup_window(self) -> None:
        """Set up the window properties, such as title, size, and modality.
        
        This method should remove the OS title bar, set the width and height of the popup,
        and center it in the middle of the app.
        """
        self.overrideredirect(True) # Remove OS title bar
        
        popup_width = 600
        popup_height = 400

        def get_screen_center() -> tuple[int, int]:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            return (
                (screen_width // 2) - (popup_width // 2),
                (screen_height // 2) - (popup_height // 2),
            )
        
        try:
            self.parent.update_idletasks()  # Ensure the parent window's dimensions are up to date

            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()

            # Fallback to screen centering if parent geometry is not yet laid out
            if parent_width <= 0 or parent_height <= 0:
                center_x, center_y = get_screen_center()
            else:
                # Calculate the position to center the popup relative to the parent
                center_x = parent_x + (parent_width // 2) - (popup_width // 2)
                center_y = parent_y + (parent_height // 2) - (popup_height // 2)
        except tk.TclError:
            logger.debug("Could not query parent geometry; falling back to screen center", exc_info=True)
            center_x, center_y = get_screen_center()
        
        self.geometry(f"{popup_width}x{popup_height}+{center_x}+{center_y}")
        
        self.lift()  # Bring the popup to the front
        self.focus_force()  # Focus on the popup window
    
    def _build_ui(self) -> None:
        """Build the UI elements of the alert popup based on the theme and alert type.
        
        This method should create a top title label (coloured according to the alert type), 
        a CTkTextbox to show the message which can use a scrollbar if the message is too long, 
        and iterates through the options list to create a CTkButton for each option,
        placing them dynamically at the bottom of the popup
        """
        colors = self.theme.get("colors", {})
        default_accent_color = (
            colors.get("warning")
            or colors.get("error")
            or colors.get("primary")
            or colors.get("primary_text")
            or "white"
        )
        accent_color = colors.get(self.alert_type, default_accent_color)
        background_color = colors.get("background", "transparent")
        
        main_container = ctk.CTkFrame(
            self,
            fg_color=background_color,
            border_width=2,              # Thickness of the border
            border_color=accent_color,   # Ties the border to the error/warning/success color
            corner_radius=0              # Set to 0 for sharp edges, or match your theme
        )
        main_container.pack(fill="both", expand=True)
        
        # Thin accent line at the top
        accent_line = ctk.CTkFrame(main_container, height=5, fg_color=accent_color)
        accent_line.pack(fill="x", side="top")
        
        # Title label
        title = ctk.CTkLabel(
            main_container,
            text=self.title_text,
            font=self.theme["fonts"]["title"],
            text_color=accent_color,
        )
        title.pack(pady=10)

        # Message textbox with explicit vertical scrollbar
        message_frame = ctk.CTkFrame(
            main_container,
            fg_color="transparent",
        )
        message_frame.pack(fill="both", expand=True, padx=5, pady=5)

        message_textbox = ctk.CTkTextbox(
            message_frame,
            font=self.theme["fonts"]["body"],
            text_color=colors.get("primary_text", "white"),
            fg_color=background_color,
            border_width=0,
            wrap="word",
        )
        message_textbox.pack(side="left", fill="both", expand=True)

        message_scrollbar = ctk.CTkScrollbar(
            message_frame,
            orientation="vertical",
            command=message_textbox.yview,
        )
        message_scrollbar.pack(side="right", fill="y")

        message_textbox.configure(yscrollcommand=message_scrollbar.set)

        message_textbox.insert("0.0", self.message_text)  # Insert the message text
        message_textbox.configure(state="disabled")  # Make the textbox read-only
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(main_container, fg_color=background_color)
        buttons_frame.pack(pady=10)

        self._buttons: Dict[str, ctk.CTkButton] = {}

        for index, option in enumerate(self.options):
            button = ctk.CTkButton(
                buttons_frame,
                text=option.title(),
                font=self.theme["fonts"]["button"],
                fg_color=self.theme["colors"]["button_fg"],
                bg_color=self.theme["colors"]["button_bg"],
                hover_color=accent_color,
                command=lambda opt=option: self._button_callback(opt)
            )
            button.pack(side="left", padx=10)
            self._buttons[option.lower()] = button

            if index == 0:
                try:
                    button.focus_set()
                except tk.TclError:
                    logger.debug("Could not focus primary alert button", exc_info=True)

        if self.options:
            primary_option = self.options[0]
            self.bind("<Return>", lambda _event, opt=primary_option: self._button_callback(opt))

        cancel_option = next(
            (option for option in self.options if option.strip().lower() in {"cancel", "close"}),
            None,
        )
        if cancel_option is not None:
            self.bind("<Escape>", lambda _event, opt=cancel_option: self._button_callback(opt))
    
    def _button_callback(self, choice: str) -> None:
        """Handle button clicks based on the alert type and the specific choice made by the user.
        
        This method receives a string of the button that the user clicked, 
        it then saves that string to self.user_choice, and then calls self.destroy()
        to close the popup. The main window can then call get_result() to retrieve the user's choice.
        """
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        self._close_with_choice(choice)
    
    def _make_modal(self) -> None:
        """Make the popup modal by disabling interaction with the main window until the popup is closed.
        
        self.transient(self.parent) should be called to set the popup as a transient window of the parent,
        self.grab_set() should be called to prevent interaction with the parent window, 
        and self.wait_window() should be called to pause execution in the main window until the popup is destroyed."""
        self.transient(self.parent)  # Set the popup as a transient window of the parent
        self.grab_set()
        
        # If the main app is clicked, force the popup to the front
        current_bindtags = self.parent.bindtags()
        if self._focus_bindtag not in current_bindtags:
            self.parent.bindtags((self._focus_bindtag, *current_bindtags))
        self.parent.bind_class(
            self._focus_bindtag,
            "<FocusIn>",
            self._on_parent_focus,
            add="+"
        )
        
        self.wait_window()

    def _on_parent_focus(self, _event: tk.Event) -> None:
        """Bring this alert to front when the parent receives focus."""
        if self.winfo_exists():
            self.lift()

    def _remove_parent_focus_binding(self) -> None:
        """Remove this alert's parent focus bindtag and associated class binding."""
        try:
            self.parent.unbind_class(self._focus_bindtag, "<FocusIn>")
        except tk.TclError:
            logger.debug("Could not unbind focus class for %s", self._focus_bindtag, exc_info=True)

        try:
            current_bindtags = self.parent.bindtags()
            if self._focus_bindtag in current_bindtags:
                self.parent.bindtags(tuple(tag for tag in current_bindtags if tag != self._focus_bindtag))
        except tk.TclError:
            logger.debug("Could not update parent bindtags for %s", self._focus_bindtag, exc_info=True)

    def destroy(self) -> None:
        """Destroy the alert and clean up transient bindings/timers."""
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            finally:
                self._timer_id = None

        self._remove_parent_focus_binding()

        super().destroy()

    def _close_with_choice(self, choice: str) -> None:
        """Finalize user choice, close popup, and restore focus to main app window."""
        self.user_choice = choice

        try:
            self.grab_release()
        except tk.TclError:
            pass

        self.destroy()
        try:
            main_app_window = self.parent.winfo_toplevel()
            main_app_window.focus_force()
        except tk.TclError:
            logger.debug("Could not restore focus to main app window", exc_info=True)
        
    def _auto_close(self) -> None:
        """Automatically close the popup after a timeout (used for success messages)."""
        self._close_with_choice(AUTO_CLOSE_SENTINEL)
    
    def get_result(self) -> Optional[str]:
        """Return the user's choice from the alert popup, if applicable.
        
        """
        return self.user_choice