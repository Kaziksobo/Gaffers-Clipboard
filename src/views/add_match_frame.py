import customtkinter as ctk

class AddMatchFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme):
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller

        self.label = ctk.CTkLabel(
            self, 
            text="Navigate to the match stats screen", 
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"],
            anchor="center",
        )
        self.label.pack(expand=True)

        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=theme["colors"]["button_bg"],
            text_color=theme["colors"]["secondary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.pack(pady=10)
    
    def on_done_button_press(self):
        self.controller.capture_screenshot(is_it_player=False)
        self.controller.show_frame(self.controller.get_frame_class("MatchStatsFrame"))