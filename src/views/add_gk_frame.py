import customtkinter as ctk
import logging
import re
from typing import Dict, Any
from src.utils import safe_int_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import OCRDataMixin

logger = logging.getLogger(__name__)

class AddGKFrame(BaseViewFrame, OCRDataMixin):
    """A data entry frame for processing and saving Goalkeeper attributes."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddGKFrame layout and input fields.

        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The theme dictionary containing color and font settings.
        """
        super().__init__(parent, controller, theme)
        
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
            self.create_attribute_row(
                    parent_widget=self.attributes_grid,
                    index=i,
                    stat_key=key,
                    stat_label=label,
                    target_dict=self.attr_vars
            )
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=self.theme["fonts"]["button"],
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=5, column=1, pady=(0, 20), sticky="ew")
    
    def on_done_button_press(self) -> None:
        """Extract inputs, validate them, and route them to the Controller for saving."""
        # Convert attributes to integers using helper
        ui_data: Dict[str, Any] = {
            key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()
        }
        
        if self.validate_attr_range(ui_data, self.attr_definitions):
            return

        # Handle Text fields
        # usage of "or None" ensures empty strings become None for consistent validation
        ui_data["name"] = self.name_entry.get().strip() or None
        ui_data["country"] = self.country_entry.get().strip() or None
        
        season = self.validate_season(self.season_entry.get().strip())
        if season is None:
            return
        ui_data["season"] = season
        
        height = self.validate_height(self.height_entry.get().strip())
        if height is None:
            return
        ui_data["height"] = height

        # Handle Numeric bio fields (Age/Weight) - Convert to int standardizes them
        ui_data["age"] = self.validate_age(safe_int_conversion(self.age_entry.get()))
        ui_data["weight"] = safe_int_conversion(self.weight_entry.get())

        key_to_label = {key: label for key, label in self.attr_definitions}
        key_to_label.update({
            "name": "Name",
            "country": "Country",
            "season": "Season",
            "height": "Height",
            "age": "Age",
            "weight": "Weight"
        })
        if self.check_missing_fields(ui_data, key_to_label):
            return

        try:
            # Buffer the data and attempt the persistent save
            self.controller.buffer_player_attributes(ui_data, gk=True, first=True)
            self.controller.save_player()

            logger.info(f"Successfully saved GK {ui_data['name']}. Navigating to Library.")
            self.show_success("Goalkeeper Saved", f"Goalkeeper {ui_data['name']} saved successfully!")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections from the Controller
            logger.error(f"Failed to save Goalkeeper data: {e}", exc_info=True)
            self.show_error("Error Saving Data", f"An error occurred: \n{str(e)}\n\nPlease try again.")
            return
    
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