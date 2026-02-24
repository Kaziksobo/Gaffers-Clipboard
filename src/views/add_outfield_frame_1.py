import customtkinter as ctk
import logging
import re
from typing import Dict, Any, Tuple
from src.exceptions import UIPopulationError
from src.views.widgets.custom_alert import CustomAlert
from src.utils import safe_int_conversion

logger = logging.getLogger(__name__)

class AddOutfieldFrame1(ctk.CTkFrame):
    """A data entry frame for the first page of Outfield player attributes."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddOutfieldFrame1 layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The theme dictionary containing color and font settings.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme
        
        logger.info("Initializing AddOutfieldFrame1")
        
        self.attr_vars: Dict[str, ctk.StringVar] = {}
        self.attr_definitions_physical: list[Tuple[str, str]] = [
            ("acceleration", "Acceleration"),
            ("agility", "Agility"),
            ("balance", "Balance"),
            ("jumping", "Jumping"),
            ("sprint_speed", "Sprint Speed"),
            ("stamina", "Stamina"),
            ("strength", "Strength"),
        ]
        self.attr_definitions_mental: list[Tuple[str, str]] = [
            ("aggression", "Aggression"),
            ("att_position", "Att. Position"),
            ("composure", "Composure"),
            ("interceptions", "Interceptions"),
            ("reactions", "Reactions"),
            ("vision", "Vision"),
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
        self.base_attr_row.grid_columnconfigure(5, weight=0)
        self.base_attr_row.grid_columnconfigure(6, weight=1)
        self.base_attr_row.grid_rowconfigure(0, weight=1)
        
        self.position_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Position",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.position_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.age_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Age",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.age_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (ft'in\")",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.height_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (lbs)",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.weight_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=160
        )
        self.country_entry.grid(row=0, column=5, padx=5, pady=5, sticky="ew")
        
        self.attributes_grid = ctk.CTkScrollableFrame(self, fg_color=self.theme["colors"]["background"])
        self.attributes_grid.grid(row=4, column=1, pady=(0, 10), sticky="nsew")
       
        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=0)
        self.attributes_grid.grid_columnconfigure(4, weight=0)
        self.attributes_grid.grid_columnconfigure(5, weight=1)
        for i in range(max(len(self.attr_definitions_physical), len(self.attr_definitions_mental))):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, (key, label) in enumerate(self.attr_definitions_physical):
            self.create_stat_row(i, key, label, physical=True)

        for i, (key, label) in enumerate(self.attr_definitions_mental):
            self.create_stat_row(i, key, label, physical=False)
        
        self.next_page_button = ctk.CTkButton(
            self,
            text="Next Page",
            font=self.theme["fonts"]["button"],
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            command=lambda: self.on_next_page()
        )
        self.next_page_button.grid(row=5, column=1, pady=(5, 10), sticky="ew")

    def create_stat_row(self, index: int, attr_key: str, attr_label: str, physical: bool = True) -> None:
        """Creates a row in the attributes grid for a specific player attribute.
        
        Args:
            row (int): The row index in the grid.
            attr_key (str): The dictionary key for the data model.
            attr_label (str): The human-readable label for the UI.
            physical (bool): Determines the column (0 for physical, 1 for mental).
        """
        attr_label = ctk.CTkLabel(
            self.attributes_grid,
            text=attr_label,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        attr_label.grid(row=index, column=1 if physical else 3, padx=5, pady=5, sticky="w")
        
        attr_var = ctk.StringVar(value="")
        self.attr_vars[attr_key] = attr_var
        self.attr_entry = ctk.CTkEntry(
            self.attributes_grid,
            textvariable=attr_var,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
        )
        self.attr_entry.grid(row=index, column=2 if physical else 4, padx=5, pady=5, sticky="ew")
    
    def populate_stats(self, stats: Dict[str, Any]) -> None:
        """Populates the UI entry fields with OCR-detected statistics.
        
        Args:
            stats (Dict[str, Any]): A dictionary containing attribute keys and values.
            
        Raises:
            UIPopulationError: If the provided stats dictionary is empty.
        """
        logger.debug(f"Populating AddOutfieldFrame1 with stats: {stats.keys()}")
        if not stats:
            logger.warning("OCR returned no outfield player attributes. Prompting user for manual entry.")
            for key in self.attr_vars:
                self.attr_vars[key].set("")

            CustomAlert(
                parent=self,
                theme=self.theme,
                title="OCR Failed",
                message="No outfield player data was detected. Please enter the values manually.",
                alert_type="warning",
            )
            return
        
        for key in self.attr_vars:
            self.attr_vars[key].set(str(stats.get(key, "")))
        
        logger.debug("AddOutfieldFrame1 population complete.")

    def on_next_page(self) -> None:
        """Extracts data, validates completeness, buffers it, and transitions to Page 2."""
        # Convert attributes to int immediately
        ui_data: Dict[str, Any] = {key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()}

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
        # "or None" converts empty strings to None for consistent validation
        ui_data["season"] = self.season_entry.get().strip() or None
        ui_data["name"] = self.name_entry.get().strip() or None
        ui_data["position"] = self.position_entry.get().strip() or None
        ui_data["height"] = self.height_entry.get().strip() or None
        ui_data["country"] = self.country_entry.get().strip() or None

        # Handle Numeric bio fields
        ui_data["age"] = safe_int_conversion(self.age_entry.get())
        ui_data["weight"] = safe_int_conversion(self.weight_entry.get())

        # Validation Logic
        missing_fields = []

        # Check dynamic attributes (Physical & Mental)
        all_definitions = self.attr_definitions_physical + self.attr_definitions_mental
        key_to_label = dict(all_definitions)

        missing_fields.extend(
            key_to_label.get(key, key)
            for key in self.attr_vars.keys()
            if ui_data[key] is None
        )
        
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
        
        # Check static fields
        if ui_data["name"] is None: missing_fields.append("Name")
        if ui_data["season"] is None: missing_fields.append("Season")
        if ui_data["position"] is None: missing_fields.append("Position")
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
            logger.info("Validation passed. Buffering Outfield Page 1 and triggering Page 2 OCR.")
            # Buffer the current page's data
            self.controller.buffer_player_attributes(ui_data, gk=False, first=True)
            CustomAlert(
                parent=self,
                theme = self.theme,
                title="Data Saved",
                message=f"First page of outfield data for {ui_data['name']} in season {ui_data['season']} has been successfully saved.",
                alert_type="success",
                success_timeout=2
            )
            # Trigger OCR for the next page
            self.controller.process_player_attributes(gk=False, first=False)
            self.controller.show_frame(self.controller.get_frame_class("AddOutfieldFrame2"))
        except Exception as e:
            # Safely catch OCR or buffering failures so the app doesn't crash on transition
            logger.error(f"Failed to process transition to Page 2: {e}", exc_info=True)
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Error Saving Data",
                message=f"An error occurred while saving the Outfield data: {str(e)}. Please try again.",
                alert_type="error",
            )
            return
    
    def on_show(self) -> None:
        """Lifecycle hook to clear the UI fields when the frame is displayed."""
        self.name_entry.delete(0, 'end')
        self.name_entry.configure(placeholder_text="Enter name here")
        
        self.position_entry.delete(0, 'end')
        self.position_entry.configure(placeholder_text="Position")
        
        self.age_entry.delete(0, 'end')
        self.age_entry.configure(placeholder_text="Age")
        
        self.height_entry.delete(0, 'end')
        self.height_entry.configure(placeholder_text="Height (ft'in\")")
        
        self.weight_entry.delete(0, 'end')
        self.weight_entry.configure(placeholder_text="Weight (lbs)")
        
        self.country_entry.delete(0, 'end')
        self.country_entry.configure(placeholder_text="Country")
        
        # Reset scrollbar to top
        self.attributes_grid._parent_canvas.yview_moveto(0)