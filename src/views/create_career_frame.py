import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)

class CreateCareerFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        ## Entries for club name, manager name, starting year, half length, match difficulty
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
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
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1)
        
        # Entry grid
        self.entry_frame = ctk.CTkFrame(
            self,
            fg_color=theme["colors"]["background"]
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
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.club_name_label.grid(row=1, column=1, sticky="e", pady=5, padx=(0,10))
        self.club_name_entry = ctk.CTkEntry(
            self.entry_frame,
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["entry_fg"],
            text_color=theme["colors"]["primary_text"],
            width=200
        )
        self.club_name_entry.grid(row=1, column=2, sticky="w", pady=5)
        
        # Manager Name
        self.manager_name_label = ctk.CTkLabel(
            self.entry_frame,
            text="Manager Name:",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.manager_name_label.grid(row=2, column=1, sticky="e", pady=5, padx=(0,10))
        self.manager_name_entry = ctk.CTkEntry(
            self.entry_frame,
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["entry_fg"],
            text_color=theme["colors"]["primary_text"],
            width=200
        )
        self.manager_name_entry.grid(row=2, column=2, sticky="w", pady=5)
        
        # Starting Year
        self.starting_season_label = ctk.CTkLabel(
            self.entry_frame,
            text="Starting Season:",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.starting_season_label.grid(row=3, column=1, sticky="e", pady=5, padx=(0,10))
        self.starting_season_entry = ctk.CTkEntry(
            self.entry_frame,
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["entry_fg"],
            text_color=theme["colors"]["primary_text"],
            width=200
        )
        self.starting_season_entry.grid(row=3, column=2, sticky="w", pady=5)
        
        # Half Length
        self.half_length_label = ctk.CTkLabel(
            self.entry_frame,
            text="Half Length (minutes):",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.half_length_label.grid(row=4, column=1, sticky="e", pady=5, padx=(0,10))
        self.half_length_entry = ctk.CTkEntry(
            self.entry_frame,
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["entry_fg"],
            text_color=theme["colors"]["primary_text"],
            width=200
        )
        self.half_length_entry.grid(row=4, column=2, sticky="w", pady=5)
        
        # Match Difficulty
        self.match_difficulty_label = ctk.CTkLabel(
            self.entry_frame,
            text="Match Difficulty:",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.match_difficulty_label.grid(row=5, column=1, sticky="e", pady=5, padx=(0,10))
        # Dropdown for match difficulty, with options: Beginner, Amateur, Semi-Pro, Professional, World Class, Legendary, Ultimate
        self.match_difficulty_var = ctk.StringVar(value="Select Difficulty")
        self.match_difficulty_dropdown = ctk.CTkOptionMenu(
            self.entry_frame,
            variable=self.match_difficulty_var,
            values=["Beginner", "Amateur", "Semi-Pro", "Professional", "World Class", "Legendary", "Ultimate"],
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["dropdown_fg"],
            text_color=theme["colors"]["primary_text"],
            button_color=theme["colors"]["button_fg"],
            dropdown_fg_color=theme["colors"]["dropdown_fg"],
            dropdown_text_color=theme["colors"]["primary_text"]
        )
        self.match_difficulty_dropdown.grid(row=5, column=2, sticky="w", pady=5)
        
        # Create Career Button
        self.create_career_button = ctk.CTkButton(
            self,
            text="Create Career",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["button_bg"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            command=self.on_create_career_button_press
        )
        self.create_career_button.grid(row=3, column=1)
        
    def on_create_career_button_press(self) -> None:
        club_name = self.club_name_entry.get().strip()
        manager_name = self.manager_name_entry.get().strip()
        starting_season = self.starting_season_entry.get().strip()
        half_length = self.half_length_entry.get().strip()
        match_difficulty = self.match_difficulty_var.get().strip()

        # Define validation rules: (value, field_name, condition)
        fields_to_validate = [
            (club_name, "Club Name", bool(club_name)),
            (manager_name, "Manager Name", bool(manager_name)),
            (starting_season, "Starting Season", bool(starting_season)),
            (half_length, "Half Length", bool(half_length)),
            (match_difficulty, "Match Difficulty", match_difficulty and match_difficulty != "Select Difficulty"),
        ]

        if missing_fields := [
            name for _, name, is_valid in fields_to_validate if not is_valid
        ]:
            logger.warning(f"Validation failed: Missing fields - {', '.join(missing_fields)}")
            return

        self.controller.save_new_career(club_name, manager_name, starting_season, int(half_length), match_difficulty)
        self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))