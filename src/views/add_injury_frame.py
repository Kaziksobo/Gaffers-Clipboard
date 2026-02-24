import customtkinter as ctk
import logging
import re
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.views.widgets.custom_alert import CustomAlert
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
        self.theme = theme

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
        self.data_entries[data_key] = data_entry
        
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
        injury_data: Dict[str, Any] = {key: entry.get().strip() for key, entry in self.data_entries.items()}
        player_name = self.player_list_var.get()
        season = self.season_entry.get().strip()
        injury_data["time_out_unit"] = self.time_out_unit_var.get()

        # Check if the season is in a valid format (e.g. "24/25") using a simple regex
        # If the season is in format "2024/2025", convert it to "24/25"
        # If the format is completely wrong, just set it to None
        if re.match(r'^\d{2}/\d{2}$', season):
            pass
        elif re.match(r'^\d{4}/\d{4}$', season):
            season = f'{season[2:4]}/{season[7:9]}'
        else:
            season = None
        
        # Check if the time_out_unit is still the placeholder value and if so, set it to None
        if injury_data["time_out_unit"] == "Select unit":
            injury_data["time_out_unit"] = None
        

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
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Missing Information",
                message=f"The following required fields are missing: {', '.join(missing_fields)}. Please fill them in before proceeding.",
                alert_type="warning",
            )
            return

        # Preemptive Date Validation
        in_game_date_str = str(injury_data.get("in_game_date", ""))
        try:
            datetime.strptime(in_game_date_str, "%d/%m/%y")
        except ValueError:
            logger.warning(f"Cannot add injury record. Invalid date format for 'In-game Date'. Expected format: dd/mm/yy, got: '{in_game_date_str}'")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Invalid Date Format",
                message="The 'In-game Date' field must be in the format dd/mm/yy. Please correct the date and try again.",
                alert_type="warning",
            )
            return

        try:
            logger.info(f"Validation passed. Saving injury record for {player_name}.")
            self.controller.add_injury_record(player_name, season, injury_data)
            CustomAlert(
                parent=self,
                theme = self.theme,
                title="Data Saved",
                message=f"Injury data for {player_name} in season {season} has been successfully saved.",
                alert_type="success",
                success_timeout=2
            )
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save injury data: {e}", exc_info=True)
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Error Saving Data",
                message=f"An error occurred while saving the injury data: {str(e)}. Please try again.",
                alert_type="error",
            )
            return
    
    def refresh_player_dropdown(self) -> None:
        """Fetch the latest player list from the database and update the custom dropdown."""
        names = self.controller.get_all_player_names()
        if not names:
            logger.warning("No players found in the database to populate the dropdown.")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="No Players Found",
                message="No players were found in the database. Please add players to the library before adding injury information.",
                alert_type="warning",
                options=["Return to Library"],
            )
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
            return
        self.player_names = names or ["No players found"]
        self.player_dropdown.set_values(self.player_names)

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