import customtkinter as ctk
import logging
import re
from typing import Dict, Any
from src.views.widgets.custom_alert import CustomAlert
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
            logger.warning("OCR returned no GK attributes. Prompting user for manual entry.")
            for key in self.attr_vars:
                self.attr_vars[key].set("")

            CustomAlert(
                parent=self,
                theme=self.theme,
                title="OCR Failed",
                message="No goalkeeper data was detected. Please enter the values manually.",
                alert_type="warning",
            )
            return
            
        for key in self.attr_vars:
            self.attr_vars[key].set(str(stats.get(key, "")))
        
        logger.debug("AddGKFrame population complete.")
    
    def on_done_button_press(self) -> None:
        """Extract inputs, validate them, and route them to the Controller for saving."""
        # Convert attributes to integers using helper
        ui_data: Dict[str, Any] = {
            key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()
        }

        if invalid_attrs := [
            key
            for key, value in ui_data.items()
            if value is not None and (value > 99 or value < 1)
        ]:
            key_to_label = dict(self.attr_definitions)
            invalid_attr_labels = [key_to_label.get(key, key) for key in invalid_attrs]
            logger.warning(f"Validation failed: Invalid attribute values for {', '.join(invalid_attr_labels)}")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Invalid Attribute Values",
                message=f"The following attributes have invalid values (must be between 1 and 99): {', '.join(invalid_attr_labels)}. Please correct them before proceeding.",
                alert_type="warning",
            )
            return

        # Handle Text fields
        # usage of "or None" ensures empty strings become None for consistent validation
        ui_data["name"] = self.name_entry.get().strip() or None
        ui_data["country"] = self.country_entry.get().strip() or None
        ui_data["season"] = self.season_entry.get().strip() or None
        ui_data["height"] = self.height_entry.get().strip() or None

        # Handle Numeric bio fields (Age/Weight) - Convert to int standardizes them
        ui_data["age"] = safe_int_conversion(self.age_entry.get())
        ui_data["weight"] = safe_int_conversion(self.weight_entry.get())

        # Check if the season is in a valid format (e.g. "24/25") using a simple regex
        # If the season is in format "2024/2025", convert it to "24/25"
        # If the format is completely wrong, just set it to None
        if re.match(r'^\d{2}/\d{2}$', ui_data["season"]):
            pass
        elif re.match(r'^\d{4}/\d{4}$', ui_data["season"]):
            ui_data["season"] = f'{ui_data["season"][2:4]}/{ui_data["season"][7:9]}'
        else:
            ui_data["season"] = None

        # Check if the height is in a valid format (e.g. 6'2") using a simple regex
        # If the height is in format "6ft 2in", convert it to 6'2\"
        # If the format is completely wrong, just set it to None
        if re.match(r'^\d{1,2}\'\d{1,2}"$', ui_data["height"]):
            pass
        elif re.match(r'^\d{1,2}ft\s?\d{1,2}in$', ui_data["height"]):
            if match := re.match(
                r'^(\d{1,2})ft\s?(\d{1,2})in$', ui_data["height"]
            ):
                feet = match[1]
                inches = match[2]
                ui_data["height"] = f"{feet}'{inches}\""
        else:
            ui_data["height"] = None

        # Throw a warning if age is higher than 50 or lower than 14
        if ui_data["age"] is not None and (ui_data["age"] > 50 or ui_data["age"] < 14):
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Age Warning",
                message=f"Age {ui_data['age']} is outside the expected range of 14-50. Please verify.",
                alert_type="warning",
            )
            return

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
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Missing Information",
                message=f"The following required fields are missing: {', '.join(missing_fields)}. Please fill them in before proceeding.",
                alert_type="warning",
            )
            return

        try:
            # Buffer the data and attempt the persistent save
            self.controller.buffer_player_attributes(ui_data, gk=True, first=True)
            self.controller.save_player()

            logger.info(f"Successfully saved GK {ui_data['name']}. Navigating to Library.")
            CustomAlert(
                parent=self,
                theme = self.theme,
                title="Data Saved",
                message=f"Goalkeeper data for {ui_data['name']} in season {ui_data['season']} has been successfully saved.",
                alert_type="success",
                success_timeout=2
            )
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
        except Exception as e:
            # Safely catch Pydantic rejections from the Controller
            logger.error(f"Failed to save Goalkeeper data: {e}", exc_info=True)
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Error Saving Data",
                message=f"An error occurred while saving the Goalkeeper data: {str(e)}. Please try again.",
                alert_type="error",
            )
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