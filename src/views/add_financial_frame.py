"""UI frame for editing player financial and contract details.

This module defines AddFinancialFrame, a CustomTkinter view used to capture
financial updates for an existing player. It handles roster selection, in-game
date entry, field normalization for currency-style inputs, and validation of
required values before delegating persistence to the frame controller.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import (
    AddFinancialFrameControllerProtocol,
    BaseViewThemeProtocol,
)
from src.schemas import (
    FINANCIAL_CONTRACT_LENGTH_MAX,
    FINANCIAL_CONTRACT_LENGTH_MIN,
    FINANCIAL_MIN_VALUE,
    FINANCIAL_SELL_ON_CLAUSE_MAX,
    FINANCIAL_SELL_ON_CLAUSE_MIN,
)
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, PlayerDropdownMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class AddFinancialFrame(BaseViewFrame, PlayerDropdownMixin, EntryFocusMixin):
    """Data-entry frame for player financial and contract updates.

    The frame isolates UI concerns for financial editing while delegating
    persistence and navigation to the controller interface.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: AddFinancialFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the financial update form.

        Constructs the full widget layout for player selection, in-game date
        entry, and financial fields. It also registers callback wiring for the
        save action and initializes dynamic data bindings used by shared base
        validation helpers.

        Financial fields are generated from ``self.stat_definitions`` so UI
        labels and payload keys remain synchronized in one canonical mapping.

        Args:
            parent (ctk.CTkFrame): Parent container for this frame.
            controller (AddFinancialFrameControllerProtocol): Controller providing
                navigation and save actions.
            theme (BaseViewThemeProtocol): Appearance tokens and fonts used
                to style widgets.
        """
        super().__init__(parent, controller, theme)
        self.controller: AddFinancialFrameControllerProtocol = controller

        logger.info("Initializing AddFinancialFrame")

        self.stat_definitions: list[tuple[str, str]] = [
            ("wage", "Wage"),
            ("market_value", "Market Value"),
            ("contract_length", "Contract Length (years)"),
            ("release_clause", "Release Clause"),
            ("sell_on_clause", "Sell On Clause (%)"),
        ]

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

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self, text="Update Player Financials", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(80, 10))

        # Player and season selection mini-frame
        self.selection_frame = ctk.CTkFrame(self)
        self.selection_frame.grid(row=2, column=1, pady=(0, 20))

        # Dropdown to select player
        self.player_dropdown_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self.selection_frame,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.player_dropdown_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player",
        )
        self.player_dropdown.grid(row=1, column=1, pady=(0, 20), padx=(0, 20))

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
            text="Enter the in-game date for this update:",
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

        # financial data subgrid
        self.financial_frame = ctk.CTkFrame(self)
        self.financial_frame.grid(row=4, column=1, pady=(0, 20))

        self.financial_frame.grid_columnconfigure(0, weight=1)
        self.financial_frame.grid_columnconfigure(1, weight=0)
        self.financial_frame.grid_columnconfigure(2, weight=0)
        self.financial_frame.grid_columnconfigure(3, weight=1)

        for i in range(len(self.stat_definitions)):
            self.financial_frame.grid_rowconfigure(i, weight=1)

        for i, (key, label) in enumerate(self.stat_definitions):
            self.create_data_row(
                parent_widget=self.financial_frame,
                index=i,
                stat_key=key,
                stat_label=label,
                target_dict=self.data_vars,
            )

        # Done Button
        self.done_button = ctk.CTkButton(
            self,
            text="Save Financials",
            font=self.fonts["button"],
            command=self._on_done_button_press,
        )
        self.done_button.grid(row=5, column=1)
        self.style_submit_button(self.done_button)

        self.apply_focus_flourishes(self)

    def on_show(self) -> None:
        """Reset view state whenever the frame becomes active.

        Clears all financial field variables, refreshes player options from the
        active career, restores the dropdown placeholder, and resets the date
        entry widget. This prevents stale input from previous interactions from
        carrying into a new save flow.
        """
        for var in self.data_vars.values():
            var.set("")

        # Refresh player dropdown
        self.refresh_player_dropdown()

        self.player_dropdown.set_value("Click here to select player")

        self.in_game_date_entry.delete(0, "end")
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")

    def _on_done_button_press(self) -> None:
        """Handle Save Financials button clicks.

        This method is the submit pipeline for the frame. It resolves the
        selected player identity, normalizes currency-style text into integer
        values, validates required fields, applies defaults for optional
        financial fields, and validates the in-game date.

        Once all checks pass, it delegates persistence to the controller,
        reports success to the user, and navigates back to the player library.
        Validation failures short-circuit early with contextual UI feedback.
        """
        player: str | None = self.resolve_selected_player_name(
            self.player_dropdown_var.get()
        )
        if player is None:
            self.show_warning(
                title="No Player Selected",
                message="Please select a player from the dropdown before saving.",
            )
            return

        ui_data: dict[str, int | None] = {
            key: safe_int_conversion(
                var.get()
                .replace(",", "")
                .replace("£", "")
                .replace("$", "")
                .replace("€", "")
                .replace("k", "000")
                .replace("m", "000000")
                .strip()
            )
            for key, var in self.data_vars.items()
        }

        required_keys: list[str] = ["wage", "market_value"]
        key_to_label: dict[str, str] = {
            key: label
            for key, label in self.stat_definitions
            if key not in ["contract_length", "release_clause", "sell_on_clause"]
        }
        if not self.check_missing_fields(
            ui_data,
            key_to_label=key_to_label,
            required_keys=required_keys,
            zero_invalid_keys=required_keys,
        ):
            return

        for field in ["contract_length", "release_clause", "sell_on_clause"]:
            if ui_data[field] is None:
                ui_data[field] = 0

        if not self._validate_financial_schema_bounds(ui_data):
            return

        in_game_date: str = self.in_game_date_entry.get().strip()
        if not self.validate_in_game_date(in_game_date):
            return

        try:
            logger.info(f"Validation passed. Saving financial data for {player}.")
            self.controller.save_financial_data(player, ui_data, in_game_date)
            self.show_success(
                "Data Saved", f"Financial details for {player} updated successfully."
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save financial data: {e}", exc_info=True)
            self.show_error(
                "Error Saving Data", f"An error occurred: {e!s}\n\nPlease try again."
            )

    def _validate_financial_schema_bounds(self, ui_data: dict[str, int | None]) -> bool:
        """Hard-validate financial values against schema-backed bounds.

        Args:
            ui_data (dict[str, int | None]): Normalized financial payload.

        Returns:
            bool: True when all bounded values are valid, otherwise False.
        """
        violations: list[str] = []

        wage: int | None = ui_data.get("wage")
        if wage is not None and wage < FINANCIAL_MIN_VALUE:
            violations.append(f"Wage must be at least {FINANCIAL_MIN_VALUE}.")

        market_value: int | None = ui_data.get("market_value")
        if market_value is not None and market_value < FINANCIAL_MIN_VALUE:
            violations.append(f"Market Value must be at least {FINANCIAL_MIN_VALUE}.")

        contract_length: int | None = ui_data.get("contract_length")
        if contract_length is not None and not (
            FINANCIAL_CONTRACT_LENGTH_MIN
            <= contract_length
            <= FINANCIAL_CONTRACT_LENGTH_MAX
        ):
            violations.append(
                "Contract Length (years) must be between "
                f"{FINANCIAL_CONTRACT_LENGTH_MIN} and "
                f"{FINANCIAL_CONTRACT_LENGTH_MAX}."
            )

        release_clause: int | None = ui_data.get("release_clause")
        if release_clause is not None and release_clause < FINANCIAL_MIN_VALUE:
            violations.append(f"Release Clause must be at least {FINANCIAL_MIN_VALUE}.")

        sell_on_clause: int | None = ui_data.get("sell_on_clause")
        if sell_on_clause is not None and not (
            FINANCIAL_SELL_ON_CLAUSE_MIN
            <= sell_on_clause
            <= FINANCIAL_SELL_ON_CLAUSE_MAX
        ):
            violations.append(
                "Sell On Clause (%) must be between "
                f"{FINANCIAL_SELL_ON_CLAUSE_MIN} and "
                f"{FINANCIAL_SELL_ON_CLAUSE_MAX}."
            )

        if violations:
            logger.warning(
                "Financial validation failed for bounded fields: %s",
                "; ".join(violations),
            )
            self.show_warning(
                title="Invalid Financial Values",
                message=(
                    "One or more financial values are outside the allowed bounds:\n\n"
                    + "\n".join(f"- {violation}" for violation in violations)
                ),
            )
            return False

        return True
