import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion, safe_float_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import PlayerDropdownMixin, OCRDataMixin

logger = logging.getLogger(__name__)

class PlayerStatsFrame(BaseViewFrame, PlayerDropdownMixin, OCRDataMixin):
    """Frame for displaying and adding individual outfield player match statistics."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the PlayerStatsFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        
        logger.info("Initializing PlayerStatsFrame")
        
        # Attributes to store stat variables
        self.stats_vars: Dict[str, ctk.StringVar] = {}
        
        self.stat_definitions = [
            ("goals", "Goals"),
            ("assists", "Assists"),
            ("shots", "Shots"),
            ("shot_accuracy", "Shot Accuracy (%)"),
            ("passes", "Passes"),
            ("pass_accuracy", "Pass Accuracy (%)"),
            ("dribbles", "Dribbles"),
            ("dribble_success_rate", "Dribbles Success Rate (%)"),
            ("tackles", "Tackles"),
            ("tackle_success_rate", "Tackles Success Rate (%)"),
            ("offsides", "Offsides"),
            ("fouls_committed", "Fouls Committed"),
            ("possession_won", "Possession Won"),
            ("possession_lost", "Possession Lost"),
            ("minutes_played", "Minutes Played"),
            ("distance_covered", "Distance Covered (km)"),
            ("distance_sprinted", "Distance Sprinted (km)")
        ]
        
        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        for i in range(6):
            self.grid_rowconfigure(i, weight=1 if i in [0, 5] else 0)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Player Statistics collected",
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Player dropdown (reusable scrollable dropdown)
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=self.theme,
            variable=self.player_list_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))
        
        # Info Label
        self.info_label = ctk.CTkLabel(
            self, text="Empty stats couldn't be recognised and require manual entry.\n Please review and update player attributes as necessary.",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=3, column=1, pady=(0, 20))
        
        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self, fg_color=self.theme["colors"]["background"])
        self.stats_grid.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        # Configure subgrid
        self.stats_grid.grid_columnconfigure(0, weight=1)
        self.stats_grid.grid_columnconfigure(1, weight=1)
        for row in range(len(self.stat_definitions)):
            self.stats_grid.grid_rowconfigure(row, weight=1)

        # Populate stats grid
        for i, (stat_key, stat_label) in enumerate(self.stat_definitions):
            self.create_data_row(
                parent_widget=self.stats_grid,
                index=i,
                stat_key=stat_key,
                stat_label=stat_label,
                target_dict=self.stats_vars,
                label_col=0,
                entry_col=1
            )
        
        # Direction subgrid
        self.direction_frame = ctk.CTkFrame(self, fg_color=self.theme["colors"]["background"])
        self.direction_frame.grid(row=5, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)
        self.direction_frame.grid_columnconfigure(3, weight=1)

        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text="Please navigate to the next player's stats",
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Next Outfield Player",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_next_outfield_player_button_press()
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Next Goalkeeper",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_next_goalkeeper_button_press()
        )
        self.next_goalkeeper_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="All Players Added",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.all_players_added_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")
    
    def collect_data(self) -> bool:
        """Extract inputs, validate them, and buffer the player performance data."""
        player_name = self.player_list_var.get()

        # Validate Player Name first
        if player_name in ["", "Click here to select player", "No players found"]:
            self.show_warning("Validation Error", "Please select a valid player from the dropdown before proceeding.")
            return False

        ui_data: Dict[str, Any] = {}
        float_keys = {"distance_covered", "distance_sprinted"}

        # Collect and convert stats
        for stat_key, var in self.stats_vars.items():
            value = var.get()
            if stat_key in float_keys:
                ui_data[stat_key] = safe_float_conversion(value)
            else:
                ui_data[stat_key] = safe_int_conversion(value)

        if self.check_missing_fields(ui_data, dict(self.stat_definitions)):
            return False 

        ui_data["player_name"] = player_name
        ui_data["performance_type"] = "Outfield"

        logger.info(f"Validation passed for {player_name}. Buffering performance data.")
        try:
            self.controller.buffer_player_performance(ui_data)
            logger.debug(f"Buffered data for {player_name}")
            self.show_success("Data Saved", f"Performance data for {player_name} has been saved successfully.")
            return True
        except Exception as e:
            logger.error(f"Error buffering player performance data: {e}", exc_info=True)
            self.show_error("Error Saving Data", f"An error occurred while saving the performance data: \n{str(e)}. \n\nPlease try again.")
            return False

    def on_next_outfield_player_button_press(self) -> None:
        """Buffer current stats, trigger OCR for the next outfield player, and refresh."""
        if not self.collect_data():
            return
        try:
            # Trigger the controller OCR logic for the next player
            self.controller.process_player_stats(gk=False)
            self.controller.show_frame(self.controller.get_frame_class("PlayerStatsFrame"))
        except Exception as e:
            logger.error(f"Failed to process next outfield player stats: {e}", exc_info=True)
            self.show_error("Error Processing Data", f"An error occurred while processing the next player's stats: \n{str(e)}. \n\nPlease try again.")
            return
    
    def on_next_goalkeeper_button_press(self) -> None:
        """Buffer current stats, trigger OCR for the goalkeeper, and transition view."""
        if not self.collect_data():
            return
        try:
            # Trigger the controller OCR logic for the goalkeeper
            self.controller.process_player_stats(gk=True)
            self.controller.show_frame(self.controller.get_frame_class("GKStatsFrame"))
        except Exception as e:
            logger.error(f"Failed to process next goalkeeper stats: {e}", exc_info=True)
            self.show_error("Error Processing Data", f"An error occurred while processing the next goalkeeper's stats: \n{str(e)}. \n\nPlease try again.")
            return
    
    def on_done_button_press(self):
        """Buffer final player stats and command the controller to save the entire match."""
        if not self.collect_data():
            return
        try:
            logger.info("Initiating final match save from GKStatsFrame.")
            self.controller.save_buffered_match()
            self.controller.show_frame(self.controller.get_frame_class("MatchAddedFrame"))
        except Exception as e:
            # Crucial catch for DataPersistenceError to prevent data loss via hard-crash
            logger.error(f"Failed to save the match to persistent storage: {e}", exc_info=True)
            self.show_error("Error Saving Match", f"An error occurred while saving the match data: {str(e)}. Please try again.")
            return

    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields and refresh the dropdown when displayed."""
        self.refresh_player_dropdown(only_outfield=True, remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")