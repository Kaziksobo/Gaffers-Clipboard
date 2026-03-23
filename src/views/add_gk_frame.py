import customtkinter as ctk
import logging
from typing import Dict, Any
from src.utils import safe_int_conversion
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import OCRDataMixin, PlayerDropdownMixin, EntryFocusMixin

logger = logging.getLogger(__name__)

class AddGKFrame(BaseViewFrame, OCRDataMixin, PlayerDropdownMixin, EntryFocusMixin):
    """A data entry frame for processing and saving Goalkeeper attributes."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
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
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(6):
            self.grid_rowconfigure(i, weight=1 if i in [0, 5] else 0)
        
        self.name_and_date_frame = ctk.CTkFrame(self)
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
            font=self.fonts["body"],
            width=200
        )
        self.name_entry.grid(row=1, column=1, pady=(10, 5), padx=(0, 10), sticky="e")
        
        self.player_dropdown_var = ctk.StringVar(value="Or select existing player")
        self.player_dropdown = ScrollableDropdown(
            self.name_and_date_frame,
            theme=self.theme,
            fonts=self.fonts,
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
            font=self.fonts["body"]
        )
        self.in_game_date_label.grid(row=2, column=1, padx=(20, 10), pady=(10, 5), sticky="w")
        self.in_game_date_entry = ctk.CTkEntry(
            self.name_and_date_frame,
            placeholder_text="dd/mm/yy",
            font=self.fonts["body"]
        )
        self.in_game_date_entry.grid(row=2, column=2, pady=(10, 5), padx=(10, 20), sticky="ew")

        self.base_attr_row = ctk.CTkFrame(self)
        self.base_attr_row.grid(row=2, column=1, pady=(5, 10), sticky="nsew")
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
            font=self.fonts["body"],
            width=160
        )
        self.age_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (ft'in\")",
            font=self.fonts["body"],
            width=160
        )
        self.height_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (lbs)",
            font=self.fonts["body"],
            width=160
        )
        self.weight_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=self.fonts["body"],
            width=160
        )
        self.country_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.attributes_grid = ctk.CTkFrame(self)
        self.attributes_grid.grid(row=3, column=1, pady=(0, 10), sticky="nsew")
        
        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=1)
        for i in range(len(self.attr_definitions)):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, (key, label) in enumerate(self.attr_definitions):
            self.create_data_row(
                    parent_widget=self.attributes_grid,
                    index=i,
                    stat_key=key,
                    stat_label=label,
                    target_dict=self.attr_vars
            )
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=self.fonts["button"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=4, column=1, pady=(0, 20), sticky="ew")
        self.style_submit_button(self.done_button)
        
        self.apply_focus_flourishes(self)
    
    def _on_player_selected(self, name: str) -> None:
        """Auto-fill bio fields when an existing player is selected."""
        bio = self.controller.get_player_bio(name)
        if bio is None:
            return
        self.age_entry.delete(0, 'end')
        self.age_entry.insert(0, str(bio["age"]))
        self.height_entry.delete(0, 'end')
        self.height_entry.insert(0, bio["height"])
        self.weight_entry.delete(0, 'end')
        self.weight_entry.insert(0, str(bio["weight"]))
        self.country_entry.delete(0, 'end')
        self.country_entry.insert(0, bio["country"])

    def on_done_button_press(self) -> None:
        """Extract inputs, validate them, and route them to the Controller for saving."""
        # Convert attributes to integers using helper
        ui_data: Dict[str, Any] = {
            key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()
        }

        if not self.validate_attr_range(ui_data, self.attr_definitions):
            return

        # Handle Text fields
        # usage of "or None" ensures empty strings become None for consistent validation
        invalid_fields = ["Or select existing player", "Enter name here", "dd/mm/yy", "Height (ft'in\")", "Weight (lbs)", "Country", "Age", "No Players Found", ""]
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

        # Handle Numeric bio fields (Age/Weight) - Convert to int standardizes them
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
        key_to_label = dict(self.attr_definitions) | {
            "name": "Name",
            "country": "Country",
            "in_game_date": "In-game Date",
            "height": "Height",
            "age": "Age",
            "weight": "Weight",
        }
        if is_existing_player:
            required_keys = [k for k, _ in self.attr_definitions] + ["name", "in_game_date"]
        else:
            required_keys = None
        if not self.check_missing_fields(ui_data, key_to_label, required_keys=required_keys):
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
        self._dismissed_warnings.clear()
        
        self.refresh_player_dropdown(only_gk=True)
        self.player_dropdown.set_value("Or select existing player")
        
        self.name_entry.delete(0, 'end')
        self.name_entry.configure(placeholder_text="Enter name here")

        self.in_game_date_entry.delete(0, 'end')
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")
        
        self.age_entry.delete(0, 'end')
        self.age_entry.configure(placeholder_text="Age")
        
        self.height_entry.delete(0, 'end')
        self.height_entry.configure(placeholder_text="Height (ft'in\")")
        
        self.weight_entry.delete(0, 'end')
        self.weight_entry.configure(placeholder_text="Weight (lbs)")
        
        self.country_entry.delete(0, 'end')
        self.country_entry.configure(placeholder_text="Country")