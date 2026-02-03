import customtkinter as ctk
import logging
from src.exceptions import UIPopulationError
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)

class MatchStatsFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        '''Frame for displaying match statistics in editable text boxes.

        Args:
            parent: The parent CTk window.
            controller: The main application controller.
            theme (dict): The theme dictionary containing colors and fonts.
        '''
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing MatchStatsFrame")
        
        # Attributes to store stat variables
        self.home_stats_vars = {}
        self.away_stats_vars = {}
        
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

        stat_names = ['Possession (%)', 'Ball Recovery Time (seconds)', 'Shots', 'xG', 'Passes', 'Tackles', 'Tackles Won', 'Interceptions', 'Saves', 'Fouls Committed', 'Offsides', 'Corners', 'Free Kicks', 'Penalty Kicks', 'Yellow Cards']
        # Configure subgrid
        for col in range(5):
            self.stats_grid.grid_columnconfigure(col, weight=1)
        for row in range(len(stat_names)):
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

        for i, stat in enumerate(stat_names):
            self.create_stat_row(i+1, stat, theme)
        
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

    def create_stat_row(self, row: int, stat_name: str, theme: dict) -> None:
        '''Create a row in the stats grid for a specific statistic.

        Args:
            row (int): The row number in the grid.
            stat_name (str): The name of the statistic.
            theme (dict): The theme dictionary containing colors and fonts.
        '''
        home_stat_value = ctk.StringVar(value="")
        self.home_stats_vars[stat_name] = home_stat_value
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
            text=stat_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.stat_label.grid(row=row, column=2, padx=5, pady=5)
        away_stat_value = ctk.StringVar(value="")
        self.away_stats_vars[stat_name] = away_stat_value
        self.away_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=away_stat_value,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.away_stat_entry.grid(row=row, column=4, padx=5, pady=5)

    def populate_stats(self, stats_data: dict) -> None:
        '''Populates the match statistics entry fields with detected statistics.
        Updates the input fields for each statistic using the provided stats_data dictionary.

        Args:
            stats_data (dict): A dictionary containing match statistics for home and away teams.
        '''
        logger.debug(f"Populating MatchStatsFrame with stats: {stats_data.keys()}")
        if not stats_data:
            raise UIPopulationError("Received no data to populate match statistics.")
        # Maps key from OCR to display name in the UI
        key_to_display_name = {
            'possession': 'Possession (%)',
            'ball_recovery': 'Ball Recovery Time (seconds)',
            'shots': 'Shots',
            'xG': 'xG',
            'passes': 'Passes',
            'tackles': 'Tackles',
            'tackles_won': 'Tackles Won',
            'interceptions': 'Interceptions',
            'saves': 'Saves',
            'fouls_committed': 'Fouls Committed',
            'offsides': 'Offsides',
            'corners': 'Corners',
            'free_kicks': 'Free Kicks',
            'penalty_kicks': 'Penalty Kicks',
            'yellow_cards': 'Yellow Cards',
        }
        
        home_stats = stats_data.get('home_team', {})
        away_stats = stats_data.get('away_team', {})
        
        if home_stats is None or away_stats is None:
            raise UIPopulationError("Match stats data is missing 'home_team' or 'away_team' keys.")

        self.home_team_score_var.set(str(home_stats.get('score', '0')))
        self.away_team_score_var.set(str(away_stats.get('score', '0')))

        for key, display_name in key_to_display_name.items():
            if display_name in self.home_stats_vars:
                self.home_stats_vars[display_name].set(str(home_stats.get(key, '')))
            if display_name in self.away_stats_vars:
                self.away_stats_vars[display_name].set(str(away_stats.get(key, '')))
        
        logger.debug("MatchStatsFrame populated successfully.")

    def collect_data(self) -> None:
        '''Handle the button pressing event, initiating screenshot capture and navigating to PlayerStatsFrame.
        '''
        # Collect match overview
        ui_data = {
            "competition": self.competition_var.get(),
            "home_team_name": self.home_team_name_var.get(),
            "away_team_name": self.away_team_name_var.get(),
            "home_score": self.home_team_score_var.get(),
            "away_score": self.away_team_score_var.get(),
            "home_stats": {k: v.get() for k, v in self.home_stats_vars.items()},
            "away_stats": {k: v.get() for k, v in self.away_stats_vars.items()}
        }
        
        if missing_fields := [
            key for key, value in ui_data.items() if value.strip() == ""
        ]:
            logger.warning(f"Validation failed: Missing fields - {', '.join(missing_fields)}")
            return
        
        # Buffer match overview
        self.controller.buffer_match_overview(ui_data)
    
    def on_next_outfield_player_button_press(self) -> None:
        '''Handle the button pressing event, initiating screenshot capture and navigating to PlayerStatsFrame.
        '''
        self.collect_data()
        self.controller.process_player_stats()
        self.controller.show_frame(self.controller.get_frame_class("PlayerStatsFrame"))
    
    def on_next_goalkeeper_button_press(self) -> None:
        '''Handle the button pressing event, initiating screenshot capture and navigating to GKStatsFrame.
        '''
        self.collect_data()
        self.controller.process_player_stats(gk=True)
        self.controller.show_frame(self.controller.get_frame_class("GKStatsFrame"))
    
    def on_done_button_press(self):
        self.collect_data()
        self.controller.save_buffered_match()
        self.controller.show_frame(self.controller.get_frame_class("MatchAddedFrame"))
    
    def on_show(self) -> None:
        self.competition_var.set("Select Competition")
        self.competition_dropdown.set_value("Select Competition")
