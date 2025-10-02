import customtkinter as ctk

class AddMatchFrame(ctk.CTkFrame):
    def __init__(self, parent, theme):
        super().__init__(parent, fg_color=theme["colors"]["background"])
        
        self.pack(expand=True, fill="both")
        self.pack_propagate(False)
        
        