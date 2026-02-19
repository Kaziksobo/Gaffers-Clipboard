import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.exceptions import UIPopulationError
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion, safe_float_conversion

logger = logging.getLogger(__name__)

class GKStatsFrame(ctk.CTkFrame):
    """Frame for displaying and adding individual goalkeeper match statistics."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the GKStatsFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
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
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Player dropdown (reusable scrollable dropdown)
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=theme,
            variable=self.player_list_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))
        
        # Info Label
        self.info_label = ctk.CTkLabel(
            self, text="Empty stats couldn't be recognised and require manual entry.\n Please review and update player attributes as necessary.",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=3, column=1, pady=(0, 20))
        
        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self, fg_color=theme["colors"]["background"])
        self.stats_grid.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        # Configure subgrid
        self.stats_grid.grid_columnconfigure(0, weight=1)
        self.stats_grid.grid_columnconfigure(1, weight=1)
        for row in range(len(self.stat_definitions)):
            self.stats_grid.grid_rowconfigure(row, weight=1)
        
        # Populate stats grid
        for i, (stat_key, stat_label) in enumerate(self.stat_definitions):
            self.create_stat_row(i, stat_key, stat_label, theme)
        
        # Direction subgrid
        self.direction_frame = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.direction_frame.grid(row=5, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)
        self.direction_frame.grid_columnconfigure(3, weight=1)
        
        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text="Please navigate to the next player's stats",
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Next Outfield Player",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_next_outfield_player_button_press()
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Next Goalkeeper",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_next_goalkeeper_button_press()
        )
        self.next_goalkeeper_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="All Players Added",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.all_players_added_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")
    
    def create_stat_row(self, row: int, stat_key: str, stat_label: str, theme: Dict[str, Any]) -> None:
        """Helper to create a unified entry row for a specific performance statistic."""
        self.stat_label = ctk.CTkLabel(
            self.stats_grid,
            text=stat_label,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.stat_label.grid(row=row, column=0, padx=5, pady=5, sticky="w")
        
        stat_value = ctk.StringVar(value="0")
        self.stats_vars[stat_key] = stat_value
        stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=stat_value,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        stat_entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    
    def populate_stats(self, stats_data: Dict[str, Any]) -> None:
        """Populate the entry fields with OCR-detected statistics.
        
        Args:
            stats (Dict[str, Any]): A dictionary containing performance data keys and values.
            
        Raises:
            UIPopulationError: If the provided stats dictionary is empty.
        """
        logger.debug(f"Populating GKStatsFrame with stats: {stats_data.keys()}")
        if not stats_data:
            raise UIPopulationError("Received no data to populate player statistics.")
        
        for stat_key, _ in self.stat_definitions:
            self.stats_vars[stat_key].set(str(stats_data.get(stat_key, "0")))
        
        logger.debug("GKStatsFrame population complete.")
    
    def collect_data(self) -> None:
        """Extract inputs, validate them, and buffer the player performance data."""
        player_name = self.player_list_var.get()
        
        # Validate Player Name first
        if player_name == "Click here to select player" or player_name == "No players found" or not player_name:
            logger.warning("Validation failed: Missing fields - Player")
            return

        # Convert all stats to integers
        ui_data: Dict[str, Any] = {stat_key: safe_int_conversion(var.get()) for stat_key, var in self.stats_vars.items()}
        
        # Check specifically for None (which indicates empty or invalid input)
        if missing_key_list := [key for key, value in ui_data.items() if value is None]:
            key_to_label = dict(self.stat_definitions)
            missing_labels = [key_to_label.get(key, key) for key in missing_key_list]
            logger.warning(f"Validation failed: Missing fields - {', '.join(missing_labels)}")
            return 
        
        ui_data['player_name'] = player_name
        
        logger.info(f"Validation passed for {player_name}. Buffering performance data.")
        try:
            self.controller.buffer_player_performance(ui_data)
            logger.debug(f"Buffered data for {player_name}")
        except Exception as e:
            logger.error(f"Error buffering player performance data: {e}", exc_info=True)
            raise

    def on_next_outfield_player_button_press(self) -> None:
        """Buffer current stats, trigger OCR for the next outfield player, and refresh."""
        self.collect_data()
        try:
            # Trigger the controller OCR logic for the next player
            self.controller.process_player_stats(gk=False)
            self.controller.show_frame(self.controller.get_frame_class("PlayerStatsFrame"))
        except Exception as e:
            logger.error(f"Failed to process next outfield player stats: {e}", exc_info=True)
    
    def on_next_goalkeeper_button_press(self) -> None:
        """Buffer current stats, trigger OCR for the goalkeeper, and transition view."""
        self.collect_data()
        try:
            # Trigger the controller OCR logic for the goalkeeper
            self.controller.process_player_stats(gk=True)
            # Assuming you have a separate frame for GK stats
            self.controller.show_frame(self.controller.get_frame_class("GKStatsFrame"))
        except Exception as e:
            logger.error(f"Failed to process next goalkeeper stats: {e}", exc_info=True)
    
    def on_done_button_press(self):
        """Buffer final player stats and command the controller to save the entire match."""
        self.collect_data()
        try:
            logger.info("Initiating final match save from PlayerStatsFrame.")
            self.controller.save_buffered_match()
            self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
        except Exception as e:
            # Crucial catch for DataPersistenceError to prevent data loss via hard-crash
            logger.error(f"Failed to save the match to persistent storage: {e}", exc_info=True)
    
    def refresh_player_dropdown(self) -> None:
        """Fetch the latest active player list from the database and update the dropdown."""
        names = self.controller.get_all_player_names(only_outfield=True)
        self.player_dropdown.set_values(names or ["No players found"])

    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields and refresh the dropdown when displayed."""
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")