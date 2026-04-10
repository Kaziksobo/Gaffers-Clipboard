"""UI frame for player departure actions.

This module defines LeftPlayerFrame, a management view used to process player
status transitions such as permanent sales, loan-outs, and loan returns. It
validates player selection and date input where required, then delegates
persistence and navigation to the controller.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, LeftPlayerFrameControllerProtocol
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, PlayerDropdownMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class LeftPlayerFrame(BaseViewFrame, PlayerDropdownMixin, EntryFocusMixin):
    """Management frame for selling, loaning, and returning players.

    The frame centralizes departure-related actions and user confirmations,
    while leaving mutation logic to the controller layer.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: LeftPlayerFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the player departure management interface.

        Creates player selection controls, optional in-game date entry for
        sales, and action buttons for sell, loan out, and return from loan
        workflows.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (LeftPlayerFrameControllerProtocol):
                The main application controller.
            theme (BaseViewThemeProtocol): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        self.controller: LeftPlayerFrameControllerProtocol = controller

        logger.info("Initializing LeftPlayerFrame")

        # Basic UI, with a player dropdown and a sell button
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)

        self.main_heading = ctk.CTkLabel(
            self, text="Sell/Loan Player", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(10, 5))

        # Dropdown to select player (reusable scrollable dropdown)
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.player_list_var,
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
            text="Enter the in-game date if selling player:",
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

        # Sell/loan mini frame
        self.sell_loan_frame = ctk.CTkFrame(self)
        self.sell_loan_frame.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        self.sell_loan_frame.grid_columnconfigure(0, weight=1)
        self.sell_loan_frame.grid_columnconfigure(1, weight=1)
        self.sell_loan_frame.grid_columnconfigure(2, weight=1)
        self.sell_loan_frame.grid_rowconfigure(0, weight=1)

        # Sell button
        self.sell_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Sell Player",
            font=self.fonts["button"],
            command=self._sell_player,
        )
        self.sell_button.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        # Loan button
        self.loan_out_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Loan Out Player",
            font=self.fonts["button"],
            command=self._loan_out_player,
        )
        self.loan_out_button.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.return_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Return From Loan",
            font=self.fonts["button"],
            command=self._return_loan_player,
        )
        self.return_button.grid(row=0, column=2, padx=10, pady=5, sticky="ew")

        self.apply_focus_flourishes(self)

    def on_show(self) -> None:
        """Reset frame state whenever the view becomes active.

        Refreshes player options, restores dropdown placeholder text, and
        clears the in-game date entry to prevent stale input from prior runs.
        """
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")

        self.in_game_date_entry.delete(0, "end")
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")

    def _sell_player(self) -> None:
        """Confirm and process a permanent player sale.

        Requires a valid selected player and in-game date, asks for explicit
        confirmation, then delegates the sale to the controller and returns to
        the player library on success.
        """
        player_name: str | None = self._get_player_name()
        if not player_name:
            return

        in_game_date: str | None = self._get_in_game_date()
        if in_game_date is None:
            return

        # Ask for confirmation before selling the player
        confirmation = self.show_warning(
            title="Confirm Player Sale",
            message=(
                f"Are you sure you want to sell {player_name}? "
                "This action cannot be undone."
            ),
            options=["Cancel", "Sell Player"],
        )
        if confirmation != "Sell Player":
            return

        try:
            logger.info(f"Initiating sale for player: {player_name}")
            self.controller.sell_player(player_name, in_game_date)
            self.show_success(
                "Player Sold", f"{player_name} has been successfully sold."
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
        except Exception as e:
            logger.error(f"Failed to execute player sale: {e}", exc_info=True)
            self.show_error(
                "Player Sale Failed",
                f"Failed to sell player {player_name}. Please try again.",
            )
            return

    def _loan_out_player(self) -> None:
        """Process a loan-out action for the selected player.

        Validates player selection, delegates the loan mutation to the
        controller, and navigates to the player library on success.
        """
        player_name: str | None = self._get_player_name()
        if not player_name:
            return

        try:
            logger.info(f"Initiating loan-out for player: {player_name}")
            self.controller.loan_out_player(player_name)
            self.show_success(
                "Player Loaned Out", f"{player_name} has been successfully loaned out."
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
        except Exception as e:
            logger.error(f"Failed to execute player loan: {e}", exc_info=True)
            self.show_error(
                "Player Loan Failed",
                f"Failed to loan out player {player_name}. Please try again.",
            )
            return

    def _return_loan_player(self) -> None:
        """Process a return-from-loan action for the selected player.

        Validates player selection, delegates the status update to the
        controller, and navigates to the player library on success.
        """
        player_name: str | None = self._get_player_name()
        if not player_name:
            return

        try:
            logger.info(f"Initiating loan return for player: {player_name}")
            self.controller.return_loan_player(player_name)
            self.show_success(
                "Player Returned",
                f"{player_name} has been successfully returned from loan.",
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
        except Exception as e:
            logger.error(f"Failed to execute player loan return: {e}", exc_info=True)
            self.show_error(
                "Player Return Failed",
                f"Failed to return player {player_name} from loan. Please try again.",
            )
            return

    def _get_player_name(self) -> str | None:
        """Resolve and validate the currently selected player from the dropdown.

        Presents a warning dialog when no valid player is selected.

        Returns:
            str | None: Selected player name when valid; otherwise None.
        """
        player_name: str | None = self.resolve_selected_player_name(
            self.player_list_var.get()
        )

        if player_name is None:
            self.show_warning(
                "Selection Error", "Please select a player before performing an action."
            )
            return

        return player_name

    def _get_in_game_date(self) -> str | None:
        """Read and validate the in-game date required for sale actions.

        Returns ``None`` when the current entry fails shared date validation.

        Returns:
            str | None: Validated in-game date string, or None when invalid.
        """
        in_game_date_str: str = self.in_game_date_entry.get().strip()

        if not self.validate_in_game_date(in_game_date_str):
            return None

        return in_game_date_str
