import customtkinter as ctk
import logging
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.utils import safe_int_conversion
from datetime import datetime

logger = logging.getLogger(__name__)

class AddInjuryFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict):
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing AddInjuryFrame")
        
        self.data_vars = {}
        self.stat_definitions = [
            ("in_game_date", "In-game Date"),
            ("injury_detail", "Injury Detail"),
            ("time_out", "Time Out")
        ]
        self.player_names = []
        self.time_out_unit_var = ctk.StringVar(value="Select unit")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
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
            self,
            text="Add player injury record",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1)
        
        # Dropdown to select player
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=theme,
            variable=self.player_list_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=2, column=1)
        
        # Season entry
        self.season_entry = ctk.CTkEntry(
            self,
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["entry_fg"],
            text_color=theme["colors"]["primary_text"],
            width=250,
            placeholder_text="Season (e.g., 24/25)"
        )
        self.season_entry.grid(row=3, column=1)
        
        # Data subgrid
        self.data_frame = ctk.CTkFrame(
            self,
            fg_color=theme["colors"]["background"]
        )
        self.data_frame.grid(row=4, column=1)
        
        self.data_frame.grid_columnconfigure(0, weight=1)
        self.data_frame.grid_columnconfigure(1, weight=0)
        self.data_frame.grid_columnconfigure(2, weight=0)
        self.data_frame.grid_columnconfigure(3, weight=0)
        self.data_frame.grid_columnconfigure(4, weight=1)
        
        for i in range(len(self.stat_definitions)):
            self.data_frame.grid_rowconfigure(i, weight=1)
        
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
        self.done_button.grid(row=5, column=1)
    
    def create_data_row(self, index: int, data_key: str, data_name: str, theme: dict) -> None:
        data_label = ctk.CTkLabel(
            self.data_frame,
            text=data_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        data_label.grid(row=index, column=1, padx=5, pady=5, sticky="w")
        
        data_var = ctk.StringVar(value="")
        self.data_vars[data_key] = data_var
        
        placeholder_text = "dd/mm/yy" if data_key == "in_game_date" else ""
        
        data_entry = ctk.CTkEntry(
            self.data_frame,
            textvariable=data_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"],
            placeholder_text=placeholder_text
        )
        data_entry.grid(row=index, column=2, padx=5, pady=5, sticky="ew")
        
        if data_key == "time_out":
            # Drop down to select between days, weeks, months, in a third column next to the entry
            time_out_unit_dropdown = ctk.CTkComboBox(
                self.data_frame,
                variable=self.time_out_unit_var,
                values=["Days", "Weeks", "Months"],
                font=theme["fonts"]["body"],
                text_color=theme["colors"]["primary_text"],
                fg_color=theme["colors"]["dropdown_fg"]
            )
            time_out_unit_dropdown.grid(row=index, column=3, padx=5, pady=5, sticky="ew")
    
    def on_done_button_press(self):
        injury_data = {key: var.get().strip() for key, var in self.data_vars.items()}
        player_name = self.player_list_var.get()
        season = self.season_entry.get().strip()
        injury_data["time_out_unit"] = self.time_out_unit_var.get()

        # convert time_out to an integer and store in injury_data, if possible
        time_out_str = injury_data.get("time_out", "")
        time_out_int = safe_int_conversion(time_out_str)
        injury_data["time_out"] = time_out_int if time_out_int is not None else None
        
        missing_fields = []
        if player_name == "Click here to select player" or player_name == "No players found" or not player_name:
            missing_fields.append("Player")
        if not season:
            missing_fields.append("Season")
        missing_fields.extend(
            key.replace("_", " ").title()
            for key, value in injury_data.items()
            if not value
        )
        if missing_fields:
            logger.warning(f"Cannot add injury record. Missing fields: {', '.join(missing_fields)}")
            return
        
        # Validate in_game_date format
        in_game_date_str = injury_data.get("in_game_date", "").strip()
        try:
            datetime.strptime(in_game_date_str, "%d/%m/%y")
        except ValueError:
            logger.warning(f"Cannot add injury record. Invalid date format for 'In-game Date'. Expected format: dd/mm/yy, got: '{in_game_date_str}'")
            return

        self.controller.add_injury_record(player_name, season, injury_data)
        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))