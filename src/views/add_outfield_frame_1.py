import customtkinter as ctk
import logging
import re
from typing import Dict, Any, Tuple
from src.utils import safe_int_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import OCRDataMixin

logger = logging.getLogger(__name__)

class AddOutfieldFrame1(BaseViewFrame, OCRDataMixin):
    """A data entry frame for the first page of Outfield player attributes."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the AddOutfieldFrame1 layout and input fields.
        
        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The theme dictionary containing color and font settings.
        """
        super().__init__(parent, controller, theme)
        
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
        for i in range(7):
            self.base_attr_row.grid_columnconfigure(i, weight=1 if i in [0, 6] else 0)
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
       
        for i in range(6):
            self.attributes_grid.grid_columnconfigure(i, weight=1 if i in [0, 5] else 0)
        for i in range(max(len(self.attr_definitions_physical), len(self.attr_definitions_mental))):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, (key, label) in enumerate(self.attr_definitions_physical):
            self.create_data_row(
                parent_widget=self.attributes_grid,
                index=i,
                stat_key=key,
                stat_label=label,
                target_dict=self.attr_vars,
                label_col=1,
                entry_col=2
            )

        for i, (key, label) in enumerate(self.attr_definitions_mental):
            self.create_data_row(
                parent_widget=self.attributes_grid,
                index=i,
                stat_key=key,
                stat_label=label,
                target_dict=self.attr_vars,
                label_col=3,
                entry_col=4
            )
        
        self.next_page_button = ctk.CTkButton(
            self,
            text="Next Page",
            font=self.theme["fonts"]["button"],
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            command=lambda: self.on_next_page()
        )
        self.next_page_button.grid(row=5, column=1, pady=(5, 10), sticky="ew")

    def on_next_page(self) -> None:
        """Extracts data, validates completeness, buffers it, and transitions to Page 2."""
        # Convert attributes to int immediately
        ui_data: Dict[str, Any] = {key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()}

        if not self.validate_attr_range(ui_data, self.attr_definitions_physical + self.attr_definitions_mental):
            return

        # Handle Text fields
        # "or None" converts empty strings to None for consistent validation
        season = self.validate_season(self.season_entry.get().strip())
        if season is None:
            return
        ui_data["season"] = season
        ui_data["name"] = self.name_entry.get().strip() or None
        ui_data["position"] = self.position_entry.get().strip() or None
        height = self.validate_height(self.height_entry.get().strip())
        if height is None:
            return
        ui_data["height"] = height
        ui_data["country"] = self.country_entry.get().strip() or None

        # Handle Numeric bio fields
        if not self.validate_age(safe_int_conversion(self.age_entry.get())):
            return
        ui_data["age"] = safe_int_conversion(self.age_entry.get())
        ui_data["weight"] = safe_int_conversion(self.weight_entry.get())

        key_to_label = {
            "name": "Name",
            "season": "Season",
            "position": "Position",
            "height": "Height",
            "country": "Country",
            "age": "Age",
            "weight": "Weight",
        } | self.attr_definitions_physical + self.attr_definitions_mental
        if not self.check_missing_fields(ui_data, key_to_label):
            return

        try:
            logger.info("Validation passed. Buffering Outfield Page 1 and triggering Page 2 OCR.")
            # Buffer the current page's data
            self.controller.buffer_player_attributes(ui_data, gk=False, first=True)
            self.show_success("Page 1 Saved", "Outfield Page 1 data saved successfully! Moving to Page 2...")
            # Trigger OCR for the next page
            self.controller.process_player_attributes(gk=False, first=False)
            self.controller.show_frame(self.controller.get_frame_class("AddOutfieldFrame2"))
        except Exception as e:
            # Safely catch OCR or buffering failures so the app doesn't crash on transition
            logger.error(f"Failed to process transition to Page 2: {e}", exc_info=True)
            self.show_error("Error Processing Data", f"An error occurred while processing the data: {str(e)}. Please try again.")
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