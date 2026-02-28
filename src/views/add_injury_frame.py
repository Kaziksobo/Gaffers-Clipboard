import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion
from datetime import datetime

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import PlayerDropdownMixin

logger = logging.getLogger(__name__)

class AddInjuryFrame(BaseViewFrame, PlayerDropdownMixin):
    """A data entry frame for logging a player's injury record."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddInjuryFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)

        logger.info("Initializing AddInjuryFrame")

        self.stat_definitions: List[Tuple[str, str]] = [
            ("in_game_date", "In-game Date"),
            ("injury_detail", "Injury Detail"),
            ("time_out", "Time Out")
        ]
        
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
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))

        # Dropdown to select player
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

        # Season entry
        self.season_entry = ctk.CTkEntry(
            self,
            font=self.theme["fonts"]["body"],
            fg_color=self.theme["colors"]["entry_fg"],
            text_color=self.theme["colors"]["primary_text"],
            width=250,
            placeholder_text="Season (e.g. 24/25)"
        )
        self.season_entry.grid(row=3, column=1, pady=(0, 20))

        # Data subgrid
        self.data_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme["colors"]["background"]
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
            self.create_data_row(i, key, name)

        # Done Button
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=self.on_done_button_press
        )
        self.done_button.grid(row=5, column=1)
    
    def create_data_row(self, index: int, data_key: str, data_name: str) -> None:
        """Helper to create a label, entry pair, and optional unit combobox for injury data."""
        data_label = ctk.CTkLabel(
            self.data_frame,
            text=data_name,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")
        
        placeholder_text = "dd/mm/yy" if data_key == "in_game_date" else ""
        
        data_entry = ctk.CTkEntry(
            self.data_frame,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            placeholder_text=placeholder_text,
            width=300
        )
        data_entry.grid(row=index, column=2, padx=5, pady=5, sticky="ew")
        self.data_vars[data_key] = data_entry
        
        if data_key == "time_out":
            # Drop down to select between days, weeks, months, in a third column next to the entry
            time_out_unit_dropdown = ScrollableDropdown(
                self.data_frame,
                theme=self.theme,
                variable=self.time_out_unit_var,
                values=["Days", "Weeks", "Months"],
                width=150,
                dropdown_height=150,
                placeholder="Select unit"
            )
            time_out_unit_dropdown.grid(row=index, column=3, padx=5, pady=5)
    
    def on_done_button_press(self):
        """Validates inputs, formats the date safely, and routes to the Controller."""
        player_name = self.player_dropdown_var.get()
        if player_name in ["Select Player", "Click here to select player", "No players found"]:
            self.show_warning("Selection Error", "Please select a player before saving.")
            return
        
        ui_data = {key: entry.get() for key, entry in self.data_vars.items()}
        key_to_label = {key: label for key, label in self.stat_definitions}
        if self.check_missing_fields(ui_data, key_to_label=key_to_label, required_keys=[key for key, _ in self.stat_definitions]):
            return
        
        season = self.validate_season(self.season_entry.get())
        if season is None:
            return
        
        time_out_unit = self.time_out_unit_var.get()
        if time_out_unit in ["Select unit", ""]:
            self.show_warning("Selection Error", "Please select a unit for 'Time Out'.")
            return
        ui_data["time_out_unit"] = time_out_unit
        
        # Convert time_out to an integer if possible, otherwise show a warning
        try:
            ui_data["time_out"] = safe_int_conversion(ui_data["time_out"])
        except ValueError:
            logger.warning(f"Invalid input for 'Time Out': {ui_data['time_out']}. Must be a number.")
            self.show_warning("Input Error", "The 'Time Out' field must be a number. Please correct it and try again.")
            return

        # Preemptive Date Validation
        in_game_date_str = str(ui_data.get("in_game_date", ""))
        try:
            datetime.strptime(in_game_date_str, "%d/%m/%y")
        except ValueError:
            logger.warning(f"Cannot add injury record. Invalid date format for 'In-game Date'. Expected format: dd/mm/yy, got: '{in_game_date_str}'")
            self.show_warning("Input Error", "The 'In-game Date' field must be in the format dd/mm/yy. Please correct it and try again.")
            return

        try:
            logger.info(f"Validation passed. Saving injury record for {player_name}.")
            self.controller.add_injury_record(player_name, season, ui_data)
            self.show_success("Data Saved", f"Injury record for {player_name} in season {season} has been successfully saved.")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save injury data: {e}", exc_info=True)
            self.show_error("Error Saving Data", f"An error occurred: {str(e)}\n\nPlease try again.")
            return

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