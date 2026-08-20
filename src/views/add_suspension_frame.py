"""UI frame for recording player suspension history entries.

This module defines AddSuspensionFrame, a CustomTkinter view that captures
suspension records for an existing player. It manages player selection,
in-game date entry, reason selection, and matches-out entry before
delegating persistence and navigation to the controller.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import (
    AddSuspensionFrameControllerProtocol,
    BaseViewThemeProtocol,
)
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, PlayerDropdownMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)

REASON_OPTIONS: list[str] = ["Red Card", "Accumulated Yellow Cards", "Other"]


class AddSuspensionFrame(BaseViewFrame, PlayerDropdownMixin, EntryFocusMixin):
    """Data-entry frame for logging a player's suspension record.

    The frame keeps suspension-specific UI behavior localized while relying
    on the controller to perform data persistence and frame navigation.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: AddSuspensionFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the suspension-entry form.

        Constructs the heading, player selection dropdown, in-game date
        entry, reason selection, and matches-out entry. The constructor also
        wires submit behavior and applies focus styling across input widgets.

        Suspension fields are generated from ``self.stat_definitions`` so UI
        labels and payload keys remain synchronized in one canonical mapping.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (AddSuspensionFrameControllerProtocol): The main
                application controller.
            theme (BaseViewThemeProtocol): The application's theme
                configuration.
        """
        super().__init__(parent, controller, theme)
        self.controller: AddSuspensionFrameControllerProtocol = controller

        logger.info("Initializing AddSuspensionFrame")

        self.stat_definitions: list[tuple[str, str]] = [
            ("matches_out", "Matches Out"),
            ("suspension_detail", "Suspension Detail (Optional)"),
        ]

        self.reason_var = ctk.StringVar(value="Select reason")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct and arrange widgets for the suspension logging form.

        Builds the heading, player selector, in-game date entry, reason
        dropdown, and matches-out/detail rows so users can record suspension
        events for existing players.
        """
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=0)
        self.grid_rowconfigure(6, weight=1)

        # Main heading
        self.main_heading = ctk.CTkLabel(
            self, text="Log Player Suspension", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(80, 10))

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

        # In-game Date mini frame
        self.in_game_date_frame = ctk.CTkFrame(self)
        self.in_game_date_frame.grid(
            row=3, column=1, padx=(20, 0), pady=(0, 20), sticky="ew"
        )
        self.in_game_date_frame.grid_columnconfigure(0, weight=1)
        self.in_game_date_frame.grid_columnconfigure(1, weight=0)
        self.in_game_date_frame.grid_columnconfigure(2, weight=0)
        self.in_game_date_frame.grid_columnconfigure(3, weight=1)
        self.in_game_date_frame.grid_rowconfigure(0, weight=1)
        self.in_game_date_frame.grid_rowconfigure(1, weight=0)
        self.in_game_date_frame.grid_rowconfigure(2, weight=1)

        self.in_game_date_label = ctk.CTkLabel(
            self.in_game_date_frame,
            text="Enter the in-game date for this suspension:",
            font=self.fonts["body"],
        )
        self.in_game_date_label.grid(row=1, column=1, padx=(20, 0), sticky="w")
        self.in_game_date_entry = ctk.CTkEntry(
            self.in_game_date_frame,
            font=self.fonts["body"],
            width=200,
            placeholder_text="dd/mm/yy",
        )
        self.in_game_date_entry.grid(row=1, column=2, padx=(20, 0), sticky="e")

        # Suspension data subgrid
        self.data_frame = ctk.CTkFrame(self)
        self.data_frame.grid(row=4, column=1, pady=(0, 20))

        self.data_frame.grid_columnconfigure(0, weight=1)
        self.data_frame.grid_columnconfigure(1, weight=0)
        self.data_frame.grid_columnconfigure(2, weight=0)
        self.data_frame.grid_columnconfigure(3, weight=1)

        for i in range(3):
            self.data_frame.grid_rowconfigure(i, weight=1)

        # Row 0: Reason dropdown, its own full row (not paired with a number
        # field the way the injury form's time-out unit dropdown is), since
        # Reason and Matches Out are independent fields, not one compound value
        self.reason_label = ctk.CTkLabel(
            self.data_frame, text="Reason", font=self.fonts["body"]
        )
        self.reason_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        self.reason_dropdown = ScrollableDropdown(
            self.data_frame,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.reason_var,
            values=REASON_OPTIONS,
            width=300,
            dropdown_height=120,
            placeholder="Select reason",
        )
        self.reason_dropdown.grid(row=0, column=2, sticky="ew", padx=5, pady=5)

        # Row 1: Matches Out, Row 2: Suspension Detail (Optional)
        for i, (key, label) in enumerate(self.stat_definitions, start=1):
            self.create_data_row(
                parent_widget=self.data_frame,
                index=i,
                stat_key=key,
                stat_label=label,
                target_dict=self.data_vars,
                entry_width=300 if key == "suspension_detail" else 140,
            )

        # Done Button
        self.done_button = ctk.CTkButton(
            self,
            text="Save Suspension",
            font=self.fonts["button"],
            command=self._on_done_button_press,
        )
        self.done_button.grid(row=5, column=1)
        self.style_submit_button(self.done_button)

        self.apply_focus_flourishes(self)

    def on_show(self) -> None:
        """Reset form state each time the frame becomes active.

        Clears all suspension input fields, restores default placeholders,
        resets the reason selection, refreshes available player options, and
        returns focus to a non-entry widget so placeholders remain visible.
        """
        for var in self.data_vars.values():
            var.set("")

        self.reason_var.set("Select reason")
        self.reason_dropdown.set_value("Select reason")

        self.refresh_player_dropdown(remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")

        self.in_game_date_entry.delete(0, "end")
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")

        # Ensure placeholder visibility by moving focus away from entries
        self.after_idle(self.done_button.focus_set)

    def _on_done_button_press(self) -> None:
        """Validate suspension inputs, normalize values, and trigger save flow.

        This method is the primary submit pipeline for the frame. It resolves
        the selected player, validates required suspension fields, enforces a
        selected reason, converts matches-out to an integer value, and
        validates in-game date formatting.

        When validation succeeds, it delegates persistence to the controller,
        shows success feedback, and navigates back to the player library.
        Validation or persistence failures short-circuit with contextual
        warning or error messaging.
        """
        player_name = self.resolve_selected_player_name(self.player_dropdown_var.get())
        if player_name is None:
            self.show_warning(
                title="No Player Selected",
                message="Please select a player from the dropdown before saving.",
            )
            return

        ui_data: dict[str, str | int] = {
            key: var.get() for key, var in self.data_vars.items()
        }
        key_to_label = dict(self.stat_definitions)
        if not self.check_missing_fields(
            ui_data,
            key_to_label=key_to_label,
            required_keys=["matches_out"],
            zero_invalid_keys=["matches_out"],
        ):
            return

        reason = self.reason_var.get()
        if reason in ("Select reason", ""):
            self.show_warning(
                "Selection Error", "Please select a reason for the suspension."
            )
            return
        ui_data["reason"] = reason

        # Convert matches_out to an integer if possible, otherwise show a warning
        matches_out = safe_int_conversion(ui_data["matches_out"])
        if matches_out is None:
            logger.warning(
                "Invalid input for 'Matches Out': %s. Must be a number.",
                ui_data["matches_out"],
            )
            self.show_warning(
                "Input Error",
                (
                    "The 'Matches Out' field must be a number. "
                    "Please correct it and try again."
                ),
            )
            return
        ui_data["matches_out"] = matches_out

        # Preemptive Date Validation
        in_game_date_str = self.in_game_date_entry.get().strip()
        if not self.validate_in_game_date(
            in_game_date_str, check_suspension_floor=True, player_name=player_name
        ):
            return
        ui_data["in_game_date"] = in_game_date_str

        try:
            logger.info(
                f"Validation passed. Saving suspension record for {player_name}."
            )
            self.controller.add_suspension_record(player_name, ui_data)
            self.show_success(
                "Data Saved",
                f"Suspension record for {player_name} has been successfully saved.",
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save suspension data: {e}", exc_info=True)
            self.show_error(
                "Error Saving Data", f"An error occurred: {e!s}\n\nPlease try again."
            )
            return
