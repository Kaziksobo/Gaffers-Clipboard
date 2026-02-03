import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)

class AddMatchFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        '''Frame for adding a match. Basic layout with a label and a button, used to start the match capture process.

        Args:
            parent: The parent CTk window.
            controller: The main application controller.
            theme (dict): The theme dictionary containing colors and fonts.
        '''
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing AddMatchFrame")

        # Create a container frame to center the labels vertically and horizontally
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(expand=True)

        self.label = ctk.CTkLabel(
            self.container, 
            text="Navigate to the match stats screen", 
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"],
            anchor="center",
        )
        self.label.pack()

        # Use the controller's configured screenshot delay so the label is not hardcoded
        delay_seconds = getattr(self.controller, "screenshot_delay", 3)
        self.sub_label = ctk.CTkLabel(
            self.container,
            text=f"Once you click done, you have {delay_seconds} seconds to switch to the game and correct screen.",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"],
            anchor="center",
        )
        self.sub_label.pack()

        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["secondary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.pack(pady=10)
    
    def on_done_button_press(self) -> None:
        '''Handle the done button press event, initiating screenshot capture and navigating to MatchStatsFrame.
        '''
        self.controller.process_match_stats()
        self.controller.show_frame(self.controller.get_frame_class("MatchStatsFrame"))