import customtkinter as ctk
import logging
import re
from typing import Dict, Any, Tuple
from src.utils import safe_int_conversion

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import OCRDataMixin, PlayerDropdownMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)

class AddOutfieldFrame1(BaseViewFrame, OCRDataMixin, PlayerDropdownMixin):
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
        
        self.name_and_date_frame = ctk.CTkFrame(self, fg_color=self.theme["colors"]["background"])
        self.name_and_date_frame.grid(row=1, column=1, pady=(10, 5), sticky="ew")
        self.name_and_date_frame.grid_columnconfigure(0, weight=1)
        self.name_and_date_frame.grid_columnconfigure(1, weight=0)
        self.name_and_date_frame.grid_columnconfigure(2, weight=0)
        self.name_and_date_frame.grid_columnconfigure(3, weight=1)
        self.name_and_date_frame.grid_rowconfigure(0, weight=1)
        self.name_and_date_frame.grid_rowconfigure(1, weight=0)
        self.name_and_date_frame.grid_rowconfigure(2, weight=0)
        self.name_and_date_frame.grid_rowconfigure(3, weight=1)
        
        self.name_entry = ctk.CTkEntry(
            self.name_and_date_frame,
            placeholder_text="Enter name here",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"],
            width=200
        )
        self.name_entry.grid(row=1, column=1, pady=(10, 5), padx=(0, 10), sticky="e")
        
        self.player_dropdown_var = ctk.StringVar(value="Or select existing player")
        self.player_dropdown = ScrollableDropdown(
            self.name_and_date_frame,
            theme=self.theme,
            variable=self.player_dropdown_var,
            width=200,
            dropdown_height=150,
            placeholder="Or select existing player",
            command=self._on_player_selected
        )
        self.player_dropdown.grid(row=1, column=2, pady=(10, 5), padx=(10, 0), sticky="w")
        
        self.in_game_date_label = ctk.CTkLabel(
            self.name_and_date_frame,
            text="In-game date:",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.in_game_date_label.grid(row=2, column=1, padx=(20, 10), pady=(10, 5), sticky="w")
        self.in_game_date_entry = ctk.CTkEntry(
            self.name_and_date_frame,
            placeholder_text="e.g. 01/07/29",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"],
            fg_color=self.theme["colors"]["entry_fg"]
        )
        self.in_game_date_entry.grid(row=2, column=2, pady=(10, 5), padx=(10, 20), sticky="ew")

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

    def _on_player_selected(self, name: str) -> None:
        """Auto-fill bio fields when an existing player is selected."""
        bio = self.controller.get_player_bio(name)
        if bio is None:
            return
        self.position_entry.delete(0, 'end')
        self.position_entry.insert(0, bio["positions"][-1])
        self.age_entry.delete(0, 'end')
        self.age_entry.insert(0, str(bio["age"]))
        self.height_entry.delete(0, 'end')
        self.height_entry.insert(0, bio["height"])
        self.weight_entry.delete(0, 'end')
        self.weight_entry.insert(0, str(bio["weight"]))
        self.country_entry.delete(0, 'end')
        self.country_entry.insert(0, bio["country"])

    def on_next_page(self) -> None:
        """Extracts data, validates completeness, buffers it, and transitions to Page 2."""
        # Convert attributes to int immediately
        ui_data: Dict[str, Any] = {key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()}

        if not self.validate_attr_range(ui_data, self.attr_definitions_physical + self.attr_definitions_mental):
            return

        # Handle Text fields
        # usage of "or None" ensures empty strings become None for consistent validation
        invalid_fields = ["Or select existing player", "Enter name here", "e.g. 01/07/29", "Height (ft'in\")", "Weight (lbs)", "Country", "Age", "No Players Found", "Position", ""]
        player_name_dropdown = self.player_dropdown_var.get()
        if player_name_dropdown in invalid_fields:
            player_name_dropdown = None
        ui_data["name"] = player_name_dropdown or self.name_entry.get().strip() or None

        if ui_data["name"] is None:
            self.show_error("Validation Error", "Please enter a name or select an existing player.")
            return

        is_existing_player = player_name_dropdown is not None

        country = self.country_entry.get().strip()
        ui_data["country"] = country if country not in invalid_fields else None

        in_game_date = self.in_game_date_entry.get().strip()
        if not self.validate_in_game_date(in_game_date):
            return
        ui_data["in_game_date"] = in_game_date

        height_raw = self.height_entry.get().strip()
        if height_raw and height_raw not in invalid_fields:
            height = self.validate_height(height_raw)
            if height is None:
                return
            ui_data["height"] = height
        else:
            ui_data["height"] = None

        position = self.position_entry.get().strip()
        ui_data["position"] = position if position not in invalid_fields else None

        # Handle Numeric bio fields
        age_raw = safe_int_conversion(self.age_entry.get())
        if age_raw is None:
            ui_data["age"] = None

        elif not self.validate_age(age_raw):
            return
        else:
            ui_data["age"] = age_raw
        weight_raw = safe_int_conversion(self.weight_entry.get())
        if weight_raw is None:
            ui_data["weight"] = None

        elif not self.validate_weight(weight_raw):
            return
        else:
            ui_data["weight"] = weight_raw
        key_to_label = {
            "name": "Name",
            "in_game_date": "In-game Date",
            "position": "Position",
            "height": "Height",
            "country": "Country",
            "age": "Age",
            "weight": "Weight",
        } | dict(self.attr_definitions_physical) | dict(self.attr_definitions_mental)
        if is_existing_player:
            required_keys = [k for k, _ in self.attr_definitions_physical] + [k for k, _ in self.attr_definitions_mental] + ["name", "in_game_date"]
        else:
            required_keys = None
        if not self.check_missing_fields(ui_data, key_to_label, required_keys=required_keys):
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
        self._dismissed_warnings.clear()
        
        self.refresh_player_dropdown(only_outfield=True)
        self.player_dropdown.set_value("Or select existing player")
        
        self.name_entry.delete(0, 'end')
        self.name_entry.configure(placeholder_text="Enter name here")
        
        self.in_game_date_entry.delete(0, 'end')
        self.in_game_date_entry.configure(placeholder_text="e.g. 01/07/29")
        
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