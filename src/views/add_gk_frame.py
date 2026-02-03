import customtkinter as ctk
import logging
from src.exceptions import UIPopulationError

logger = logging.getLogger(__name__)

class AddGKFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict):
        '''Initializes the goalkeeper attribute entry frame for the application.
        Sets up input fields for player details and goalkeeper attributes, and configures the layout.

        Args:
            parent: The parent widget for this frame.
            controller: The main application controller.
            theme (dict): The theme dictionary containing color and font settings.
        '''
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        logger.info("Initializing AddGKFrame")
        
        self.attr_vars = {}
        
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
        
        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter name here",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.name_entry.grid(row=1, column=1, pady=(10, 5), sticky="ew")
        
        self.season_entry = ctk.CTkEntry(
            self,
            placeholder_text="Season (e.g. 25/26)",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.season_entry.grid(row=2, column=1, pady=(10, 5), sticky="ew")

        self.base_attr_row = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.base_attr_row.grid(row=3, column=1, pady=(5, 10), sticky="nsew")
        self.base_attr_row.grid_columnconfigure(0, weight=1)
        self.base_attr_row.grid_columnconfigure(1, weight=0)
        self.base_attr_row.grid_columnconfigure(2, weight=0)
        self.base_attr_row.grid_columnconfigure(3, weight=0)
        self.base_attr_row.grid_columnconfigure(4, weight=0)
        self.base_attr_row.grid_columnconfigure(5, weight=1)
        self.base_attr_row.grid_rowconfigure(0, weight=1)
        
        self.age_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Age",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"],
            width=160
        )
        self.age_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (ft'in\")",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"],
            width=160
        )
        self.height_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (lbs)",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"],
            width=160
        )
        self.weight_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"],
            width=160
        )
        self.country_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.attributes_grid = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.attributes_grid.grid(row=4, column=1, pady=(0, 10), sticky="nsew")

        attr_names = ["Diving", "Handling", "Kicking", "Reflexes", "Positioning"]
        
        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=1)
        for i in range(len(attr_names)):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, attr in enumerate(attr_names):
            self.create_attribute_row(i, attr, theme)
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=theme["fonts"]["button"],
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=5, column=1, pady=(0, 20), sticky="ew")
    
    def create_attribute_row(self, row: int, attr_name: str, theme: dict) -> None:
        '''Creates a row in the attributes grid for a specific goalkeeper attribute.
        Adds a label and entry field for the attribute to the grid layout.

        Args:
            row (int): The row index in the grid.
            attr_name (str): The name of the attribute.
            theme (dict): The theme dictionary containing color and font settings.
        '''
        attr_label = ctk.CTkLabel(
            self.attributes_grid,
            text=attr_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        attr_label.grid(row=row, column=1, padx=5, pady=5)
        
        attr_var = ctk.StringVar(value="")  
        self.attr_vars[attr_name] = attr_var      
        self.attr_entry = ctk.CTkEntry(
            self.attributes_grid,
            textvariable=attr_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        self.attr_entry.grid(row=row, column=2, padx=5, pady=5)
    
    def populate_stats(self, stats: dict) -> None:
        ''' Populates the goalkeeper attribute entry fields with detected statistics.
        Updates the input fields for each attribute using the provided stats dictionary.

        Args:
            stats (dict): A dictionary containing attribute names and their corresponding values.
        '''
        logger.debug(f"Populating AddGKFrame with stats: {stats.keys()}")
        if not stats:
            raise UIPopulationError("Received no data to populate GK attributes.")
        key_to_display_name = {
            "diving": "Diving",
            "handling": "Handling",
            "kicking": "Kicking",
            "reflexes": "Reflexes",
            "positioning": "Positioning"
        }
        
        for key, display_name in key_to_display_name.items():
            self.attr_vars[display_name].set(str(stats.get(key, "")))
        
        logger.debug("AddGKFrame population complete.")
    
    def on_done_button_press(self) -> None:
        """
        Handles the event when the 'Done' button is pressed on the goalkeeper attributes page.
        Collects the entered attribute and player data, saves it through the controller, and navigates back to the player library frame.
        """
        ui_data = {name: var.get() for name, var in self.attr_vars.items()}
        ui_data["name"] = self.name_entry.get()
        ui_data["age"] = self.age_entry.get()
        ui_data["height"] = self.height_entry.get()
        ui_data["weight"] = self.weight_entry.get()
        ui_data["country"] = self.country_entry.get()
        ui_data["season"] = self.season_entry.get()

        if missing_fields := [
            key for key, value in ui_data.items() if value.strip() == ""
        ]:
            logger.warning(f"Validation failed: Missing fields - {', '.join(missing_fields)}")
            return
        
        self.controller.buffer_data(ui_data, gk=True)
        self.controller.save_player()

        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
    
    def on_show(self) -> None:
        """
        Clears the following input fields when the frame is shown:
        - Name
        - Position
        - Age
        - Height
        - Weight
        - Country
        """
        self.name_entry.delete(0, 'end')
        self.name_entry.configure(placeholder_text="Enter name here")
        
        self.age_entry.delete(0, 'end')
        self.age_entry.configure(placeholder_text="Age")
        
        self.height_entry.delete(0, 'end')
        self.height_entry.configure(placeholder_text="Height (ft'in\")")
        
        self.weight_entry.delete(0, 'end')
        self.weight_entry.configure(placeholder_text="Weight (lbs)")
        
        self.country_entry.delete(0, 'end')
        self.country_entry.configure(placeholder_text="Country")