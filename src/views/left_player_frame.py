import customtkinter as ctk
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

class LeftPlayerFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        # Basic UI, with a player dropdown and a sell button
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1)
        
        self.main_heading = ctk.CTkLabel(
            self,
            text="Sell Player",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(10, 5))
        
        # Dropdown to select player (reusable scrollable dropdown)
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=theme,
            variable=self.player_list_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))
        
        # Sell/loan mini frame
        self.sell_loan_frame = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.sell_loan_frame.grid(row=3, column=1, pady=(0, 20), sticky="nsew")
        self.sell_loan_frame.grid_columnconfigure(0, weight=1)
        self.sell_loan_frame.grid_columnconfigure(1, weight=1)
        self.sell_loan_frame.grid_columnconfigure(2, weight=1)
        self.sell_loan_frame.grid_rowconfigure(0, weight=1)
        
        # Sell button
        self.sell_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Sell Player",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["background"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["accent"],
            command=self.sell_player
        )
        self.sell_button.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        # Loan button
        self.loan_out_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Loan out Player",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["background"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["accent"],
            command=self.loan_out_player
        )
        self.loan_out_button.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        self.return_button = ctk.CTkButton(
            self.sell_loan_frame,
            text="Return from loan",
            fg_color=theme["colors"]["button_fg"],
            bg_color=theme["colors"]["background"],
            font=theme["fonts"]["button"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["accent"],
            command=self.return_loan_player
        )
        self.return_button.grid(row=0, column=2, padx=10, pady=5, sticky="ew")
        
    
    def sell_player(self) -> None:
        """
        Sell the currently selected player and navigate back to the player library.

        This retrieves the chosen player from the dropdown, triggers the controller's
        sell logic, then switches the view to the player library frame.
        """
        player_name = self.player_list_var.get()
        self.controller.sell_player(player_name)
        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
    
    def loan_out_player(self) -> None:
        """Loan out the currently selected player and return to the player library view.

        This uses the selected player from the dropdown, calls the controller loan
        action, and then switches the active frame back to the player library.
        """
        player_name = self.player_list_var.get()
        self.controller.loan_out_player(player_name)
        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
    
    def return_loan_player(self) -> None:
        """Return the currently selected player from loan and go back to the player library.

        This gets the selected player from the dropdown, invokes the controller's
        return from loan method, and navigates back to the player library frame.
        """
        player_name = self.player_list_var.get()
        self.controller.return_loan_player(player_name)
        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
    
    def refresh_player_dropdown(self) -> None:
        """Reload player names and update the dropdown."""
        names = self.controller.get_all_player_names()
        self.player_dropdown.set_values(names or ["No players found"])
    
    def on_show(self) -> None:
        """Called when the frame is shown; refreshes the player dropdown."""
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")