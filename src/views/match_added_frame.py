import customtkinter as ctk
import logging
from typing import Dict, Any

from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)

class MatchAddedFrame(BaseViewFrame):
    """A simple success screen displayed when a match is successfully recorded."""
    
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the MatchAddedFrame layout.
        
        Args:
            parent (ctk.CTkFrame): The parent CTk window/frame.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The theme dictionary containing colors and fonts.
        """
        super().__init__(parent, controller, theme)
        
        logger.info("Initializing MatchAddedFrame")

        self.label = ctk.CTkLabel(
            self, 
            text="Match successfully recorded", 
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"],
            anchor="center",
        )
        self.label.pack(expand=True)

        self.done_button = ctk.CTkButton(
            self,
            text="Return to Main Menu",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
        )
        self.done_button.pack(pady=10)