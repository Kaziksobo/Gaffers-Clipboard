import customtkinter as ctk
import logging
from typing import Dict, Any, Optional
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import PlayerDropdownMixin

logger = logging.getLogger(__name__)

class LeftPlayerFrame(BaseViewFrame, PlayerDropdownMixin):
    """A management frame for executing player sales and loans."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        """Initialize the LeftPlayerFrame layout and controls.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        
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
            self,
            text="Sell/Loan Player",
            font=self.fonts["title"],
            text_color=self.theme.colors.primary_text
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
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))
        
        # In-game Date mini frame
        self.in_game_date_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme.colors.background
        )
        self.in_game_date_frame.grid(row=3, column=1, padx=(20, 0), pady=(0, 20), sticky="ew")
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
            text_color=self.theme.colors.primary_text
        )
        self.in_game_date_label.grid(row=1, column=1, padx=(20, 0), sticky="w")
        self.in_game_date_entry = ctk.CTkEntry(
            self.in_game_date_frame,
            font=self.fonts["body"],
            fg_color=self.theme.colors.entry_fg,
            text_color=self.theme.colors.primary_text,
            width=200,
            placeholder_text="dd/mm/yy"
        )
        self.in_game_date_entry.grid(row=1, column=2, padx=(20, 0), sticky="e")
        
        # Sell/loan mini frame
        self.sell_loan_frame = ctk.CTkFrame(self, fg_color=self.theme.colors.background)
        self.sell_loan_frame.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        self.sell_loan_frame.grid_columnconfigure(0, weight=1)
        self.sell_loan_frame.grid_columnconfigure(1, weight=1)
        self.sell_loan_frame.grid_columnconfigure(2, weight=1)
        self.sell_loan_frame.grid_rowconfigure(0, weight=1)
        
        # Sell button
        self.sell_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Sell Player",
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.background,
            font=self.fonts["button"],
            text_color=self.theme.colors.primary_text,
            hover_color=self.theme.colors.accent,
            command=self.sell_player
        )
        self.sell_button.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        # Loan button
        self.loan_out_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Loan Out Player",
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.background,
            font=self.fonts["button"],
            text_color=self.theme.colors.primary_text,
            hover_color=self.theme.colors.accent,
            command=self.loan_out_player
        )
        self.loan_out_button.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        self.return_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Return From Loan",
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.background,
            font=self.fonts["button"],
            text_color=self.theme.colors.primary_text,
            hover_color=self.theme.colors.accent,
            command=self.return_loan_player
        )
        self.return_button.grid(row=0, column=2, padx=10, pady=5, sticky="ew")
    
    def get_in_game_date(self) -> Optional[str]:
        """Helper to extract and validate the in-game date from the entry field.

        Returns:
            Optional[str]: The valid in-game date string, or None if invalid.
        """
        in_game_date_str = self.in_game_date_entry.get().strip()
        
        if not self.validate_in_game_date(in_game_date_str):
            return None
        
        return in_game_date_str
        
    def _get_player_name(self) -> Optional[str]:
        """Extract and validate the currently selected player's name from the dropdown.

        Returns:
            str: The valid name of the selected player, or an empty string if invalid.
        """
        player_name = self.player_list_var.get()
        
        invalid_states = ["Click here to select player", "No players found", ""]
        if player_name in invalid_states:
            self.show_warning("Selection Error", "Please select a player before performing an action.")
            return
            
        return player_name
    
    def sell_player(self) -> None:
        """Execute the sale of the currently selected player and return to the library."""
        player_name = self._get_player_name()
        if not player_name:
            return
        
        in_game_date = self.get_in_game_date()
        if in_game_date is None:
            return
        
        # Ask for confirmation before selling the player
        confirmation = self.show_warning(
            title="Confirm Player Sale",
            message=f"Are you sure you want to sell {player_name}? This action cannot be undone.",
            options=["Cancel", "Sell Player"],
        )
        if confirmation != "Sell Player":
            return
        
        try:
            logger.info(f"Initiating sale for player: {player_name}")
            self.controller.sell_player(player_name, in_game_date)
            self.show_success("Player Sold", f"{player_name} has been successfully sold.")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            logger.error(f"Failed to execute player sale: {e}", exc_info=True)
            self.show_error("Player Sale Failed", f"Failed to sell player {player_name}. Please try again.")
            return
    
    def loan_out_player(self) -> None:
        """Execute the loan-out of the currently selected player and return to the library."""
        player_name = self._get_player_name()
        if not player_name:
            return
        
        try:
            logger.info(f"Initiating loan-out for player: {player_name}")
            self.controller.loan_out_player(player_name)
            self.show_success("Player Loaned Out", f"{player_name} has been successfully loaned out.")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            logger.error(f"Failed to execute player loan: {e}", exc_info=True)
            self.show_error("Player Loan Failed", f"Failed to loan out player {player_name}. Please try again.")
            return
    
    def return_loan_player(self) -> None:
        """Execute the loan return of the currently selected player and return to the library."""
        player_name = self._get_player_name()
        if not player_name:
            return

        try:
            logger.info(f"Initiating loan return for player: {player_name}")
            self.controller.return_loan_player(player_name)
            self.show_success("Player Returned", f"{player_name} has been successfully returned from loan.")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            logger.error(f"Failed to execute player loan return: {e}", exc_info=True)
            self.show_error("Player Return Failed", f"Failed to return player {player_name} from loan. Please try again.")
            return
    
    def on_show(self) -> None:
        """Lifecycle hook triggered when the frame is displayed to reset its state."""
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")
        
        self.in_game_date_entry.delete(0, "end")
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")