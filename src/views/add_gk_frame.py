import customtkinter as ctk
import logging
from typing import Dict, Any
from src.exceptions import UIPopulationError
from src.utils import safe_int_conversion

logger = logging.getLogger(__name__)

class AddGKFrame(ctk.CTkFrame):
    """A data entry frame for processing and saving Goalkeeper attributes."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddGKFrame layout and input fields.

        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The theme dictionary containing color and font settings.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme
        
        logger.info("Initializing AddGKFrame")
        
        self.attr_vars: Dict[str, ctk.StringVar] = {}
        self.attr_definitions = [
            ("diving", "Diving"),
            ("handling", "Handling"),
            ("kicking", "Kicking"),
            ("reflexes", "Reflexes"),
            ("positioning", "Positioning"),
        ]
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        for i in range(7):
            self.grid_rowconfigure(i, weight=1 if i in [0, 6] else 0)
        
        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter name here",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
        )
        self.name_entry.grid(row=1, column=1, pady=(10, 5), sticky="ew")
        
        self.season_entry = ctk.CTkEntry(
            self,
            placeholder_text="Season (e.g. 25/26)",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
        )
        self.season_entry.grid(row=2, column=1, pady=(10, 5), sticky="ew")

        self.base_attr_row = ctk.CTkFrame(self, fg_color=self.theme["colors"]["background"])
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
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.age_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (ft'in\")",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.height_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (lbs)",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.weight_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.country_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.attributes_grid = ctk.CTkFrame(self, fg_color=self.theme["colors"]["background"])
        self.attributes_grid.grid(row=4, column=1, pady=(0, 10), sticky="nsew")
        
        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=1)
        for i in range(len(self.attr_definitions)):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, (key, label) in enumerate(self.attr_definitions):
            self.create_attribute_row(i, key, label)
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=self.theme["fonts"]["button"],
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=5, column=1, pady=(0, 20), sticky="ew")
    
    def create_attribute_row(self, row: int, attr_key: str, attr_label: str) -> None:
        """Creates a row in the attributes grid for a specific goalkeeper attribute.
        
        Args:
            row (int): The row index in the attributes grid where this attribute should be placed.
            attr_key (str): The key used to identify this attribute in the data model.
            attr_label (str): The human-readable label for this attribute to display in the UI.
        """
        
        attr_label = ctk.CTkLabel(
            self.attributes_grid,
            text=attr_label,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        attr_label.grid(row=row, column=1, padx=5, pady=5)
        
        attr_var = ctk.StringVar(value="")  
        self.attr_vars[attr_key] = attr_var      
        self.attr_entry = ctk.CTkEntry(
            self.attributes_grid,
            textvariable=attr_var,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
        )
        self.attr_entry.grid(row=row, column=2, padx=5, pady=5)
    
    def populate_stats(self, stats: Dict[str, Any]) -> None:
        """Populate the UI entry fields with OCR-detected statistics.

        Args:
            stats (Dict[str, Any]): A dictionary containing attribute keys and integer values.

        Raises:
            UIPopulationError: If the provided stats dictionary is empty.
        """
        logger.debug(f"Populating AddGKFrame with stats: {stats.keys()}")
        if not stats:
            raise UIPopulationError("Received no data to populate GK attributes.")
        
        for key in self.attr_vars:
            self.attr_vars[key].set(str(stats.get(key, "")))
        
        logger.debug("AddGKFrame population complete.")
    
    def on_done_button_press(self) -> None:
        """Extract inputs, validate them, and route them to the Controller for saving."""
        # Convert attributes to integers using helper
        ui_data: Dict[str, Any] = {
            key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()
        }

        # Handle Text fields
        # usage of "or None" ensures empty strings become None for consistent validation
        ui_data["name"] = self.name_entry.get().strip() or None
        ui_data["country"] = self.country_entry.get().strip() or None
        ui_data["season"] = self.season_entry.get().strip() or None
        ui_data["height"] = self.height_entry.get().strip() or None

        # Handle Numeric bio fields (Age/Weight) - Convert to int standardizes them
        ui_data["age"] = safe_int_conversion(self.age_entry.get())
        ui_data["weight"] = safe_int_conversion(self.weight_entry.get())

        # Check dynamic attributes
        key_to_label = dict(self.attr_definitions)
        missing_fields = [
            key_to_label.get(key, key)
            for key in self.attr_vars.keys()
            if ui_data[key] is None
        ]
        # Check static fields
        if ui_data["name"] is None: missing_fields.append("Name")
        if ui_data["season"] is None: missing_fields.append("Season")
        if ui_data["age"] is None: missing_fields.append("Age")
        if ui_data["height"] is None: missing_fields.append("Height")
        if ui_data["weight"] is None: missing_fields.append("Weight")
        if ui_data["country"] is None: missing_fields.append("Country")

        if missing_fields:
            logger.warning(f"Validation failed: Missing fields - {', '.join(missing_fields)}")
            return

        try:
            # Buffer the data and attempt the persistent save
            self.controller.buffer_player_attributes(ui_data, gk=True, first=True)
            self.controller.save_player()
            
            logger.info(f"Successfully saved GK {ui_data['name']}. Navigating to Library.")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections from the Controller
            logger.error(f"Failed to save Goalkeeper data: {e}", exc_info=True)
    
    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
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