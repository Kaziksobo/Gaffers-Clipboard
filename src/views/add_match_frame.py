import customtkinter as ctk
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class AddMatchFrame(ctk.CTkFrame):
    """Frame for adding a match. 
    
    Provides basic layout with instructions and a button used to start 
    the match screenshot capture process.
    """
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddMatchFrame layout and components.
        
        Args:
            parent (ctk.CTkFrame): The parent CTk window/frame.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The theme dictionary containing colors and fonts.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme
        
        logger.info("Initializing AddMatchFrame")

        # Create a container frame to center the labels vertically and horizontally
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(expand=True)

        self.label = ctk.CTkLabel(
            self.container, 
            text="Navigate to the match stats screen", 
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"],
            anchor="center",
        )
        self.label.pack()

        # Use the controller's configured screenshot delay so the label is not hardcoded
        delay_seconds = getattr(self.controller, "screenshot_delay", 3)
        self.sub_label = ctk.CTkLabel(
            self.container,
            text=f"Once you click done, you have {delay_seconds} seconds to switch to the game and correct screen.",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["secondary_text"],
            anchor="center",
        )
        self.sub_label.pack()

        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["secondary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.pack(pady=10)
    
    def on_done_button_press(self) -> None:
        """Handle the done button press event.
        
        Initiates the screenshot capture and OCR process. If successful, 
        navigates the user to the MatchStatsFrame to validate the data.
        """
        try:
            logger.info("Initiating match stats capture process.")
            self.controller.process_match_stats()
            self.controller.show_frame(self.controller.get_frame_class("MatchStatsFrame"))
        except Exception as e:
            # Catch the UIPopulationError from the Controller to prevent navigating to a broken frame
            logger.error(f"Match stats OCR process aborted. Navigation cancelled: {e}", exc_info=True)