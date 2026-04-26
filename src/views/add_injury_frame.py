"""UI frame for recording player injury history entries.

This module defines AddInjuryFrame, a CustomTkinter view that captures injury
records for an existing player. It manages player selection, injury detail
entry, time-out duration plus unit selection, and validation before
delegating persistence and navigation to the controller.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import (
    AddInjuryFrameControllerProtocol,
    BaseViewThemeProtocol,
)
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, PlayerDropdownMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class AddInjuryFrame(BaseViewFrame, PlayerDropdownMixin, EntryFocusMixin):
    """Data-entry frame for logging a player's injury record.

    The frame keeps injury-specific UI behavior localized while relying on the
    controller to perform data persistence and frame navigation.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: AddInjuryFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the injury-entry form.

        Constructs the heading, player selection dropdown, and dynamic injury
        input rows driven by stat definitions. The constructor also wires
        submit behavior, initializes the time-out unit selector state, and
        applies focus styling across input widgets.

        Form field widgets are registered in shared data mappings so later
        validation and payload assembly can operate through a unified path.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (AddInjuryFrameControllerProtocol): The main
                application controller.
            theme (BaseViewThemeProtocol): The application's theme
                configuration.
        """
        super().__init__(parent, controller, theme)
        self.controller: AddInjuryFrameControllerProtocol = controller

        logger.info("Initializing AddInjuryFrame")

        self.stat_definitions: list[tuple[str, str]] = [
            ("in_game_date", "In-game Date"),
            ("injury_detail", "Injury Detail"),
            ("time_out", "Time Out"),
        ]

        self.time_out_unit_var = ctk.StringVar(value="Select unit")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct and arrange widgets for the injury logging form.

        Builds the heading, player selector, injury detail rows, and submit
        button so users can record injury events for existing players.
        """
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(5):
            self.grid_rowconfigure(i, weight=1 if i in [0, 4] else 0)

        # Main heading
        self.main_heading = ctk.CTkLabel(
            self, text="Log Player Injury", font=self.fonts["title"]
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
            placeholder="Click here to select player",
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
            self._create_entry_row(i, key, name)

        # Done Button
        self.done_button = ctk.CTkButton(
            self,
            text="Save Record",
            font=self.fonts["button"],
            command=self._on_done_button_press,
        )
        self.done_button.grid(row=4, column=1)
        self.style_submit_button(self.done_button)

        self.apply_focus_flourishes(self)

    def on_show(self) -> None:
        """Reset form state each time the frame becomes active.

        Clears all injury input entries, restores default placeholders, resets
        the time-out unit selection, refreshes available player options, and
        returns focus to a non-entry widget so placeholders remain visible.
        """
        for key, entry in self.data_vars.items():
            entry.delete(0, "end")
            entry.configure(
                placeholder_text="dd/mm/yy" if key == "in_game_date" else ""
            )

        self.time_out_unit_var.set("Select unit")
        self.time_out_unit_dropdown.set_value("Select Unit")

        self.refresh_player_dropdown(remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")

        # Ensure placeholder visibility by moving focus away from entries
        self.after_idle(self.done_button.focus_set)

    def _create_entry_row(self, index: int, data_key: str, data_name: str) -> None:
        """Create one injury input row within the data subgrid.

        Each row includes a label and entry widget; the time-out row also adds
        a unit dropdown for days, weeks, or months. This helper keeps row
        construction consistent and ensures data widgets are registered for
        later validation and submission.

        Args:
            index (int): Grid row index within the data frame.
            data_key (str): Internal payload key associated with the row.
            data_name (str): User-facing label text for the row.
        """
        data_label = ctk.CTkLabel(
            self.data_frame, text=data_name, font=self.fonts["body"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")

        placeholder_text = "dd/mm/yy" if data_key == "in_game_date" else ""
        is_time_out_row = data_key == "time_out"
        entry_width = 145 if is_time_out_row else 300

        data_entry = ctk.CTkEntry(
            self.data_frame,
            font=self.fonts["body"],
            placeholder_text=placeholder_text,
            width=entry_width,
        )
        if is_time_out_row:
            data_entry.grid(row=index, column=2, padx=(5, 0), pady=5, sticky="w")
        else:
            data_entry.grid(
                row=index, column=2, columnspan=2, padx=5, pady=5, sticky="ew"
            )
        self.data_vars[data_key] = data_entry

        if is_time_out_row:
            # Drop down to select between days, weeks, months,
            # in a third column next to the entry
            self.time_out_unit_dropdown = ScrollableDropdown(
                self.data_frame,
                theme=self.theme,
                fonts=self.fonts,
                variable=self.time_out_unit_var,
                values=["Days", "Weeks", "Months"],
                width=145,
                dropdown_height=150,
                placeholder="Select unit",
            )
            self.time_out_unit_dropdown.grid(row=index, column=3, padx=(0, 5), pady=5)

    def _on_done_button_press(self) -> None:
        """Validate injury inputs, normalize values, and trigger save flow.

        This method is the primary submit pipeline for the frame. It resolves
        the selected player, validates required injury fields, enforces a
        selected time-out unit, converts time-out duration to an integer value,
        and validates in-game date formatting.

        When validation succeeds, it delegates persistence to the controller,
        shows success feedback, and navigates back to the player library.
        Validation or persistence failures short-circuit with contextual
        warning or error messaging.
        """
        player_name = self.resolve_selected_player_name(self.player_dropdown_var.get())
        if player_name is None:
            self.show_warning(
                "Selection Error", "Please select a player before saving."
            )
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
            logger.warning(
                (
                    f"Invalid input for 'Time Out': {ui_data['time_out']}. ",
                    "Must be a number.",
                )
            )
            self.show_warning(
                "Input Error",
                (
                    "The 'Time Out' field must be a number. "
                    "Please correct it and try again."
                ),
            )
            return

        # Preemptive Date Validation
        in_game_date_str = str(ui_data.get("in_game_date", "")).strip()
        if not self.validate_in_game_date(in_game_date_str):
            return

        try:
            logger.info(f"Validation passed. Saving injury record for {player_name}.")
            self.controller.add_injury_record(player_name, ui_data)
            self.show_success(
                "Data Saved",
                f"Injury record for {player_name} has been successfully saved.",
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save injury data: {e}", exc_info=True)
            self.show_error(
                "Error Saving Data", f"An error occurred: {e!s}\n\nPlease try again."
            )
            return
