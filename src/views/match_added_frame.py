import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)

class MatchAddedFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        '''Frame displayed when a match is successfully added.

        Args:
            parent: The parent CTk window.
            controller: The main application controller.
            theme (dict): The theme dictionary containing colors and fonts.
        '''
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing MatchAddedFrame")

        self.label = ctk.CTkLabel(
            self, 
            text="Match successfully recorded", 
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"],
            anchor="center",
        )
        self.label.pack(expand=True)

        self.done_button = ctk.CTkButton(
            self,
            text="Return to Main Menu",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
        )
        self.done_button.pack(pady=10)