import customtkinter as ctk
import logging
from typing import Any, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import PlayerDropdownMixin, EntryFocusMixin

logger = logging.getLogger(__name__)

class AddInjuryFrame(BaseViewFrame, PlayerDropdownMixin, EntryFocusMixin):
    """A data entry frame for logging a player's injury record."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        """Initialize the AddInjuryFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)

        logger.info("Initializing AddInjuryFrame")

        self.stat_definitions: list[Tuple[str, str]] = [
            ("in_game_date", "In-game Date"),
            ("injury_detail", "Injury Detail"),
            ("time_out", "Time Out")
        ]
        
        self.time_out_unit_var = ctk.StringVar(value="Select unit")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(5):
            self.grid_rowconfigure(i, weight=1 if i in [0, 4] else 0)

        # Main heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Log Player Injury",
            font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))

        # Dropdown to select player
        self.player_dropdown_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.player_dropdown_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))

        # Data subgrid
        self.data_frame = ctk.CTkFrame(self)
        self.data_frame.grid(row=3, column=1, pady=(0, 20))

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
            text="Save Record",
            font=self.fonts["button"],
            command=self.on_done_button_press
        )
        self.done_button.grid(row=4, column=1)
        self.style_submit_button(self.done_button)
        
        self.apply_focus_flourishes(self)

    def create_data_row(self, index: int, data_key: str, data_name: str) -> None:
        """Helper to create a label, entry pair, and optional unit combobox for injury data."""
        data_label = ctk.CTkLabel(
            self.data_frame,
            text=data_name,
            font=self.fonts["body"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")
        
        placeholder_text = "dd/mm/yy" if data_key == "in_game_date" else ""
        is_time_out_row = data_key == "time_out"
        entry_width = 145 if is_time_out_row else 300
        
        data_entry = ctk.CTkEntry(
            self.data_frame,
            font=self.fonts["body"],
            placeholder_text=placeholder_text,
            width=entry_width
        )
        if is_time_out_row:
            data_entry.grid(row=index, column=2, padx=(5, 0), pady=5, sticky="w")
        else:
            data_entry.grid(row=index, column=2, columnspan=2, padx=5, pady=5, sticky="ew")
        self.data_vars[data_key] = data_entry
        
        if is_time_out_row:
            # Drop down to select between days, weeks, months, in a third column next to the entry
            time_out_unit_dropdown = ScrollableDropdown(
                self.data_frame,
                theme=self.theme,
                fonts=self.fonts,
                variable=self.time_out_unit_var,
                values=["Days", "Weeks", "Months"],
                width=145,
                dropdown_height=150,
                placeholder="Select unit"
            )
            time_out_unit_dropdown.grid(row=index, column=3, padx=(0, 5), pady=5)
    
    def on_done_button_press(self):
        """Validates inputs, formats the date safely, and routes to the Controller."""
        player_name = self.player_dropdown_var.get()
        if player_name in ["Select Player", "Click here to select player", "No Players Found", "No Items Found"]:
            self.show_warning("Selection Error", "Please select a player before saving.")
            return

        ui_data = {key: entry.get() for key, entry in self.data_vars.items()}
        key_to_label = dict(self.stat_definitions)
        required_injury_keys = [key for key, _ in self.stat_definitions]
        if not self.check_missing_fields(
            ui_data,
            key_to_label=key_to_label,
            required_keys=required_injury_keys,
            zero_invalid_keys=required_injury_keys,
        ):
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
        in_game_date_str = str(ui_data.get("in_game_date", "")).strip()
        if not self.validate_in_game_date(in_game_date_str):
            return

        try:
            logger.info(f"Validation passed. Saving injury record for {player_name}.")
            self.controller.add_injury_record(player_name, ui_data)
            self.show_success("Data Saved", f"Injury record for {player_name} has been successfully saved.")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save injury data: {e}", exc_info=True)
            self.show_error("Error Saving Data", f"An error occurred: {str(e)}\n\nPlease try again.")
            return

    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        for key, entry in self.data_vars.items():
            entry.delete(0, "end")
            entry.configure(placeholder_text="dd/mm/yy" if key == "in_game_date" else "")

        self.time_out_unit_var.set("Select unit")
        
        self.refresh_player_dropdown(remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")
        
        # Ensure placeholder visibility by moving focus away from entries
        self.after_idle(self.done_button.focus_set)