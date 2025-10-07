import customtkinter as ctk
from src.theme import THEME

class AddMatchFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme):
        super().__init__(parent, fg_color=theme["colors"]["background"])

        self.label = ctk.CTkLabel(
            self, 
            text="Navigate to the match stats screen", 
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"],
            anchor="center",
        )
        self.label.pack(expand=True)