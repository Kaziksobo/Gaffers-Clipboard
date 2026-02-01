import customtkinter as ctk

class MainMenuFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        '''Main menu frame for the application.

        Args:
            parent: The parent CTk window.
            controller: The main application controller.
            theme (dict): The theme dictionary containing colors and fonts.
        '''
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller

        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text=self.get_career_welcome_text(),
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        # Question Label
        self.question_label = ctk.CTkLabel(
            self, text="What would you like to do?",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.question_label.grid(row=2, column=1, pady=10)

        # Buttons Frame
        self.button_frame = ctk.CTkFrame(
            self,
            fg_color=theme["colors"]["background"]
        )
        self.button_frame.grid(row=3, column=1, pady=20)

        # Player Update Button
        self.player_update_button = ctk.CTkButton(
            self.button_frame,
            text="Update player attributes",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["button_bg"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["accent"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        )
        self.player_update_button.pack(side="left", padx=(0, 10), pady=10)

        # Add Match Button
        self.add_match_button = ctk.CTkButton(
            self.button_frame, text="Add new match",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["button_bg"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["accent"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("AddMatchFrame"))
        )
        self.add_match_button.pack(side="right", padx=(10, 0), pady=10)
    
    def get_career_welcome_text(self) -> str:
        """Generates the welcome text shown on the main menu. Adapts the message based on the currently loaded career details.

        Returns:
            str: A formatted welcome message including club and manager names when available, otherwise a generic welcome message.
        """
        current_career = self.controller.get_current_career_details()
        if current_career:
            club_name = current_career["club_name"] or "your club"
            manager_name = current_career["manager_name"] or "Gaffer"
            return f"Welcome back to {club_name}, {manager_name}!"
        else:
            return "Welcome to Gaffer's Clipboard!"
    
    def on_show(self) -> None:
        """Called when the frame is shown. Refreshes the welcome text."""
        welcome_text = self.get_career_welcome_text()
        self.main_heading.configure(text=welcome_text)