import customtkinter as ctk
import logging
from typing import Dict, Any, Tuple
from src.exceptions import UIPopulationError
from src.views.widgets.custom_alert import CustomAlert
from src.utils import safe_int_conversion

logger = logging.getLogger(__name__)

class AddOutfieldFrame2(ctk.CTkFrame):
    """The outfield player attribute entry frame for the second page.
    
    Sets up input fields for technical attributes and configures the layout.
    """
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddOutfieldFrame2 layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The theme dictionary containing color and font settings.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme
        
        logger.info("Initializing AddOutfieldFrame2")
        
        self.attr_vars: Dict[str, ctk.StringVar] = {}
        self.attr_definitions: list[Tuple[str, str]] = [
            ("ball_control", "Ball Control"),
            ("crossing", "Crossing"),
            ("curve", "Curve"),
            ("defensive_awareness", "Def. Awareness"),
            ("dribbling", "Dribbling"),
            ("fk_accuracy", "FK Accuracy"),
            ("finishing", "Finishing"),
            ("heading_accuracy", "Heading Acc."),
            ("long_pass", "Long Pass"),
            ("long_shots", "Long Shots"),
            ("penalties", "Penalties"),
            ("short_pass", "Short Pass"),
            ("shot_power", "Shot Power"),
            ("slide_tackle", "Slide Tackle"),
            ("stand_tackle", "Stand Tackle"),
            ("volleys", "Volleys"),
        ]
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=5)
        
        self.title = ctk.CTkLabel(
            self,
            text="Page 2 - Technical Attributes",
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.title.grid(row=1, column=1, pady=(20, 10))
        
        self.attributes_grid = ctk.CTkScrollableFrame(self, fg_color=self.theme["colors"]["background"])
        self.attributes_grid.grid(row=2, column=1, pady=(10, 20), sticky="nsew")

        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=0)
        self.attributes_grid.grid_columnconfigure(4, weight=0)
        self.attributes_grid.grid_columnconfigure(5, weight=1)
        # Use half the list height so the left and right columns share the same rows
        half = len(self.attr_definitions) // 2
        for i in range(half):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, (key, label) in enumerate(self.attr_definitions):
            self.create_stat_row(i, key, label)
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=3, column=1, pady=(0, 20), sticky="ew")

    def create_stat_row(self, index: int, attr_key: str, attr_label: str) -> None:
        """Creates a row in the attributes grid for a specific technical attribute.
        
        Args:
            index (int): The index of the attribute in the list.
            attr_key (str): The name of the attribute to display.
            attr_label (str): The human-readable label for the UI.
        """
        # place items in two columns but on the same row index (row = index % half)
        half = 8  # number of rows per column (for a 16-item list)
        row = index % half
        # decide which side this attribute belongs to
        if index < half:
            left_column_label = 1
            label_col = left_column_label
            left_column_entry = 2
            entry_col = left_column_entry
        else:
            right_column_label = 3
            label_col = right_column_label
            right_column_entry = 4

            entry_col = right_column_entry

        attr_label = ctk.CTkLabel(
            self.attributes_grid,
            text=attr_label,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        attr_label.grid(row=row, column=label_col, padx=5, pady=5, sticky="w")

        attr_var = ctk.StringVar(value="")
        self.attr_vars[attr_key] = attr_var
        attr_entry = ctk.CTkEntry(
            self.attributes_grid,
            textvariable=attr_var,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
        )
        attr_entry.grid(row=row, column=entry_col, padx=5, pady=5, sticky="ew")
    
    def populate_stats(self, stats: Dict[str, Any]) -> None:
        """Populates the technical attribute entry fields with detected statistics.
        
        Args:
            stats (Dict[str, Any]): A dictionary containing attribute names and their values.
            
        Raises:
            UIPopulationError: If the provided stats dictionary is empty.
        """
        logger.debug(f"Populating AddOutfieldFrame2 with stats: {stats.keys()}")
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
        
        logger.debug("AddOutfieldFrame2 population complete.")
    
    def on_done_button_press(self) -> None:
        """Collects attributes, validates them, and routes them to the Controller to save."""
        # Convert all technical attributes to integers
        ui_data = {key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()}

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
        
        # Validate that no fields are None (missing)
        if missing_keys := [key for key, value in ui_data.items() if value is None]:
            key_to_label = dict(self.attr_definitions)
            missing_labels = [key_to_label[key] for key in missing_keys]
            logger.warning(f"Validation failed: Missing fields - {', '.join(missing_labels)}")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Missing Information",
                message=f"The following required fields are missing: {', '.join(missing_labels)}. Please fill them in before proceeding.",
                alert_type="warning",
            )
            return

        try:
            logger.info("Validation passed. Buffering Outfield Page 2 and initiating final save.")
            
            # Step 1: Push Page 2 data to the buffer
            self.controller.buffer_player_attributes(ui_data, gk=False, first=False)
            
            # Step 2: Tell the Controller to cross the Pydantic boundary
            self.controller.save_player()
            
            # Step 3: Only navigate if the save was successful!
            logger.info("Outfield player successfully saved. Returning to Player Library.")
            CustomAlert(
                parent=self,
                theme = self.theme,
                title="Data Saved",
                message=f"Full outfield data has been successfully saved.",
                alert_type="success",
                success_timeout=2
            )
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
            
        except Exception as e:
            # Catch Pydantic Validation errors or Database locks safely
            logger.error(f"Failed to save outfield player data: {e}", exc_info=True)
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="Error Saving Data",
                message=f"An error occurred while saving the Outfield data: {str(e)}. Please try again.",
                alert_type="error",
            )
            return