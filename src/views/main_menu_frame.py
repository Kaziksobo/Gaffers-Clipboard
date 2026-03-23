import customtkinter as ctk
import logging
from typing import Dict, Any

from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)

class MainMenuFrame(BaseViewFrame):
    """The central navigation hub shown after a career is successfully loaded."""
    _show_main_menu_nav = False
    
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        """Initialize the MainMenuFrame and its navigation components.

        Args:
            parent (ctk.CTkFrame): The parent container.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        
        logger.info("Initializing MainMenuFrame")

        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(5):
            self.grid_rowconfigure(i, weight=1 if i in [0, 4] else 0)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text=self.get_career_welcome_text(),
            font=self.fonts["title"],
            text_color=self.theme.colors.primary_text
        )
        self.main_heading.grid(row=1, column=1, sticky="s", pady=(0, 60))
        self.register_wrapping_widget(self.main_heading, width_ratio=0.85)
        
        # Question Label
        self.question_label = ctk.CTkLabel(
            self, text="What would you like to do?",
            font=self.fonts["body"],
            text_color=self.theme.colors.secondary_text
        )
        self.question_label.grid(row=2, column=1, sticky="s", pady=(0, 20))

        # Buttons Frame
        self.button_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme.colors.background
        )
        self.button_frame.grid(row=3, column=1, sticky="nsew")
        self.button_frame.grid_columnconfigure((0, 1), weight=1)
        self.button_frame.grid_rowconfigure(0, weight=1)

        # Player Update Button
        self.player_update_button = ctk.CTkButton(
            self.button_frame,
            text="Enter Player Library",
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.button_bg,
            font=self.fonts["button"],
            text_color=self.theme.colors.primary_text,
            hover_color=self.theme.colors.accent,
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        )
        self.player_update_button.grid(row=0, column=0, sticky="ew", padx=(0, 10), ipady=15)

        # Add Match Button
        self.add_match_button = ctk.CTkButton(
            self.button_frame, 
            text="Add New Match",
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.button_bg,
            font=self.fonts["button"],
            text_color=self.theme.colors.primary_text,
            hover_color=self.theme.colors.accent,
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("AddMatchFrame"))
        )
        self.add_match_button.grid(row=0, column=1, sticky="ew", padx=(10, 0), ipady=15)
    
    def get_career_welcome_text(self) -> str:
        """Generate a personalized welcome message based on the active career.

        Returns:
            str: A formatted string including the club and manager name.
        """
        if current_career := self.controller.get_current_career_details():
            return f"Welcome back to {current_career.club_name}, {current_career.manager_name}!"

        logger.warning("No active career found while generating welcome text.")
        return "Welcome to Gaffer's Clipboard!"
    
    def on_show(self) -> None:
        """Lifecycle hook triggered when the frame is displayed to refresh content."""
        welcome_text = self.get_career_welcome_text()
        self.main_heading.configure(text=welcome_text)