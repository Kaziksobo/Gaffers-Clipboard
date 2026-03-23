import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion, safe_float_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import OCRDataMixin, EntryFocusMixin

logger = logging.getLogger(__name__)

class MatchStatsFrame(BaseViewFrame, OCRDataMixin, EntryFocusMixin):
    """A data entry frame for validating and saving team match statistics."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        """Initialize the MatchStatsFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        
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
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # Title
        self.grid_rowconfigure(2, weight=0) # Info label
        self.grid_rowconfigure(3, weight=0) # Date
        self.grid_rowconfigure(4, weight=0) # Competition dropdown
        self.grid_rowconfigure(5, weight=1) # Stats grid
        self.grid_rowconfigure(6, weight=0) # Direction subgrid
        self.grid_rowconfigure(7, weight=1)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Review Match Statistics",
            font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Info Label
        self.info_label = ctk.CTkLabel(
            self, 
            text="Please review the captured match data. Fill in any missing fields and correct any inaccuracies.",
            font=self.fonts["body"]
        )
        self.info_label.grid(row=2, column=1, pady=(0, 20))
        self.register_wrapping_widget(self.info_label, width_ratio=0.6)
        
        # In-game date entry
        self.date_frame = ctk.CTkFrame(self)
        self.date_frame.grid(row=3, column=1, pady=(0, 20))
        self.in_game_date_label = ctk.CTkLabel(
            self.date_frame,
            text="In-game date:",
            font=self.fonts["body"]
        )
        self.in_game_date_label.grid(row=0, column=0, padx=(0, 10))
        self.in_game_date_entry = ctk.CTkEntry(
            self.date_frame,
            placeholder_text="dd/mm/yy",
            font=self.fonts["body"]
        )
        self.in_game_date_entry.grid(row=0, column=1)
        
        # Chronological validation for matches will be enforced by the view when collecting data
        
        # Competition dropdown
        self.competition_var = ctk.StringVar(value="Select Competition")
        self.competition_dropdown = ScrollableDropdown(
            self,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.competition_var,
            values=self.controller.full_competitions_list,
            width=350,
            dropdown_height=200,
            placeholder="Select Competition"
        )
        self.competition_dropdown.grid(row=4, column=1, pady=(0, 20))
        
        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self)
        self.stats_grid.grid(row=5, column=1, pady=(0, 20), sticky="nsew")

        # Configure subgrid
        for col in range(5):
            self.stats_grid.grid_columnconfigure(col, weight=1)
        for row in range(len(self.stat_definitions)):
            self.stats_grid.grid_rowconfigure(row, weight=1)

        # Populate subgrid with entry fields
        self.home_team_name = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.home_team_name_var,
            width=200,
            font=self.fonts["body"]
        )
        self.home_team_name.grid(row=0, column=0, padx=5, pady=5)

        self.home_team_score = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.home_team_score_var,
            width=80,
            font=self.fonts["body"]
        )
        self.home_team_score.grid(row=0, column=1, padx=5, pady=5)

        self.score_dash = ctk.CTkLabel(
            self.stats_grid,
            text="-",
            font=self.fonts["body"]
        )
        self.score_dash.grid(row=0, column=2, padx=5, pady=5)
        self.away_team_score = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.away_team_score_var,
            width=80,
            font=self.fonts["body"]
        )
        self.away_team_score.grid(row=0, column=3, padx=5, pady=5)

        self.away_team_name = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.away_team_name_var,
            width=200,
            font=self.fonts["body"]
        )
        self.away_team_name.grid(row=0, column=4, padx=5, pady=5)

        for i, (stat_key, stat_label) in enumerate(self.stat_definitions):
            self.create_home_away_stat_row(i + 1, stat_key, stat_label)
        
        # Direction subgrid
        self.direction_frame = ctk.CTkFrame(self)
        self.direction_frame.grid(row=6, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)
        self.direction_frame.grid_columnconfigure(3, weight=1)
        
        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text="To log individual performances, navigate to the in-game player performance screen:",
            font=self.fonts["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.register_wrapping_widget(self.direction_label, width_ratio=0.3)

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan Outfield Player",
            font=self.fonts["button"],
            command=lambda: self.on_next_outfield_player_button_press()
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan Goalkeeper",
            font=self.fonts["button"],
            command=lambda: self.on_next_goalkeeper_button_press()
        )
        self.next_goalkeeper_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="Save Match Only",
            font=self.fonts["button"],
            command=lambda: self.on_done_button_press()
        )
        self.all_players_added_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")
        self.style_submit_button(self.all_players_added_button)
        
        self.apply_focus_flourishes(self)

    def create_home_away_stat_row(self, row: int, stat_key: str, stat_label: str) -> None:
        """Helper to create a unified Home/Away entry row for a specific statistic."""
        home_stat_value = ctk.StringVar(value="")
        self.home_stats_vars[stat_key] = home_stat_value
        self.home_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=home_stat_value,
            width=80,
            font=self.fonts["body"]
        )
        self.home_stat_entry.grid(row=row, column=0, padx=5, pady=5)
        self.stat_label = ctk.CTkLabel(
            self.stats_grid,
            text=stat_label,
            font=self.fonts["body"]
        )
        self.stat_label.grid(row=row, column=2, padx=5, pady=5)
        away_stat_value = ctk.StringVar(value="")
        self.away_stats_vars[stat_key] = away_stat_value
        self.away_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=away_stat_value,
            width=80,
            font=self.fonts["body"]
        )
        self.away_stat_entry.grid(row=row, column=4, padx=5, pady=5)
        
    def get_ocr_mapping(self) -> Dict[str, Dict[str, ctk.StringVar]]:
        """Override OCRDataMixin mapping to handle nested dictionaries cleanly."""
        return {
            "home_team": self.home_stats_vars,
            "away_team": self.away_stats_vars
        }

    def collect_data(self) -> bool:
        """Extract inputs, validate them, and securely buffer the match overview data."""
        # Helper to convert stat based on key (xG is float, others are int)
        def convert_stat(key: str, value: str):
            if key == "xG":
                return safe_float_conversion(value)
            return safe_int_conversion(value)

        in_game_date = self.in_game_date_entry.get().strip()
        if not self.validate_in_game_date(in_game_date, disallow_older_than_last=True):
            return False
        
        # Ensure team names aren't the default placeholders
        if self.home_team_name_var.get().strip() in ["", "Home Team"]:
            self.show_warning("Missing Home Team Name", "Please enter the home team name before proceeding.")
            return False
        if self.away_team_name_var.get().strip() in ["", "Away Team"]:
            self.show_warning("Missing Away Team Name", "Please enter the away team name before proceeding.")
            return False

        # Collect match overview with type conversion
        ui_data = {
            "in_game_date": in_game_date,
            "competition": self.competition_var.get(),
            "home_team_name": self.home_team_name_var.get().strip() or None,
            "away_team_name": self.away_team_name_var.get().strip() or None,
            "home_score": safe_int_conversion(self.home_team_score_var.get()),
            "away_score": safe_int_conversion(self.away_team_score_var.get()),
            "home_stats": {k: convert_stat(k, v.get()) for k, v in self.home_stats_vars.items()},
            "away_stats": {k: convert_stat(k, v.get()) for k, v in self.away_stats_vars.items()},
        }

        validation_dict = {
            "Competition": ui_data["competition"],
            "Home Team Name": ui_data["home_team_name"],
            "Away Team Name": ui_data["away_team_name"],
            "Home Score": ui_data["home_score"],
            "Away Score": ui_data["away_score"]
        }

        key_to_label = dict(self.stat_definitions)
        for k, v in ui_data["home_stats"].items():
            validation_dict[f"Home {key_to_label.get(k, k)}"] = v
        for k, v in ui_data["away_stats"].items():
            validation_dict[f"Away {key_to_label.get(k, k)}"] = v

        if not self.check_missing_fields(
            validation_dict, {k: k for k in validation_dict}
        ):
            self.show_warning("Missing Fields", "Please fill in all required fields before proceeding.")
            return False
        
        percentage_data = {
            "Home Possession": ui_data["home_stats"]["possession"],
            "Away Possession": ui_data["away_stats"]["possession"]
        }
        percentage_defs = [("Home Possession", "Home Possession (%)"), ("Away Possession", "Away Possession (%)")]
        if not self.validate_attr_range(percentage_data, percentage_defs, min_val=0, max_val=100):
            return False
        
        home_poss = ui_data["home_stats"]["possession"]
        away_poss = ui_data["away_stats"]["possession"]
        if home_poss is not None and away_poss is not None and (home_poss + away_poss > 100):
            if not self.soft_validate(
                "possession_sum",
                home_poss + away_poss,
                "Possession Total Exceeds 100%",
                f"Home possession ({home_poss}%) and Away possession ({away_poss}%) total {home_poss + away_poss}%, which exceeds 100%. Are you sure?",
            ):
                return False
        
        if not self.validate_pair_hard(ui_data["home_stats"], [
            ("tackles_won", "Home Tackles Won", "tackles", "Home Tackles"),
        ]):
            return False
        if not self.validate_pair_hard(ui_data["away_stats"], [
            ("tackles_won", "Away Tackles Won", "tackles", "Away Tackles"),
        ]):
            return False
        
        home_xg = ui_data["home_stats"].get("xG")
        if not self.validate_xg(home_xg):
            return False

        away_xg = ui_data["away_stats"].get("xG")
        if not self.validate_xg(away_xg):
            return False
        
        stat_max_rules = [
            ("ball_recovery", "Ball Recovery Time", 50),
            ("shots", "Shots", 50),
            ("passes", "Passes", 1000),
            ("tackles", "Tackles", 100),
            ("interceptions", "Interceptions", 100),
            ("saves", "Saves", 50),
            ("fouls_committed", "Fouls Committed", 100),
            ("offsides", "Offsides", 50),
            ("corners", "Corners", 50),
            ("free_kicks", "Free Kicks", 100),
            ("penalty_kicks", "Penalty Kicks", 20),
            ("yellow_cards", "Yellow Cards", 20)
        ]
        for stat_key, stat_label, max_val in stat_max_rules:
            if not self.validate_stat_max(ui_data, stat_key, stat_label, max_val):
                return False

        # Buffer match overview
        logger.info("Match overview validation passed. Buffering data.")
        try:
            self.controller.buffer_match_overview(ui_data)
            logger.debug("Match overview buffered successfully.")
            self.show_success("Data Saved", "Match overview data Saved successfully! Proceed to add player stats.")
            return True
        except Exception as e:
            logger.error(f"Error buffering match overview: {e}")
            self.show_error("Error Saving Data", f"An error occurred while saving the match overview data: \n{str(e)}. \n\nPlease try again.")
            return False
    
    def on_next_outfield_player_button_press(self) -> None:
        """Buffer match overview and transition to adding individual player stats."""
        if not self.collect_data():
            return
        try: 
            self.controller.process_player_stats()
            self.controller.show_frame(self.controller.get_frame_class("PlayerStatsFrame"))
        except Exception as e:
            logger.error(f"Error during transition to PlayerStatsFrame: {e}", exc_info=True)
            self.show_error("Error Processing Data", f"An error occurred while processing the next player's stats: \n{str(e)}. \n\nPlease try again.")
    
    def on_next_goalkeeper_button_press(self) -> None:
        """Buffer match overview and transition to adding individual goalkeeper stats."""
        if not self.collect_data():
            return
        try:
            self.controller.process_player_stats(gk=True)
            self.controller.show_frame(self.controller.get_frame_class("GKStatsFrame"))
        except Exception as e:
            logger.error(f"Error during transition to GKStatsFrame: {e}", exc_info=True)
            self.show_error("Error Processing Data", f"An error occurred while processing the goalkeeper's stats: \n{str(e)}. \n\nPlease try again.")
    
    def on_done_button_press(self):
        """Buffer match overview and trigger the final database save."""
        if not self.collect_data():
            return
        try:
            self.controller.save_buffered_match()
            self.controller.show_frame(self.controller.get_frame_class("MatchAddedFrame"))
        except Exception as e:
            logger.error(f"Error during finalizing match addition: {e}", exc_info=True)
            self.show_error("Error Saving Match", f"An error occurred while saving the match data: \n{str(e)}. \n\nPlease try again.")
    
    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        self._dismissed_warnings.clear()
        
        # If a buffered overview exists (coming from AddMatchFrame), prefill those values.
        buffered = getattr(self.controller, "match_overview_buffer", None) or {}

        # Competition
        if buffered.get("competition"):
            try:
                self.competition_dropdown.set_values(self.controller.get_current_career_details().competitions or [])
            except Exception:
                # fallback to existing controller list if available
                pass
            self.competition_var.set(buffered.get("competition"))
            self.competition_dropdown.set_value(buffered.get("competition"))
        else:
            self.competition_var.set("Select Competition")
            self.competition_dropdown.set_value("Select Competition")

        # In-game date
        if buffered.get("in_game_date"):
            self.in_game_date_entry.delete(0, 'end')
            self.in_game_date_entry.insert(0, buffered.get("in_game_date"))
        else:
            self.in_game_date_entry.delete(0, 'end')
            self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")
                
        # Reset team names
        self.home_team_name_var.set("Home Team")
        self.away_team_name_var.set("Away Team")
