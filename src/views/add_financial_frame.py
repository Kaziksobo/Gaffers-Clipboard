import customtkinter as ctk
import logging
import re
from typing import Dict, Any, List, Tuple
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.views.widgets.custom_alert import CustomAlert
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
        self.theme = theme
        
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
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self.selection_frame,
            theme=self.theme,
            variable=self.player_list_var,
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
            placeholder_text="Season (e.g., 24/25)"
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
        self.done_button.grid(row=4, column=1)
    
    def create_data_row(self, index: int, data_key: str, data_name: str) -> None:
        """Helper to create a label and entry pair for a financial data point."""
        data_label = ctk.CTkLabel(
            self.financial_frame,
            text=data_name,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")
        
        data_var = ctk.StringVar(value="")
        self.data_vars[data_key] = data_var
        data_entry = ctk.CTkEntry(
            self.financial_frame,
            textvariable=data_var,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
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

        # Check if the season is in a valid format (e.g. "24/25") using a simple regex
        # If the season is in format "2024/2025", convert it to "24/25"
        # If the format is completely wrong, just set it to None
        if re.match(r'^\d{2}/\d{2}$', season):
            pass
        elif re.match(r'^\d{4}/\d{4}$', season):
            season = f'{season[2:4]}/{season[7:9]}'
        else:
            season = None

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
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Missing Information",
                message=f"The following required fields are missing: {', '.join(missing_fields)}. Please fill them in before proceeding.",
                alert_type="warning",
            )
            return

        try:
            logger.info(f"Validation passed. Saving financial data for {player}.")
            self.controller.save_financial_data(player, financial_data, season)
            CustomAlert(
                parent=self,
                theme = self.theme,
                title="Data Saved",
                message=f"Financial data for {player} in season {season} has been successfully saved.",
                alert_type="success",
                success_timeout=2
            )
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections or DB locks
            logger.error(f"Failed to save financial data: {e}", exc_info=True)
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Error Saving Data",
                message=f"An error occurred while saving the financial data: {str(e)}. Please try again.",
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
                message="No players were found in the database. Please add players to the library before adding financial information.",
                alert_type="warning",
                options=["Return to Library"],
            )
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
            return
        self.player_names = names or ["No players found"]
        self.player_dropdown.set_values(self.player_names)
            
    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        for var in self.data_vars.values():
            var.set("")
        
        # Refresh player dropdown
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")