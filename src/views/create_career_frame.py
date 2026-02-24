import customtkinter as ctk
import logging
import re
from typing import Dict, Any, List
from src.utils import safe_int_conversion
from src.views.widgets.custom_alert import CustomAlert

logger = logging.getLogger(__name__)

class CreateCareerFrame(ctk.CTkFrame):
    """A frame that provides a form for users to create a new FIFA career profile."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the CreateCareerFrame with input fields and layout.

        Args:
            parent (ctk.CTkFrame): The parent container.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme
        
        logger.info("Initializing CreateCareerFrame")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Create New Career",
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1)
        
        # Entry grid
        self.entry_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme["colors"]["background"]
        )
        self.entry_frame.grid(row=2, column=1, pady=20)
        self.entry_frame.grid_columnconfigure(0, weight=1)
        self.entry_frame.grid_columnconfigure(1, weight=0)
        self.entry_frame.grid_columnconfigure(2, weight=0)
        self.entry_frame.grid_columnconfigure(3, weight=1)
        self.entry_frame.grid_rowconfigure(0, weight=1)
        self.entry_frame.grid_rowconfigure(1, weight=0)
        self.entry_frame.grid_rowconfigure(2, weight=0)
        self.entry_frame.grid_rowconfigure(3, weight=0)
        self.entry_frame.grid_rowconfigure(4, weight=0)
        self.entry_frame.grid_rowconfigure(5, weight=0)
        self.entry_frame.grid_rowconfigure(6, weight=1)
        
        # Club Name
        self.club_name_label = ctk.CTkLabel(
            self.entry_frame,
            text="Club Name:",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.club_name_label.grid(row=1, column=1, sticky="e", pady=5, padx=(0,10))
        self.club_name_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.theme["fonts"]["body"],
            fg_color=self.theme["colors"]["entry_fg"],
            text_color=self.theme["colors"]["primary_text"],
            width=200
        )
        self.club_name_entry.grid(row=1, column=2, sticky="w", pady=5)
        
        # Manager Name
        self.manager_name_label = ctk.CTkLabel(
            self.entry_frame,
            text="Manager Name:",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.manager_name_label.grid(row=2, column=1, sticky="e", pady=5, padx=(0,10))
        self.manager_name_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.theme["fonts"]["body"],
            fg_color=self.theme["colors"]["entry_fg"],
            text_color=self.theme["colors"]["primary_text"],
            width=200
        )
        self.manager_name_entry.grid(row=2, column=2, sticky="w", pady=5)
        
        # Starting Year
        self.starting_season_label = ctk.CTkLabel(
            self.entry_frame,
            text="Starting Season:",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.starting_season_label.grid(row=3, column=1, sticky="e", pady=5, padx=(0,10))
        self.starting_season_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.theme["fonts"]["body"],
            fg_color=self.theme["colors"]["entry_fg"],
            text_color=self.theme["colors"]["primary_text"],
            width=200
        )
        self.starting_season_entry.grid(row=3, column=2, sticky="w", pady=5)
        
        # Half Length
        self.half_length_label = ctk.CTkLabel(
            self.entry_frame,
            text="Half Length (minutes):",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.half_length_label.grid(row=4, column=1, sticky="e", pady=5, padx=(0,10))
        self.half_length_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.theme["fonts"]["body"],
            fg_color=self.theme["colors"]["entry_fg"],
            text_color=self.theme["colors"]["primary_text"],
            width=200
        )
        self.half_length_entry.grid(row=4, column=2, sticky="w", pady=5)
        
        # Match Difficulty
        self.match_difficulty_label = ctk.CTkLabel(
            self.entry_frame,
            text="Match Difficulty:",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.match_difficulty_label.grid(row=5, column=1, sticky="e", pady=5, padx=(0,10))
        # Dropdown for match difficulty, with options: Beginner, Amateur, Semi-Pro, Professional, World Class, Legendary, Ultimate
        self.match_difficulty_var = ctk.StringVar(value="Select Difficulty")
        self.match_difficulty_dropdown = ctk.CTkOptionMenu(
            self.entry_frame,
            variable=self.match_difficulty_var,
            values=["Beginner", "Amateur", "Semi-Pro", "Professional", "World Class", "Legendary", "Ultimate"],
            font=self.theme["fonts"]["body"],
            fg_color=self.theme["colors"]["dropdown_fg"],
            text_color=self.theme["colors"]["primary_text"],
            button_color=self.theme["colors"]["button_fg"],
            dropdown_fg_color=self.theme["colors"]["dropdown_fg"],
            dropdown_text_color=self.theme["colors"]["primary_text"]
        )
        self.match_difficulty_dropdown.grid(row=5, column=2, sticky="w", pady=5)
        
        # Create Career Button
        self.create_career_button = ctk.CTkButton(
            self,
            text="Create Career",
            fg_color=self.theme["colors"]["button_fg"],
            bg_color=self.theme["colors"]["button_bg"],
            font=self.theme["fonts"]["button"],
            text_color=self.theme["colors"]["primary_text"],
            command=self.on_create_career_button_press
        )
        self.create_career_button.grid(row=3, column=1)
        
    def on_create_career_button_press(self) -> None:
        """Validate input fields and invoke the controller to create a new career profile."""
        club = self.club_name_entry.get().strip()
        manager = self.manager_name_entry.get().strip()
        season = self.starting_season_entry.get().strip()
        length = safe_int_conversion(self.half_length_entry.get().strip())
        difficulty = self.difficulty_var.get()
        
        # Check if the season is in a valid format (e.g. "24/25") using a simple regex
        # If the season is in format "2024/2025", convert it to "24/25"
        # If the format is completely wrong, just set it to None
        if re.match(r'^\d{2}/\d{2}$', season):
            pass
        elif re.match(r'^\d{4}/\d{4}$', season):
            season = f'{season[2:4]}/{season[7:9]}'
        else:
            season = None

        missing_fields = []
        if not club: missing_fields.append("Club Name")
        if not manager: missing_fields.append("Manager Name")
        if not season: missing_fields.append("Starting Season")
        if not length: missing_fields.append("Half Length")
        if difficulty == "Select Difficulty": missing_fields.append("Difficulty")

        if missing_fields:
            logger.warning(f"Career creation blocked. Missing fields: {', '.join(missing_fields)}")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Missing Information",
                message=f"The following required fields are missing: {', '.join(missing_fields)}. Please fill them in before proceeding.",
                alert_type="warning",
            )
            return

        try:
            # Difficulty is cast to the DifficultyLevel literal type
            self.controller.save_new_career(
                club_name=club,
                manager_name=manager,
                starting_season=season,
                half_length=length,
                match_difficulty=difficulty # type: ignore
            )
            
            logger.info(f"Successfully created career for {club}. Navigating to Main Menu.")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Career Created",
                message=f"Your new career with {club} has been successfully created!",
                alert_type="success",
                success_timeout=2
            )
            self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
            
        except Exception as e:
            logger.error(f"Failed to create new career: {e}", exc_info=True)
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Error Creating Career",
                message=f"An error occurred while creating the new career: {str(e)}. Please try again.",
                alert_type="error",
            )
            return