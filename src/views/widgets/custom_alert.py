import customtkinter as ctk
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

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
        self.options = options if options is not None else ["OK"]
        self.success_timeout = success_timeout
        
        self._timer_id = None
        
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
        
        popup_width = 400
        popup_height = 200
        
        self.parent.update_idletasks()  # Ensure the parent window's dimensions are up to date
        
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Calculate the position to center the popup
        center_x = parent_x + (parent_width // 2) - (popup_width // 2)
        center_y = parent_y + (parent_height // 2) - (popup_height // 2)
        
        self.geometry(f"{popup_width}x{popup_height}+{center_x}+{center_y}")
        
        self.attributes("-topmost", True)  # Keep the popup on top of other windows
    
    def _build_ui(self) -> None:
        """Build the UI elements of the alert popup based on the theme and alert type.
        
        This method should create a top title label (coloured according to the alert type), 
        a CTkTextbox to show the message which can use a scrollbar if the message is too long, 
        and iterates through the options list to create a CTkButton for each option,
        placing them dynamically at the bottom of the popup
        """
        accent_color = self.theme["colors"][self.alert_type]
        
        # Thin accent line at the top
        accent_line = ctk.CTkFrame(self, height=5, fg_color=accent_color)
        accent_line.pack(fill="x", side="top")
        
        # Title label
        title = ctk.CTkLabel(
            self,
            text=self.title_text,
            font=self.theme["fonts"]["title"],
            text_color=accent_color,
        )
        title.pack(pady=10)
        
        # Message textbox with vertical scrollbar
        message_textbox = ctk.CTkTextbox(
            self,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["background"],
            border_width=0,
            wrap="word",
        )
        message_textbox.pack(fill="both", expand=True, padx=5, pady=5)
        
        message_textbox.insert("0.0", self.message_text)  # Insert the message text
        message_textbox.configure(state="disabled")  # Make the textbox read-only
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(self, fg_color=self.theme["colors"]["background"])
        buttons_frame.pack(pady=10)
        
        for option in self.options:
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
    
    def _button_callback(self, choice: str) -> None:
        """Handle button clicks based on the alert type and the specific choice made by the user.
        
        This method receives a string of the button that the user clicked, 
        it then saves that string to self.user_choice, and then calls self.destroy()
        to close the popup. The main window can then call get_result() to retrieve the user's choice.
        """
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        
        self.user_choice = choice
        self.destroy()
    
    def _make_modal(self) -> None:
        """Make the popup modal by disabling interaction with the main window until the popup is closed.
        
        self.transient(self.parent) should be called to set the popup as a transient window of the parent,
        self.grab_set() should be called to prevent interaction with the parent window, 
        and self.wait_window() should be called to pause execution in the main window until the popup is destroyed."""
        self.transient(self.parent)
        self.grab_set()
        self.wait_window()
        
    def _auto_close(self) -> None:
        """Automatically close the popup after a timeout (used for success messages)."""
        self.user_choice = "Timeout"
        self.destroy()
    
    def get_result(self) -> Optional[str]:
        """Return the user's choice from the alert popup, if applicable.
        
        """
        return self.user_choice