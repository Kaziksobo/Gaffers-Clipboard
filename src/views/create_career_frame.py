import customtkinter as ctk
import logging
from typing import Dict, Any
from src.utils import safe_int_conversion

from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)

class CreateCareerFrame(BaseViewFrame):
    """A frame that provides a form for users to create a new FIFA career profile."""
    _show_main_menu_nav = False
    
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        """Initialize the CreateCareerFrame with input fields and layout.

        Args:
            parent (ctk.CTkFrame): The parent container.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        
        logger.info("Initializing CreateCareerFrame")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
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
            font=self.fonts["title"],
            text_color=self.theme.colors.primary_text
        )
        self.main_heading.grid(row=1, column=1)
        
        # Entry grid
        self.entry_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme.colors.background
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
            font=self.fonts["body"],
            text_color=self.theme.colors.primary_text
        )
        self.club_name_label.grid(row=1, column=1, sticky="e", pady=5, padx=(0,10))
        self.club_name_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.fonts["body"],
            fg_color=self.theme.colors.entry_fg,
            text_color=self.theme.colors.primary_text,
            width=200
        )
        self.club_name_entry.grid(row=1, column=2, sticky="w", pady=5)
        
        # Manager Name
        self.manager_name_label = ctk.CTkLabel(
            self.entry_frame,
            text="Manager Name:",
            font=self.fonts["body"],
            text_color=self.theme.colors.primary_text
        )
        self.manager_name_label.grid(row=2, column=1, sticky="e", pady=5, padx=(0,10))
        self.manager_name_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.fonts["body"],
            fg_color=self.theme.colors.entry_fg,
            text_color=self.theme.colors.primary_text,
            width=200
        )
        self.manager_name_entry.grid(row=2, column=2, sticky="w", pady=5)
        
        # Starting Year
        self.starting_season_label = ctk.CTkLabel(
            self.entry_frame,
            text="Starting Season:",
            font=self.fonts["body"],
            text_color=self.theme.colors.primary_text
        )
        self.starting_season_label.grid(row=3, column=1, sticky="e", pady=5, padx=(0,10))
        self.starting_season_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.fonts["body"],
            fg_color=self.theme.colors.entry_fg,
            text_color=self.theme.colors.primary_text,
            width=200,
            placeholder_text="e.g. 24/25"
        )
        self.starting_season_entry.grid(row=3, column=2, sticky="w", pady=5)
        
        # Half Length
        self.half_length_label = ctk.CTkLabel(
            self.entry_frame,
            text="Half Length (mins):",
            font=self.fonts["body"],
            text_color=self.theme.colors.primary_text
        )
        self.half_length_label.grid(row=4, column=1, sticky="e", pady=5, padx=(0,10))
        self.half_length_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.fonts["body"],
            fg_color=self.theme.colors.entry_fg,
            text_color=self.theme.colors.primary_text,
            width=200
        )
        self.half_length_entry.grid(row=4, column=2, sticky="w", pady=5)
        
        # Match Difficulty
        self.match_difficulty_label = ctk.CTkLabel(
            self.entry_frame,
            text="Match Difficulty:",
            font=self.fonts["body"],
            text_color=self.theme.colors.primary_text
        )
        self.match_difficulty_label.grid(row=5, column=1, sticky="e", pady=5, padx=(0,10))
        # Dropdown for match difficulty, with options: Beginner, Amateur, Semi-Pro, Professional, World Class, Legendary, Ultimate
        self.match_difficulty_var = ctk.StringVar(value="Select Difficulty")
        self.match_difficulty_dropdown = ctk.CTkOptionMenu(
            self.entry_frame,
            variable=self.match_difficulty_var,
            values=["Beginner", "Amateur", "Semi-Pro", "Professional", "World Class", "Legendary", "Ultimate"],
            font=self.fonts["body"],
            fg_color=self.theme.colors.dropdown_fg,
            text_color=self.theme.colors.primary_text,
            button_color=self.theme.colors.button_fg,
            dropdown_fg_color=self.theme.colors.dropdown_fg,
            dropdown_text_color=self.theme.colors.primary_text
        )
        self.match_difficulty_dropdown.grid(row=5, column=2, sticky="w", pady=5)
        
        # Button subgrid (return to main menu, create career)
        button_subgrid = ctk.CTkFrame(
            self,
            fg_color=self.theme.colors.background
        )
        button_subgrid.grid(row=3, column=1, pady=20)
        button_subgrid.grid_columnconfigure(0, weight=1)
        button_subgrid.grid_columnconfigure(1, weight=0)
        button_subgrid.grid_columnconfigure(2, weight=0)
        button_subgrid.grid_columnconfigure(3, weight=1)
        button_subgrid.grid_rowconfigure(0, weight=1)
        button_subgrid.grid_rowconfigure(1, weight=0)
        button_subgrid.grid_rowconfigure(2, weight=1)
        
        # Return to Main Menu Button
        self.return_button = ctk.CTkButton(
            button_subgrid,
            text="Return to Career Selection",
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.background,
            font=self.fonts["button"],
            text_color=self.theme.colors.primary_text,
            hover_color=self.theme.colors.accent,
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("CareerSelectFrame"))
        )
        self.return_button.grid(row=1, column=1, padx=10)

        # Create Career Button
        self.create_career_button = ctk.CTkButton(
            button_subgrid,
            text="Start Career",
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.button_bg,
            font=self.fonts["button"],
            text_color=self.theme.colors.primary_text,
            command=self.on_create_career_button_press
        )
        self.create_career_button.grid(row=1, column=2, padx=10)
        
    def on_create_career_button_press(self) -> None:
        """Validate input fields and invoke the controller to create a new career profile."""
        club = self.club_name_entry.get().strip()
        manager = self.manager_name_entry.get().strip()
        season = self.starting_season_entry.get().strip()
        length = safe_int_conversion(self.half_length_entry.get().strip())
        difficulty = self.match_difficulty_var.get()
        
        # Check if the season is in a valid format (e.g. "24/25")
        season = self.validate_season(season)
        if season is None:
            return

        missing_fields = []
        if not club: missing_fields.append("Club Name")
        if not manager: missing_fields.append("Manager Name")
        if not season: missing_fields.append("Starting Season")
        if not length: missing_fields.append("Half Length")
        if difficulty in ["Select Difficulty", ""]: missing_fields.append("Difficulty")

        if missing_fields:
            logger.warning(f"Career creation blocked. Missing fields: {', '.join(missing_fields)}")
            self.show_warning("Missing Information", f"The following required fields are missing: {', '.join(missing_fields)}.\n\nPlease fill them in before proceeding.")
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
            self.show_success("Career Created", f"Your new career with {club} has been successfully created!")
            self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
            
        except Exception as e:
            logger.error(f"Failed to create new career: {e}", exc_info=True)
            self.show_error("Error Creating Career", f"An error occurred while creating your career: \n{str(e)}\n\nPlease try again.")
            return
    
    def on_show(self) -> None:
        self.club_name_entry.delete(0, 'end')
        self.manager_name_entry.delete(0, 'end')
        self.starting_season_entry.delete(0, 'end')
        self.starting_season_entry.configure(placeholder_text="e.g. 24/25")
        self.half_length_entry.delete(0, 'end')
        self.match_difficulty_var.set("Select Difficulty")