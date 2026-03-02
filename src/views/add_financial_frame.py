import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import PlayerDropdownMixin

logger = logging.getLogger(__name__)

class AddFinancialFrame(BaseViewFrame, PlayerDropdownMixin):
    """A data entry frame for updating a player's financial and contract details."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddFinancialFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        
        logger.info("Initializing AddFinancialFrame")
        
        self.stat_definitions: List[Tuple[str, str]] = [
            ("wage", "Wage"),
            ("market_value", "Market Value"),
            ("contract_length", "Contract Length (years)"),
            ("release_clause", "Release Clause"),
            ("sell_on_clause", "Sell On Clause (%)")
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
            text="Add Financial Information for the player",
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Player and season selection mini-frame
        self.selection_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme["colors"]["background"]
        )
        self.selection_frame.grid(row=2, column=1, pady=(0, 20))
        
        # Dropdown to select player
        self.player_dropdown_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self.selection_frame,
            theme=self.theme,
            variable=self.player_dropdown_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=1, column=1, pady=(0, 20), padx=(0, 20))
        
        # Season entry
        self.season_entry = ctk.CTkEntry(
            self.selection_frame,
            font=self.theme["fonts"]["body"],
            fg_color=self.theme["colors"]["entry_fg"],
            text_color=self.theme["colors"]["primary_text"],
            width=250,
            placeholder_text="Season (e.g. 24/25)"
        )
        self.season_entry.grid(row=1, column=2, pady=(0, 20), padx=(20, 0))
        
        # financial data subgrid
        self.financial_frame = ctk.CTkFrame(
            self,
            fg_color=self.theme["colors"]["background"]
        )
        self.financial_frame.grid(row=3, column=1, pady=(0, 20))
        
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
                target_dict=self.data_vars
            )
        
        # Done Button
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=self.on_done_button_press
        )
        self.done_button.grid(row=4, column=1)
    
    def on_done_button_press(self) -> None:
        """Validates inputs, safely extracts monetary values, and routes to the Controller."""
        player = self.player_dropdown_var.get()
        if player in ["Click here to select player", "No players found", "Select Player", ""]:
            self.show_warning(
                title="No Player Selected",
                message="Please select a player from the dropdown before saving.",
            )
            return

        ui_data = {
            key: safe_int_conversion(var.get().replace(",", "").replace("£", "").replace("$", "").replace("€", "").replace("k", "000").replace("m", "000000").strip())
            for key, var in self.data_vars.items()
        }
        
        season = self.validate_season(self.season_entry.get().strip())
        if season is None:
            return
        
        required_keys = ["wage", "market_value"]
        key_to_label = {key: label for key, label in self.stat_definitions if key not in ["contract_length", "release_clause", "sell_on_clause"]}
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

        try:
            logger.info(f"Validation passed. Saving financial data for {player}.")
            self.controller.save_financial_data(player, ui_data, season)
            self.show_success("Data Saved", f"Financial details for {player} updated successfully.")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save financial data: {e}", exc_info=True)
            self.show_error("Error Saving Data", f"An error occurred: {str(e)}\n\nPlease try again.")
            
    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        for var in self.data_vars.values():
            var.set("")
        
        # Refresh player dropdown
        self.refresh_player_dropdown()
        
        self.player_dropdown.set_value("Click here to select player")