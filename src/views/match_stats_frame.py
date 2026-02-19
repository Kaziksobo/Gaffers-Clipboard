import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.exceptions import UIPopulationError
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion, safe_float_conversion

logger = logging.getLogger(__name__)

class MatchStatsFrame(ctk.CTkFrame):
    """A data entry frame for validating and saving team match statistics."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the MatchStatsFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing MatchStatsFrame")
        
        # Attributes to store stat variables
        self.home_stats_vars: Dict[str, ctk.StringVar] = {}
        self.away_stats_vars: Dict[str, ctk.StringVar] = {}
        
        self.stat_definitions: List[Tuple[str, str]] = [
            ("possession", "Possession (%)"),
            ("ball_recovery", "Ball Recovery Time (seconds)"),
            ("shots", "Shots"),
            ("xG", "xG"),
            ("passes", "Passes"),
            ("tackles", "Tackles"),
            ("tackles_won", "Tackles Won"),
            ("interceptions", "Interceptions"),
            ("saves", "Saves"),
            ("fouls_committed", "Fouls Committed"),
            ("offsides", "Offsides"),
            ("corners", "Corners"),
            ("free_kicks", "Free Kicks"),
            ("penalty_kicks", "Penalty Kicks"),
            ("yellow_cards", "Yellow Cards"),
        ]
        
        # Variables for team names and scores
        self.home_team_name_var = ctk.StringVar(value="Home Team")
        self.away_team_name_var = ctk.StringVar(value="Away Team")
        self.home_team_score_var = ctk.StringVar(value="0")
        self.away_team_score_var = ctk.StringVar(value="0")

        # Setting up grid
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
            text="Match Statistics collected",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Info Label
        self.info_label = ctk.CTkLabel(
            self, text="Empty stats couldn't be recognised and require manual entry.\n Please review and update player attributes as necessary.",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=2, column=1, pady=(0, 20))
        
        # Competition dropdown
        self.competition_var = ctk.StringVar(value="Select Competition")
        self.competition_dropdown = ScrollableDropdown(
            self,
            theme=theme,
            variable=self.competition_var,
            values=self.controller.full_competitions_list,
            width=350,
            dropdown_height=200,
            placeholder="Select Competition"
        )
        self.competition_dropdown.grid(row=3, column=1, pady=(0, 20))
        
        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self, fg_color=theme["colors"]["background"])
        self.stats_grid.grid(row=4, column=1, pady=(0, 20), sticky="nsew")

        # Configure subgrid
        for col in range(5):
            self.stats_grid.grid_columnconfigure(col, weight=1)
        for row in range(len(self.stat_definitions)):
            self.stats_grid.grid_rowconfigure(row, weight=1)

        # Populate subgrid with entry fields
        self.home_team_name = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.home_team_name_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.home_team_name.grid(row=0, column=0, padx=5, pady=5)

        self.home_team_score = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.home_team_score_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.home_team_score.grid(row=0, column=1, padx=5, pady=5)

        self.score_dash = ctk.CTkLabel(
            self.stats_grid,
            text="-",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.score_dash.grid(row=0, column=2, padx=5, pady=5)
        self.away_team_score = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.away_team_score_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.away_team_score.grid(row=0, column=3, padx=5, pady=5)

        self.away_team_name = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.away_team_name_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.away_team_name.grid(row=0, column=4, padx=5, pady=5)

        for i, (stat_key, stat_label) in enumerate(self.stat_definitions):
            self.create_stat_row(i + 1, stat_key, stat_label, theme)
        
        # Direction subgrid
        self.direction_frame = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.direction_frame.grid(row=5, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)
        self.direction_frame.grid_columnconfigure(3, weight=1)
        
        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text="You can navigate to the first player's stats",
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Add Outfield Player",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_next_outfield_player_button_press()
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Add Goalkeeper",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_next_goalkeeper_button_press()
        )
        self.next_goalkeeper_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="Skip Player Stats",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.all_players_added_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")

    def create_stat_row(self, row: int, stat_key: str, stat_label: str, theme: Dict[str, Any]) -> None:
        """Helper to create a unified Home/Away entry row for a specific statistic."""
        home_stat_value = ctk.StringVar(value="")
        self.home_stats_vars[stat_key] = home_stat_value
        self.home_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=home_stat_value,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.home_stat_entry.grid(row=row, column=0, padx=5, pady=5)
        self.stat_label = ctk.CTkLabel(
            self.stats_grid,
            text=stat_label,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.stat_label.grid(row=row, column=2, padx=5, pady=5)
        away_stat_value = ctk.StringVar(value="")
        self.away_stats_vars[stat_key] = away_stat_value
        self.away_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=away_stat_value,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.away_stat_entry.grid(row=row, column=4, padx=5, pady=5)

    def populate_stats(self, stats_data: Dict[str, Any]) -> None:
        """Populate the Home and Away entry fields with detected match statistics.
        
        Args:
            stats (Dict[str, Any]): A dictionary containing nested 'home_team' and 'away_team' stats.
            
        Raises:
            UIPopulationError: If the provided stats dictionary is empty.
        """
        logger.debug(f"Populating MatchStatsFrame with stats: {stats_data.keys()}")
        if not stats_data:
            raise UIPopulationError("Received no data to populate match statistics.")
        
        home_stats = stats_data.get('home_team', {})
        away_stats = stats_data.get('away_team', {})
        
        if home_stats is None or away_stats is None:
            raise UIPopulationError("Match stats data is missing 'home_team' or 'away_team' keys.")

        self.home_team_score_var.set(str(home_stats.get('score', '0')))
        self.away_team_score_var.set(str(away_stats.get('score', '0')))

        for stat_key, _ in self.stat_definitions:
            self.home_stats_vars[stat_key].set(str(home_stats.get(stat_key, "")))
            self.away_stats_vars[stat_key].set(str(away_stats.get(stat_key, "")))
        
        logger.debug("MatchStatsFrame populated successfully.")

    def collect_data(self) -> None:
        """Extract inputs, validate them, and securely buffer the match overview data."""
        # Helper to convert stat based on key (xG is float, others are int)
        def convert_stat(key: str, value: str):
            if key == "xG":
                return safe_float_conversion(value)
            return safe_int_conversion(value)

        # Collect match overview with type conversion
        ui_data = {
            "competition": self.competition_var.get(),
            "home_team_name": self.home_team_name_var.get().strip() or None,
            "away_team_name": self.away_team_name_var.get().strip() or None,
            "home_score": safe_int_conversion(self.home_team_score_var.get()),
            "away_score": safe_int_conversion(self.away_team_score_var.get()),
            "home_stats": {k: convert_stat(k, v.get()) for k, v in self.home_stats_vars.items()},
            "away_stats": {k: convert_stat(k, v.get()) for k, v in self.away_stats_vars.items()},
        }

        missing_fields = []

        # Validate basic fields
        if ui_data["competition"] == "Select Competition": missing_fields.append("Competition")
        if ui_data["home_team_name"] is None: missing_fields.append("Home Team Name")
        if ui_data["away_team_name"] is None: missing_fields.append("Away Team Name")
        if ui_data["home_score"] is None: missing_fields.append("Home Score")
        if ui_data["away_score"] is None: missing_fields.append("Away Score")

        # Validate home stats
        if missing_keys := [key for key, value in ui_data["home_stats"].items() if value is None]:
            key_to_label = dict(self.stat_definitions)
            missing_fields.extend([f"Home {key_to_label.get(key, key)}" for key in missing_keys])

        # Validate away stats
        if missing_keys := [key for key, value in ui_data["away_stats"].items() if value is None]:
            key_to_label = dict(self.stat_definitions)
            missing_fields.extend([f"Away {key_to_label.get(key, key)}" for key in missing_keys])

        if missing_fields:
            logger.warning(f"Validation failed: Missing fields - {', '.join(missing_fields[:3])}...")
            return

        # Buffer match overview
        logger.info("Match overview validation passed. Buffering data.")
        try:
            self.controller.buffer_match_overview(ui_data)
            logger.debug("Match overview buffered successfully.")
        except Exception as e:
            logger.error(f"Error buffering match overview: {e}")
            raise
    
    def on_next_outfield_player_button_press(self) -> None:
        """Buffer match overview and transition to adding individual player stats."""
        try: 
            self.collect_data()
            self.controller.process_player_stats()
            self.controller.show_frame(self.controller.get_frame_class("PlayerStatsFrame"))
        except Exception as e:
            logger.error(f"Error during transition to PlayerStatsFrame: {e}", exc_info=True)
            raise
    
    def on_next_goalkeeper_button_press(self) -> None:
        """Buffer match overview and transition to adding individual goalkeeper stats."""
        try:
            self.collect_data()
            self.controller.process_player_stats(gk=True)
            self.controller.show_frame(self.controller.get_frame_class("GKStatsFrame"))
        except Exception as e:
            logger.error(f"Error during transition to GKStatsFrame: {e}", exc_info=True)
            raise
    
    def on_done_button_press(self):
        """Buffer match overview and trigger the final database save."""
        try:
            self.collect_data()
            self.controller.save_buffered_match()
            self.controller.show_frame(self.controller.get_frame_class("MatchAddedFrame"))
        except Exception as e:
            logger.error(f"Error during finalizing match addition: {e}", exc_info=True)
            raise
    
    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        self.competition_var.set("Select Competition")
        self.competition_dropdown.set_value("Select Competition")
                
        # Reset team names
        self.home_team_name_var.set("Home Team")
        self.away_team_name_var.set("Away Team")
