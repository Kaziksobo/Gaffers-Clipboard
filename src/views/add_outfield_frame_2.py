import customtkinter as ctk
import logging
from typing import Dict, Any, Tuple
from src.utils import safe_int_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import OCRDataMixin

logger = logging.getLogger(__name__)

class AddOutfieldFrame2(BaseViewFrame, OCRDataMixin):
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
        super().__init__(parent, controller, theme)
        
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

        for i in range(6):
            self.attributes_grid.grid_columnconfigure(i, weight=1 if i in [0, 5] else 0)
        # Use half the list height so the left and right columns share the same rows
        half = len(self.attr_definitions) // 2
        for i in range(half):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, (key, label) in enumerate(self.attr_definitions):
            row = i % half
            label_col = 1 if i < half else 3
            entry_col = label_col + 1
            self.create_data_row(
                parent_widget=self.attributes_grid,
                index=row,
                stat_key=key,
                stat_label=label,
                target_dict=self.attr_vars,
                label_col=label_col,
                entry_col=entry_col
            )
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=3, column=1, pady=(0, 20), sticky="ew")
    
    def on_done_button_press(self) -> None:
        """Collects attributes, validates them, and routes them to the Controller to save."""
        # Convert all technical attributes to integers
        ui_data = {key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()}

        # Validate that all attributes are within the expected range (1-99)
        if not self.validate_attr_range(ui_data, self.attr_definitions):
            return
        
        # Check for missing fields
        if not self.check_missing_fields(ui_data, dict(self.attr_definitions)):
            return

        try:
            logger.info("Validation passed. Buffering Outfield Page 2 and initiating final save.")
            
            # Step 1: Push Page 2 data to the buffer
            self.controller.buffer_player_attributes(ui_data, gk=False, first=False)
            
            # Step 2: Tell the Controller to cross the Pydantic boundary
            self.controller.save_player()
            
            # Step 3: Only navigate if the save was successful!
            logger.info("Outfield player successfully saved. Returning to Player Library.")
            self.show_success("Player Saved", "Outfield player data saved successfully! Returning to Player Library...")
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
            
        except Exception as e:
            # Catch Pydantic Validation errors or Database locks safely
            logger.error(f"Failed to save outfield player data: {e}", exc_info=True)
            self.show_error("Error Saving Player", f"An error occurred while saving the player data: \n{str(e)} \n\nPlease try again.")
            return