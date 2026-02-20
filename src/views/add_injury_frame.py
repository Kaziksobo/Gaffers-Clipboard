import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion
from datetime import datetime

logger = logging.getLogger(__name__)

class AddInjuryFrame(ctk.CTkFrame):
    """A data entry frame for logging a player's injury record."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddInjuryFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller

        logger.info("Initializing AddInjuryFrame")

        self.data_entries: Dict[str, ctk.CTkEntry] = {}
        self.stat_definitions: List[Tuple[str, str]] = [
            ("in_game_date", "In-game Date"),
            ("injury_detail", "Injury Detail"),
            ("time_out", "Time Out")
        ]
        self.player_names = []
        self.time_out_unit_var = ctk.StringVar(value="Select unit")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        for i in range(6):
            self.grid_rowconfigure(i, weight=1 if i in [0, 5] else 0)

        # Main heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Add player injury record",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))

        # Dropdown to select player
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

        # Season entry
        self.season_entry = ctk.CTkEntry(
            self,
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["entry_fg"],
            text_color=theme["colors"]["primary_text"],
            width=250,
            placeholder_text="Season (e.g. 24/25)"
        )
        self.season_entry.grid(row=3, column=1, pady=(0, 20))

        # Data subgrid
        self.data_frame = ctk.CTkFrame(
            self,
            fg_color=theme["colors"]["background"]
        )
        self.data_frame.grid(row=4, column=1, pady=(0, 20))

        self.data_frame.grid_columnconfigure(0, weight=1)
        self.data_frame.grid_columnconfigure(1, weight=0)
        self.data_frame.grid_columnconfigure(2, weight=0)
        self.data_frame.grid_columnconfigure(3, weight=0)
        self.data_frame.grid_columnconfigure(4, weight=1)

        for i in range(len(self.stat_definitions)):
            self.data_frame.grid_rowconfigure(i, weight=1)

        for i, (key, name) in enumerate(self.stat_definitions):
            self.create_data_row(i, key, name, theme)

        # Done Button
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=self.on_done_button_press
        )
        self.done_button.grid(row=5, column=1)
    
    def create_data_row(self, index: int, data_key: str, data_name: str, theme: Dict[str, Any]) -> None:
        """Helper to create a label, entry pair, and optional unit combobox for injury data."""
        data_label = ctk.CTkLabel(
            self.data_frame,
            text=data_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")
        
        placeholder_text = "dd/mm/yy" if data_key == "in_game_date" else ""
        
        data_entry = ctk.CTkEntry(
            self.data_frame,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"],
            placeholder_text=placeholder_text,
            width=300
        )
        data_entry.grid(row=index, column=2, padx=5, pady=5, sticky="ew")
        self.data_entries[data_key] = data_entry
        
        if data_key == "time_out":
            # Drop down to select between days, weeks, months, in a third column next to the entry
            time_out_unit_dropdown = ScrollableDropdown(
                self.data_frame,
                theme=theme,
                variable=self.time_out_unit_var,
                values=["Days", "Weeks", "Months"],
                width=150,
                dropdown_height=150,
                placeholder="Select unit"
            )
            time_out_unit_dropdown.grid(row=index, column=3, padx=5, pady=5)
    
    def on_done_button_press(self):
        """Validates inputs, formats the date safely, and routes to the Controller."""
        injury_data: Dict[str, Any] = {key: entry.get().strip() for key, entry in self.data_entries.items()}
        player_name = self.player_list_var.get()
        season = self.season_entry.get().strip()
        injury_data["time_out_unit"] = self.time_out_unit_var.get()

        # convert time_out to an integer and store in injury_data, if possible
        time_out_str = injury_data.get("time_out", "")
        time_out_int = safe_int_conversion(time_out_str)
        injury_data["time_out"] = time_out_int if time_out_int is not None else None
        
        missing_fields = []
        if player_name == "Click here to select player" or player_name == "No players found" or not player_name:
            missing_fields.append("Player")
        if not season:
            missing_fields.append("Season")
        missing_fields.extend(
            key.replace("_", " ").title()
            for key, value in injury_data.items()
            if not value
        )
        if missing_fields:
            logger.warning(f"Cannot add injury record. Missing fields: {', '.join(missing_fields)}")
            return
        
        # Preemptive Date Validation
        in_game_date_str = str(injury_data.get("in_game_date", ""))
        try:
            datetime.strptime(in_game_date_str, "%d/%m/%y")
        except ValueError:
            logger.warning(f"Cannot add injury record. Invalid date format for 'In-game Date'. Expected format: dd/mm/yy, got: '{in_game_date_str}'")
            return

        try:
            logger.info(f"Validation passed. Saving injury record for {player_name}.")
            self.controller.add_injury_record(player_name, season, injury_data)
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save injury data: {e}", exc_info=True)
    
    def refresh_player_dropdown(self) -> None:
        """Fetch the latest player list from the database and update the custom dropdown."""
        names = self.controller.get_all_player_names()
        self.player_dropdown.set_values(names)
        
        if not names:
            self.player_dropdown.set_value("No players found")

    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        for key, entry in self.data_entries.items():
            entry.delete(0, "end")
            entry.configure(placeholder_text="dd/mm/yy" if key == "in_game_date" else "")

        self.season_entry.delete(0, "end")
        self.season_entry.configure(placeholder_text="Season (e.g. 24/25)")
        self.time_out_unit_var.set("Select unit")
        
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")
        
        # Ensure placeholder visibility by moving focus away from the season entry
        self.after_idle(self.done_button.focus_set)