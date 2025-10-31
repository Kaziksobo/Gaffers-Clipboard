import customtkinter as ctk

class PlayerLibraryFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme):
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)
        
        self.title = ctk.CTkLabel(
            self,
            text="Welcome to your player library",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.title.grid(row=1, column=1, pady=(20, 10))
        
        delay_seconds = getattr(self.controller, "screenshot_delay", 3)
        self.info_label = ctk.CTkLabel(
            self,
            text=f"Upon clicking each button, you have {delay_seconds} seconds to take a screenshot.",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=2, column=1, pady=(10, 20))

        # Add-player-buttons subgrid
        self.buttons_grid = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.buttons_grid.grid(row=3, column=1, pady=(0, 20), sticky="nsew")
        self.buttons_grid.grid_columnconfigure(0, weight=1)
        self.buttons_grid.grid_columnconfigure(1, weight=1)
        self.buttons_grid.grid_rowconfigure(0, weight=1)
        
        self.add_gk_button = ctk.CTkButton(
            self.buttons_grid,
            text="Add Goalkeeper",
            fg_color=theme["colors"]["button_bg"],
            text_color=theme["colors"]["secondary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_add_gk_button_press()
        )
        self.add_gk_button.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        self.add_outfield_button = ctk.CTkButton(
            self.buttons_grid,
            text="Add Outfield Player",
            fg_color=theme["colors"]["button_bg"],
            text_color=theme["colors"]["secondary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_add_outfield_button_press()
        )
        self.add_outfield_button.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        self.home_button = ctk.CTkButton(
            self,
            text="Return to Main Menu",
            fg_color=theme["colors"]["button_bg"],
            text_color=theme["colors"]["secondary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
        )
        self.home_button.grid(row=4, column=1, padx=10, pady=5, sticky="ew")

    def on_add_gk_button_press(self):
        self.controller.process_player_attributes(gk=True, first=True)
        self.controller.show_frame(self.controller.get_frame_class("AddGKFrame"))

    def on_add_outfield_button_press(self):
        self.controller.process_player_attributes(gk=False, first=True)
        self.controller.show_frame(self.controller.get_frame_class("AddOutfieldFrame1"))