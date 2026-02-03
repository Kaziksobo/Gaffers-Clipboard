import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)

class CareerSelectFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing CareerSelectFrame")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=0)
        self.grid_rowconfigure(6, weight=1)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Welcome to Gaffer's Clipboard!",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Info label
        self.info_label = ctk.CTkLabel(
            self,
            text="Please select your career to get started:",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=2, column=1, pady=10)
        
        # Career select mini-grid
        self.career_select_frame = ctk.CTkFrame(
            self,
            fg_color=theme["colors"]["background"]
        )
        self.career_select_frame.grid(row=3, column=1, pady=10)
        
        self.career_select_frame.grid_columnconfigure(0, weight=1)
        self.career_select_frame.grid_columnconfigure(1, weight=1)
        self.career_select_frame.grid_rowconfigure(0, weight=1)
        
        # Drop down of current careers
        self.careers_list_var = ctk.StringVar(value="Select Career")
        self.careers_dropdown = ctk.CTkOptionMenu(
            self.career_select_frame,
            variable=self.careers_list_var,
            values=self.controller.data_manager.get_all_career_names(),
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["dropdown_fg"],
            text_color=theme["colors"]["primary_text"],
            button_color=theme["colors"]["button_fg"],
            # command=lambda choice: self.controller.set_current_career_by_name(choice)
        )
        self.careers_dropdown.grid(row=0, column=0, pady=10)
        
        # Select Career Button
        self.select_career_button = ctk.CTkButton(
            self.career_select_frame,
            text="Select Career",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["background"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["accent"],
            command=self.on_select_button_press
        )
        self.select_career_button.grid(row=0, column=1, padx=10, pady=10)
        
        # Or label
        self.or_label = ctk.CTkLabel(
            self,
            text="-- OR --",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.or_label.grid(row=4, column=1, pady=10)
        
        # New Career Button
        self.new_career_button = ctk.CTkButton(
            self,
            text="Start New Career",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["background"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["accent"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("CreateCareerFrame"))
        )
        self.new_career_button.grid(row=5, column=1, pady=20)
    
    def refresh_careers_dropdown(self) -> None:
        names = self.controller.data_manager.get_all_career_names()
        self.careers_dropdown.configure(values=names)
        
        prev = self.careers_list_var.get()
        if prev not in names:
            self.careers_list_var.set(names[0] if names and names[0] != "No Careers Available" else "Select Career")
    
    def on_show(self) -> None:
        self.refresh_careers_dropdown()
    
    def on_select_button_press(self) -> None:
        selected_career = self.careers_list_var.get()
        self.controller.set_current_career_by_name(selected_career)
        self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))