import customtkinter as ctk
import logging
import re
from typing import Dict, Any, List, Tuple, Optional
from src.views.widgets.custom_alert import CustomAlert

logger = logging.getLogger(__name__)

class BaseViewFrame(ctk.CTkFrame):
    """A base frame for all views in the app, providing common functionality and layout"""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]):
        """Initialize the BaseViewFrame layout and common UI elements.
        
        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme configuration.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme
        
        self.data_vars: Dict[str, ctk.StringVar] = {}
    
    # --- Popup Managers ---
    def show_error(self, title: str, message: str) -> None:
        """Show an error popup with the given title and message."""
        CustomAlert(
            parent=self,
            theme=self.theme,
            title=title,
            message=message,
            alert_type="error"
        )
    
    def show_success(self, title: str, message: str, timeout: int = 2) ->None:
        """Show a success popup with the given title and message, which auto-closes after a timeout."""
        CustomAlert(
            parent=self,
            theme=self.theme,
            title=title,
            message=message,
            alert_type="success",
            success_timeout=timeout
        )
    
    def show_warning(self, title: str, message: str) -> None:
        """Show a warning popup with the given title and message."""
        CustomAlert(
            parent=self,
            theme=self.theme,
            title=title,
            message=message,
            alert_type="warning"
        )
    
    # --- UI Generators ---
    def create_stat_row(
        self, 
        parent_widget: Any, 
        index: int, 
        stat_key: str, 
        stat_label: str,
        target_dict: Dict[str, ctk.StringVar],
        label_col: int = 1,
        entry_col: int = 2) -> None:
        """Create a row in the UI for a specific stat, with a label and entry field.
        
        Args:
            parent_widget (Any): The parent widget to which the row will be added.
            index (int): The row index for grid placement.
            stat_key (str): The key used to store the stat value in data_vars.
            stat_label (str): The label text to display for the stat.
        """
        label = ctk.CTkLabel(
            parent_widget,
            text=stat_label,
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        label.grid(row=index, column=label_col, sticky="w", padx=5, pady=5)
        
        entry_var = ctk.StringVar(value="")
        target_dict[stat_key] = entry_var
        entry = ctk.CTkEntry(
            parent_widget,
            textvariable=entry_var,
            font=self.theme["fonts"]["entry"],
            fg_color=self.theme["colors"]["entry_bg"],
            text_color=self.theme["colors"]["primary_text"]
        )
        entry.grid(row=index, column=entry_col, sticky="ew", pady=5, padx=5)
    
    # --- Validation Helpers ---
    def check_missing_fields(self, data: Dict[str, Any], key_to_label: Dict[str, str], required_keys: Optional[List[str]] = None) -> bool:
        if required_keys is None:
            required_keys = list(key_to_label.keys())
        missing_fields = [key for key in required_keys if not data.get(key) or str(data.get(key)).strip() == ""]
        if missing_fields:
            logger.debug(f"Missing required fields: {missing_fields}")
            self.show_warning(
                title="Missing Information",
                message=f"The following required fields are missing: {', '.join(key_to_label.get(key, key) for key in missing_fields)}. Please fill them in before proceeding.",
            )
            return True
        return False
    
    def validate_attr_range(self, data: Dict[str, Any], data_definitions: List[Tuple[str, str]], min_val: int = 1, max_val: int = 99) -> bool:
        if invalid_attrs := [
            key
            for key, value in data.items()
            if value is not None and (value > 99 or value < 1)
        ]:
            key_to_label = dict(data_definitions)
            invalid_labels = [key_to_label.get(key, key) for key in invalid_attrs]
            logger.warning(f"Validation failed: Invalid attribute values for {', '.join(invalid_labels)}")
            self.show_warning(
                title="Invalid Attribute Values",
                message=f"The following attributes have invalid values (must be between {min_val} and {max_val}): {', '.join(invalid_labels)}. Please correct them before proceeding.",
            )
            return True
        return False
    
    def validate_season(self, season: str) -> Optional[str]:
        """Validate and standardize season input. Returns standardized season or None if invalid."""
        season = season.strip()
        if re.match(r'^\d{2}/\d{2}$', season):
            return season
        elif re.match(r'^\d{4}/\d{4}$', season):
            return f'{season[2:4]}/{season[7:9]}'
        else:
            logger.warning(f"Season validation failed for input: {season}")
            self.show_warning(
                title="Invalid Season Format",
                message="Season must be in the format '24/25' or '2024/2025'. Please correct it before proceeding.",
            )
            return None
    
    def validate_height(self, height: str) -> Optional[str]:
        """Validate height input. Returns standardized height or None if invalid."""
        height = height.strip()
        if re.match(r'^\d{1,2}\'\d{1,2}"$', height):
            return height
        if match := re.match(
                r'^(\d{1,2})ft\s?(\d{1,2})in$', height
            ):
                feet = match[1]
                inches = match[2]
                height = f"{feet}'{inches}\""
                return height
        logger.warning(f"Height validation failed for input: {height}")
        self.show_warning(
            title="Invalid Height Format",
            message="Height must be in the format '6'2\"' or '6ft 2in'. Please correct it before proceeding.",
        )
        return None 
    
    def validate_age(self, age: int) -> bool:
        if age is not None and (age > 50 or age < 15):
            logger.warning(f"Age validation failed for input: {age}")
            self.show_warning(
                title="Age warning",
                message=f"Age {age} is outside the expected range (15-50). Please double check",
            )
            return True
        return False