import customtkinter as ctk
import logging
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion

logger = logging.getLogger(__name__)

class AddFinancialFrame(ctk.CTkFrame):
    """A data entry frame for updating a player's financial and contract details."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddFinancialFrame layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing AddFinancialFrame")
        
        self.data_vars: Dict[str, ctk.StringVar] = {}
        self.stat_definitions: List[Tuple[str, str]] = [
            ("wage", "Wage"),
            ("market_value", "Market Value"),
            ("contract_length", "Contract Length (years)"),
            ("release_clause", "Release Clause"),
            ("sell_on_clause", "Sell On Clause (%)")
        ]
        self.player_names = []
        
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
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Player and season selection mini-frame
        self.selection_frame = ctk.CTkFrame(
            self,
            fg_color=theme["colors"]["background"]
        )
        self.selection_frame.grid(row=2, column=1, pady=(0, 20))
        
        # Dropdown to select player
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self.selection_frame,
            theme=theme,
            variable=self.player_list_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=1, column=1, pady=(0, 20), padx=(0, 20))
        
        # Season entry
        self.season_entry = ctk.CTkEntry(
            self.selection_frame,
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["entry_fg"],
            text_color=theme["colors"]["primary_text"],
            width=250,
            placeholder_text="Season (e.g., 24/25)"
        )
        self.season_entry.grid(row=1, column=2, pady=(0, 20), padx=(20, 0))
        
        # financial data subgrid
        self.financial_frame = ctk.CTkFrame(
            self,
            fg_color=theme["colors"]["background"]
        )
        self.financial_frame.grid(row=3, column=1, pady=(0, 20))
        
        self.financial_frame.grid_columnconfigure(0, weight=1)
        self.financial_frame.grid_columnconfigure(1, weight=0)
        self.financial_frame.grid_columnconfigure(2, weight=0)
        self.financial_frame.grid_columnconfigure(3, weight=1)
        
        for i in range(len(self.stat_definitions)):
            self.financial_frame.grid_rowconfigure(i, weight=1)
        
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
        self.done_button.grid(row=4, column=1)
    
    def create_data_row(self, index: int, data_key: str, data_name: str, theme: Dict[str, Any]) -> None:
        """Helper to create a label and entry pair for a financial data point."""
        data_label = ctk.CTkLabel(
            self.financial_frame,
            text=data_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")
        
        data_var = ctk.StringVar(value="")
        self.data_vars[data_key] = data_var
        data_entry = ctk.CTkEntry(
            self.financial_frame,
            textvariable=data_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        data_entry.grid(row=index, column=2, padx=5, pady=5, sticky="ew")
    
    def on_done_button_press(self) -> None:
        """Validates inputs, safely extracts monetary values, and routes to the Controller."""
        financial_data: Dict[str, Any] = {
            key: safe_int_conversion(var.get().replace(',', '').replace('.', '').replace('k', '000').replace('m', '000000').replace('€', '').replace('£', '').replace('$', ''))
            for key, var in self.data_vars.items()
        }
        
        player = self.player_list_var.get()
        season = self.season_entry.get().strip()
        
        # Handling missing fields.
        # If player or season aren't provided, this is a serious error
        # If wage or market value aren't provided, this is also an error
        # Handle both of the above with a logger warning and return for now, specifiying the field that was left empty
        # If contract length, release clause, or sell on clause are missing, we can default them to zero
        
        
        missing_fields = []
        if player == "Click here to select player" or player == "No players found" or not player:
            missing_fields.append("Player")
        if not season:
            missing_fields.append("Season")
        if financial_data["wage"] is None:
            missing_fields.append("Wage")
        if financial_data["market_value"] is None:
            missing_fields.append("Market Value")
        
        for field in ["contract_length", "release_clause", "sell_on_clause"]:
            if financial_data[field] is None:
                financial_data[field] = 0
        
        if missing_fields:
            logger.warning(f"Validation Failed: Missing fields - {(', '.join(missing_fields)).title()}")
            return
        
        try:
            logger.info(f"Validation passed. Saving financial data for {player}.")
            self.controller.save_financial_data(player, financial_data, season)
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save financial data: {e}", exc_info=True)
    
    def refresh_player_dropdown(self) -> None:
        """Fetch the latest player list from the database and update the custom dropdown."""
        names = self.controller.get_all_player_names()
        self.player_names = names or ["No players found"]
        self.player_dropdown.set_values(self.player_names)
            
    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        for var in self.data_vars.values():
            var.set("")
        
        # Refresh player dropdown
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")