import customtkinter as ctk
from src.exceptions import UIPopulationError
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

class AddFinancialFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict):
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        self.data_vars = {}
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
        
        data_names = ["Wage", "Market Value", "Contract Length (years)", "Release Clause", "Sell On Clause (%)"]
        
        self.financial_frame.grid_columnconfigure(0, weight=1)
        self.financial_frame.grid_columnconfigure(1, weight=0)
        self.financial_frame.grid_columnconfigure(2, weight=0)
        self.financial_frame.grid_columnconfigure(3, weight=1)
        
        for i in range(len(data_names)):
            self.financial_frame.grid_rowconfigure(i, weight=1)
        
        for i, data in enumerate(data_names):
            self.create_data_row(i, data, theme)
        
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
    
    def create_data_row(self, index: int, data_name: str, theme: dict) -> None:
        data_label = ctk.CTkLabel(
            self.financial_frame,
            text=data_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")
        
        data_var = ctk.StringVar(value="")
        self.data_vars[data_name] = data_var
        data_entry = ctk.CTkEntry(
            self.financial_frame,
            textvariable=data_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        data_entry.grid(row=index, column=2, padx=5, pady=5, sticky="ew")
    
    def on_done_button_press(self) -> None:
        """Compiles the captured financial inputs and commits them to the controller for persistence. 
        This method finalizes the financial data entry workflow and navigates back to the player library view.
        """
        financial_data = {name: var.get() for name, var in self.data_vars.items()}
        
        player = self.player_list_var.get()
        season = self.season_entry.get().strip()
        
        self.controller.save_financial_data(player, financial_data, season)

        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
    
    def refresh_player_dropdown(self) -> None:
        names = self.controller.get_all_player_names()
        self.player_names = names or ["No players found"]
        self.player_dropdown.set_values(self.player_names)
            
    def on_show(self) -> None:
        """Resets all input fields and refreshes the player dropdown."""
        for var in self.data_vars.values():
            var.set("")
        
        # Refresh player dropdown
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")