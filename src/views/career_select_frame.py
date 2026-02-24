import customtkinter as ctk
import logging
from typing import Dict, Any
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.views.widgets.custom_alert import CustomAlert

logger = logging.getLogger(__name__)

class CareerSelectFrame(ctk.CTkFrame):
    """The initial startup frame allowing the user to select or create a career."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the CareerSelectFrame with UI components and layout.
        
        Args:
            parent (ctk.CTkFrame): The parent container frame.
            controller (Any): The main application controller (typed as Any to avoid 
                              circular imports with App).
            theme (Dict[str, Any]): The application's theme configuration dictionary.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme

        logger.info("Initializing CareerSelectFrame")

        # --- Layout Configuration ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)

        for i in range(7):
            self.grid_rowconfigure(i, weight=1 if i in [0, 6] else 0)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Welcome to Gaffer's Clipboard!",
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))

        # Info label
        self.info_label = ctk.CTkLabel(
            self,
            text="Please select your career to get started:",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=2, column=1, pady=10)

        # Career select mini-grid
        self.career_select_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme["colors"]["background"]
        )
        self.career_select_frame.grid(row=3, column=1, pady=10)

        self.career_select_frame.grid_columnconfigure(0, weight=1)
        self.career_select_frame.grid_columnconfigure(1, weight=1)
        self.career_select_frame.grid_rowconfigure(0, weight=1)

        # Drop down of current careers
        self.careers_list_var = ctk.StringVar(value="Select Career")
        self.careers_dropdown = ScrollableDropdown(
            self.career_select_frame,
            theme=self.theme,
            variable=self.careers_list_var,
            values=self.controller.data_manager.get_all_career_names(),
            width=350,
            dropdown_height=200,
            placeholder="Select Career"
        )
        self.careers_dropdown.grid(row=0, column=0, pady=10)

        # Select Career Button
        self.select_career_button = ctk.CTkButton(
            self.career_select_frame,
            text="Select Career",
            fg_color=self.theme["colors"]["button_fg"],
            bg_color=self.theme["colors"]["background"],
            font=self.theme["fonts"]["button"],
            text_color=self.theme["colors"]["primary_text"],
            hover_color=self.theme["colors"]["accent"],
            command=self.on_select_button_press
        )
        self.select_career_button.grid(row=0, column=1, padx=10, pady=10)

        # Or label
        self.or_label = ctk.CTkLabel(
            self,
            text="-- OR --",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.or_label.grid(row=4, column=1, pady=10)

        # New Career Button
        self.new_career_button = ctk.CTkButton(
            self,
            text="Start New Career",
            fg_color=self.theme["colors"]["button_fg"],
            bg_color=self.theme["colors"]["background"],
            font=self.theme["fonts"]["button"],
            text_color=self.theme["colors"]["primary_text"],
            hover_color=self.theme["colors"]["accent"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("CreateCareerFrame"))
        )
        self.new_career_button.grid(row=5, column=1, pady=20)
    
    def refresh_careers_dropdown(self) -> None:
        """Fetch the latest career list from the database and update the custom dropdown."""
        names = self.controller.data_manager.get_all_career_names()
        self.careers_dropdown.set_values(names)
        
        prev = self.careers_list_var.get()
        if prev not in names:
            # Fallback handling for empty states
            fallback_text = names[0] if names and names[0] != "No Careers Available" else "Select Career"
            self.careers_dropdown.set_value(fallback_text)
    
    def on_show(self) -> None:
        """Lifecycle hook triggered when this frame is brought to the front."""
        self.refresh_careers_dropdown()
        self.careers_dropdown.set_value("Click here to select career")
    
    def on_select_button_press(self) -> None:
        """Validate UI selection, set the active career, and navigate to the Main Menu."""
        selected_career = self.careers_list_var.get()
        
        invalid_states = ["Select Career", "No Careers Available", "Click here to select career"]
        if selected_career in invalid_states:
            logger.warning(f"Invalid career selection attempted: '{selected_career}'. Aborting navigation.")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Invalid Selection",
                message="Please select a valid career from the dropdown before proceeding.",
                alert_type="warning",
            )
            return
        
        logger.info(f"User validated and selected career: {selected_career}")
        try:
            self.controller.set_current_career_by_name(selected_career)
            target_class = self.controller.get_frame_class("MainMenuFrame")
            self.controller.show_frame(target_class)
        except Exception as e:
            logger.error(f"Failed to load career '{selected_career}': {e}", exc_info=True)
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Error Loading Career",
                message=f"An error occurred while loading the selected career: {str(e)}. Please try again.",
                alert_type="error",
            )
            return