import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion, safe_float_conversion
from src.exceptions import DuplicateRecordError

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import OCRDataMixin, PlayerDropdownMixin

logger = logging.getLogger(__name__)

class GKStatsFrame(BaseViewFrame, OCRDataMixin, PlayerDropdownMixin):
    """Frame for displaying and adding individual goalkeeper match statistics."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the GKStatsFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        
        logger.info("Initializing GKStatsFrame")
        
        self.stats_vars: Dict[str, ctk.StringVar] = {}
        self.stat_definitions: List[Tuple[str, str]] = [
            ("shots_against", "Shots Against"),
            ("shots_on_target", "Shots On Target"),
            ("saves", "Saves"),
            ("goals_conceded", "Goals Conceded"),
            ("save_success_rate", "Save Success Rate (%)"),
            ("punch_saves", "Punch Saves"),
            ("rush_saves", "Rush Saves"),
            ("penalty_saves", "Penalty Saves"),
            ("penalty_goals_conceded", "Penalty Goals Conceded"),
            ("shoot_out_saves", "Shoot-out Saves"),
            ("shoot_out_goals_conceded", "Shoot-out Goals Conceded")
        ]
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Goalkeeper Statistics collected",
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
        if player_name in ["", "Click here to select player", "No Players Found"]:
            self.show_warning(
                title="No player selected",
                message="Please select a player from the dropdown before proceeding."
            )
            return False

        # Convert all stats to integers
        ui_data: Dict[str, Any] = {stat_key: safe_int_conversion(var.get()) for stat_key, var in self.stats_vars.items()}
        
        if not self.check_missing_fields(ui_data, dict(self.stat_definitions)):
            return False
        
        percentage_keys = {"save_success_rate"}
        percentage_data = {k: v for k, v in ui_data.items() if k in percentage_keys}
        percentage_defs = [(k, label) for k, label in self.stat_definitions if k in percentage_keys]
        if not self.validate_attr_range(percentage_data, percentage_defs, min_val=0, max_val=100):
            return False
        
        saves = ui_data.get("saves")
        shots_on_target = ui_data.get("shots_on_target")
        if saves is not None and shots_on_target is not None and saves > shots_on_target:
            if not self.soft_validate(
                "saves_vs_shots",
                (saves, shots_on_target),
                "Data Inconsistency",
                f"The number of saves ({saves}) exceeds the number of shots on target ({shots_on_target}). Please double-check these values.",
            ):
                return False
        
        goals_conceded = ui_data.get("goals_conceded")
        if saves is not None and goals_conceded is not None and saves + goals_conceded > shots_on_target:
            if not self.soft_validate(
                "saves_plus_goals_vs_shots",
                (saves, goals_conceded, shots_on_target),
                "Data Inconsistency",
                f"The combined total of saves ({saves}) and goals conceded ({goals_conceded}) exceeds the number of shots on target ({shots_on_target}). Please double-check these values.",
            ):
                return False
        if goals_conceded is not None and shots_on_target is not None and goals_conceded > shots_on_target:
            if not self.soft_validate(
                "goals_conceded_vs_shots",
                (goals_conceded, shots_on_target),
                "Data Inconsistency",
                f"The number of goals conceded ({goals_conceded}) exceeds the number of shots on target ({shots_on_target}). Please double-check these values.",
            ):
                return False
        
        stat_max_rules = [
            ("shots_against", "Shots Against", 25),
            ("shots_on_target", "Shots On Target", 25),
            ("saves", "Saves", 25),
            ("goals_conceded", "Goals Conceded", 10),
            ("punch_saves", "Punch Saves", 15),
            ("rush_saves", "Rush Saves", 15),
            ("penalty_saves", "Penalty Saves", 5),
            ("penalty_goals_conceded", "Penalty Goals Conceded", 5),
            ("shoot_out_saves", "Shoot-out Saves", 5),
            ("shoot_out_goals_conceded", "Shoot-out Goals Conceded", 5)
        ]
        for stat_key, stat_label, max_val in stat_max_rules:
            if not self.validate_stat_max(ui_data, stat_key, stat_label, max_val):
                return False
        
        ui_data["player_name"] = player_name
        ui_data["performance_type"] = "GK"
        
        logger.info(f"Validation passed for {player_name}. Buffering performance data.")
        try:
            self.controller.buffer_player_performance(ui_data)
            logger.debug(f"Buffered data for {player_name}")
            self.show_success("Data Saved", f"Performance data for {player_name} has been saved successfully.")
            return True
        except DuplicateRecordError as e:
            logger.error(f"Duplicate record error while buffering data for {player_name}: {e}", exc_info=True)
            self.show_error("Duplicate Record", f"Performance data for {player_name} has already been buffered. Each player's performance can only be added once per match.")
            return False
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
        self._dismissed_warnings.clear()
        
        self.refresh_player_dropdown(only_gk=True, remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")