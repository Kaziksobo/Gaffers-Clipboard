import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.views.widgets.scrollable_sidebar import ScrollableSidebar
from src.utils import safe_int_conversion, safe_float_conversion
from src.exceptions import DuplicateRecordError

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import PlayerDropdownMixin, OCRDataMixin, PerformanceSidebarMixin

logger = logging.getLogger(__name__)

# Valid positions that match PositionType from custom_types
VALID_POSITIONS = {"GK", "LB", "RB", "CB", "LWB", "RWB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST", "CF"}

class PlayerStatsFrame(BaseViewFrame, PlayerDropdownMixin, OCRDataMixin, PerformanceSidebarMixin):
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
        for i in range(7):
            self.grid_rowconfigure(i, weight=1 if i in [0, 6] else 0)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Review Outfield Player Stats",
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
            placeholder="Click here to select player",
            command=self._on_player_selected
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))
        
        # Position select
        self.position_frame = ctk.CTkFrame(self, fg_color=self.theme["colors"]["background"])
        self.position_frame.grid(row=3, column=1, padx=20, pady=(0, 20), sticky="nsew")
        self.position_frame.grid_columnconfigure(0, weight=1)
        self.position_frame.grid_columnconfigure(1, weight=0)
        self.position_frame.grid_columnconfigure(2, weight=0)
        self.position_frame.grid_columnconfigure(3, weight=1)
        self.position_frame.grid_rowconfigure(0, weight=1)
        self.position_label = ctk.CTkLabel(
            self.position_frame,
            text="Position(s) played:",
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["body"],
        )
        self.position_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.position_entry = ctk.CTkEntry(
            self.position_frame,
            placeholder_text="e.g. RW, LW",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
        )
        self.position_entry.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        # Info Label
        self.info_label = ctk.CTkLabel(
            self, text="Please review the captured player performance data.\nFill in any missing fields and correct any inaccuracies.",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=4, column=1, pady=(0, 20))
        
        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self, fg_color=self.theme["colors"]["background"])
        self.stats_grid.grid(row=5, column=1, pady=(0, 20), sticky="nsew")
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
        self.direction_frame.grid(row=6, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)
        self.direction_frame.grid_columnconfigure(3, weight=1)

        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text="To scan another player, navigate to their in-game stats:",
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan an Outfield Player",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_next_outfield_player_button_press()
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan a Goalkeeper",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_next_goalkeeper_button_press()
        )
        self.next_goalkeeper_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="Save all and Finish Match",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.all_players_added_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")
        
        self.performance_sidebar = ScrollableSidebar(
            parent=self,
            theme=self.theme,
            display_keys=["player_name", "positions_played"],
            remove_button=True,
            remove_callback=self.remove_player_from_buffer,
            title="Buffered Players",
        )
        self.performance_sidebar.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    def _on_player_selected(self, name: str) -> None:
        bio = self.controller.get_player_bio(name)
        if bio is None:
            return
        if positions := bio.get("positions", []):
            self.position_entry.delete(0, "end")
            self.position_entry.insert(0, positions[-1])
    
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

        if not self.check_missing_fields(ui_data, dict(self.stat_definitions)):
            return False 
        
        percentage_keys = {"shot_accuracy", "pass_accuracy", "dribble_success_rate", "tackle_success_rate"}
        percentage_data = {k: v for k, v in ui_data.items() if k in percentage_keys}
        percentage_defs = [(k, label) for k, label in self.stat_definitions if k in percentage_keys]
        if not self.validate_attr_range(percentage_data, percentage_defs, min_val=0, max_val=100):
            return False
        
        if not self.validate_minutes_played(ui_data.get("minutes_played")):
            return False
        
        if not self.validate_pair_hard(ui_data, [
            ("goals", "Goals", "shots", "Shots"),
            ("assists", "Assists", "passes", "Passes"),
            ("distance_sprinted", "Distance Sprinted", "distance_covered", "Distance Covered"),
        ]):
            return False
        
        stat_max_rules = [
            ("goals", "Goals", 8),
            ("assists", "Assists", 8),
            ("shots", "Shots", 20),
            ("passes", "Passes", 100),
            ("dribbles", "Dribbles", 50),
            ("tackles", "Tackles", 50),
            ("offsides", "Offsides", 8),
            ("fouls_committed", "Fouls Committed", 8),
            ("possession_won", "Possession Won", 50),
            ("possession_lost", "Possession Lost", 50),
            ("distance_covered", "Distance Covered (km)", 15),
            ("distance_sprinted", "Distance Sprinted (km)", 10)
        ]

        for key, label, max_val in stat_max_rules:
            if not self.validate_stat_max(ui_data, key, label, max_value=max_val):
                return False
        
        ui_data["player_name"] = player_name
        ui_data["performance_type"] = "Outfield"
        
        positions_played = self.position_entry.get().strip()
        if not positions_played:
            self.show_warning("Validation Warning", "No positions entered. Please specify at least one position played (e.g. RW, LW).")
            return False
        positions = [pos.strip().upper() for pos in positions_played.split(",") if pos.strip()]
        if not positions:
            self.show_warning("Validation Warning", "Invalid positions format. Please enter positions separated by commas (e.g. RW, LW).")
            return False
        for pos in positions:
            if pos not in VALID_POSITIONS:
                self.show_warning("Validation Warning", f"Invalid position '{pos}'. Please enter valid positions (e.g. RW, LW).")
                return False
        ui_data["positions_played"] = positions
        

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
            logger.error(f"Unexpected error while buffering data for {player_name}: {e}", exc_info=True)
            self.show_error("Buffering Error", f"An unexpected error occurred while saving data for {player_name}: {str(e)}. Please try again.")
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
        self.refresh_player_dropdown(only_outfield=True, remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")
        
        self.refresh_performance_sidebar()
        
        self.position_entry.delete(0, "end")
        self.position_entry.configure(placeholder_text="e.g. RW, LW")