import customtkinter as ctk
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from src.views.widgets.custom_alert import CustomAlert

logger = logging.getLogger(__name__)

class BaseViewFrame(ctk.CTkFrame):
    
    _show_main_menu_nav = True
    
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
        self.fonts = self.controller.dynamic_fonts
        
        self.data_vars: Dict[str, ctk.StringVar] = {}
        self._dismissed_warnings: List[Tuple[str, Any]] = []
        
        # Stores tuples of (widget_instance, width_ratio)
        self._wrapping_widgets: List[Tuple[ctk.CTkLabel, float]] = []
        
        self.bind("<Configure>", self._apply_dynamic_wraps)
        
        if self._show_main_menu_nav:
            self._main_menu_button = ctk.CTkButton(
                self,
                text="← Main Menu",
                fg_color=theme["colors"]["button_fg"],
                text_color=theme["colors"]["primary_text"],
                font=theme["fonts"]["button"],
                command=self._on_main_menu_press
            )
            self._main_menu_button.place(x=10, y=10)
    
    # --- Dynamic Wrapping for Responsiveness ---
    def register_wrapping_widget(self, widget: ctk.CTkLabel, width_ratio: float = 0.8) -> None:
        self._wrapping_widgets.append((widget, width_ratio))
    
    def _apply_dynamic_wraps(self, event: Any) -> None:
        if event.width > 100 and self._wrapping_widgets:
            for widget, ratio in self._wrapping_widgets:
                try:
                    dynamic_limit = int(event.width * ratio)
                    widget.configure(wraplength=dynamic_limit)
                except Exception as e:
                    logger.debug(f"Error applying dynamic wrap to widget {widget}: {e}")
    
    # --- Navigation ---
    def _on_main_menu_press(self) -> None:
        if self.controller.has_unsaved_work():
            result = self.show_warning(
                title="Unsaved Work",
                message="You have unsaved work in progress. Returning to the main menu will discard it.\n\nAre you sure you want to continue?",
                options=["Yes, Discard It", "No, Stay Here"]
            )
            if result != "Yes, Discard It":
                return
            self.controller.clear_session_buffers()
        
        self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
    
    # --- Popup Managers ---
    def show_info(self, title: str, message: str, options: Optional[List[str]] = None) -> Optional[str]:
        """Show an informational popup with the given title and message."""
        alert = CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="info",
            options=options
        )
        return alert.get_result()
    
    def show_error(self, title: str, message: str) -> None:
        """Show an error popup with the given title and message."""
        CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="error"
        )
    
    def show_success(self, title: str, message: str, timeout: int = 2) ->None:
        """Show a success popup with the given title and message, which auto-closes after a timeout."""
        CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="success",
            success_timeout=timeout
        )
    
    def show_warning(self, title: str, message: str, options: Optional[List[str]] = None) -> Optional[str]:
        """Show a warning popup with the given title and message."""
        alert = CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="warning",
            options=options
        )
        return alert.get_result()
    
    # --- UI Generators ---
    def create_data_row(
        self, 
        parent_widget: Any, 
        index: int, 
        stat_key: str, 
        stat_label: str,
        target_dict: Dict[str, ctk.StringVar],
        label_col: int = 1,
        entry_col: int = 2,
        entry_width: int = 140) -> None:
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
            font=self.fonts["body"],
            text_color=self.theme["colors"]["primary_text"]
        )
        label.grid(row=index, column=label_col, sticky="w", padx=5, pady=5)
        
        entry_var = ctk.StringVar(value="")
        target_dict[stat_key] = entry_var
        entry = ctk.CTkEntry(
            parent_widget,
            textvariable=entry_var,
            width=entry_width,
            font=self.fonts["body"],
            fg_color=self.theme["colors"]["entry_fg"],
            text_color=self.theme["colors"]["primary_text"]
        )
        entry.grid(row=index, column=entry_col, sticky="ew", pady=5, padx=5)
    
    # --- Validation Helpers ---
    def check_missing_fields(
        self,
        data: Dict[str, Any],
        key_to_label: Dict[str, str],
        required_keys: Optional[List[str]] = None,
        zero_invalid_keys: Optional[List[str]] = None,
    ) -> bool:
        """Validate that required keys are present and non-empty.

        Returns:
            bool: True when validation passes, False when it fails.
        """
        def is_zero_value(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, bool):
                return False
            if isinstance(value, (int, float)):
                return value == 0

            normalized = str(value).strip().lower().replace(",", "")
            if normalized in {"", "none", "null", "n/a"}:
                return False
            try:
                return float(normalized) == 0
            except ValueError:
                return False

        if required_keys is None:
            required_keys = list(key_to_label.keys())
        if zero_invalid_keys is None:
            zero_invalid_keys = []

        if missing_fields := [
            key
            for key in required_keys
            if (
                key not in data
                or data.get(key) is None
                or not str(data.get(key)).strip()
                or (key in zero_invalid_keys and is_zero_value(data.get(key)))
            )
        ]:
            logger.debug(f"Missing required fields: {missing_fields}")
            self.show_warning(
                title="Missing Information",
                message=f"The following required fields are missing: {', '.join(key_to_label.get(key, key) for key in missing_fields)}. Please fill them in before proceeding.",
            )
            return False
        return True
    
    def validate_attr_range(self, data: Dict[str, Any], data_definitions: List[Tuple[str, str]], min_val: int = 1, max_val: int = 99) -> bool:
        invalid_attrs: List[str] = []

        for key, value in data.items():
            if value is None:
                continue

            if isinstance(value, (int, float)):
                numeric_value = float(value)
            elif isinstance(value, str):
                normalized = value.strip().replace(",", "")
                if not normalized:
                    continue
                try:
                    numeric_value = float(normalized)
                except ValueError:
                    invalid_attrs.append(key)
                    continue
            else:
                invalid_attrs.append(key)
                continue

            if numeric_value > max_val or numeric_value < min_val:
                invalid_attrs.append(key)

        if invalid_attrs:
            key_to_label = dict(data_definitions)
            invalid_labels = [key_to_label.get(key, key) for key in invalid_attrs]
            logger.warning(f"Validation failed: Invalid or non-numeric attribute values for {', '.join(invalid_labels)}")
            self.show_warning(
                title="Invalid Attribute Values",
                message=f"The following attributes have invalid values (must be numeric and between {min_val} and {max_val}): {', '.join(invalid_labels)}. Please correct them before proceeding.",
            )
            return False
        return True
    
    def validate_season(self, season: str) -> Optional[str]:
        """Validate and standardize season input. Returns standardized season or None if invalid."""
        season = season.strip()
        if short_match := re.match(r'^(\d{2})/(\d{2})$', season):
            return season

        if long_match := re.match(r'^(\d{2})\d{2}/(\d{2})\d{2}$', season):
            start_suffix, end_suffix = long_match.groups()
            return f'{start_suffix}/{end_suffix}'

        logger.warning(f"Season validation failed for input: {season}")
        self.show_warning(
            title="Invalid Season Format",
            message="Season must be in the format '24/25' or '2024/2025'. Please correct it before proceeding.",
        )
        return None
    
    def validate_height(self, height: str) -> Optional[str]:
        """Validate height input. Returns standardized height or None if invalid."""
        height = height.strip()
        if normalized_match := re.match(r'^(\d{1,2})\'(\d{1,2})"$', height):
            feet = int(normalized_match[1])
            inches = int(normalized_match[2])
            if 1 <= feet <= 8 and 0 <= inches < 12:
                return f"{feet}'{inches}\""

        if match := re.match(r'^(\d{1,2})ft\s?(\d{1,2})in$', height):
            feet = int(match[1])
            inches = int(match[2])
            if 1 <= feet <= 8 and 0 <= inches < 12:
                return f"{feet}'{inches}\""

        logger.warning(f"Height validation failed for input: {height}")
        self.show_warning(
            title="Invalid Height Format",
            message="Height must be in the format '6'2\"' or '6ft 2in'. Please correct it before proceeding.",
        )
        return None 
    
    def soft_validate(self, warning_key: str, value: Any, title: str, message: str) -> bool:
        """Perform a soft validation that allows the user to override the warning."""
        if (warning_key, value) in self._dismissed_warnings:
            return True

        result = self.show_warning(
            title=title,
            message=message,
            options=["Yes, it's correct", "No, I'll fix it"]
        )
        if result == "Yes, it's correct":
            self._dismissed_warnings.append((warning_key, value))
            return True
        else:
            return False
    
    def validate_age(self, age: Optional[int], min_age: int = 15, max_age: int = 50) -> bool:
        if age is not None and (age > max_age or age < min_age):
            return self.soft_validate(
                warning_key="age",
                value=age,
                title="Unusual Age Value",
                message=f"The age you entered ({age}) is outside the typical range of {min_age}-{max_age}. Are you sure this is correct?"
            )
        return True
    
    def validate_weight(self, weight: Optional[int], min_weight: int = 100, max_weight: int = 400) -> bool:
        if weight is not None and (weight > max_weight or weight < min_weight):
            return self.soft_validate(
                warning_key="weight",
                value=weight,
                title="Unusual Weight Value",
                message=f"The weight you entered ({weight} lbs) is outside the typical range of {min_weight}-{max_weight} lbs. Are you sure this is correct?"
            )
        return True
    
    def validate_minutes_played(self, minutes: Optional[int], max_minutes: int = 150) -> bool:
        if minutes is not None and (minutes > max_minutes or minutes <= 0):
            return self.soft_validate(
                warning_key="minutes_played",
                value=minutes,
                title="Unusual Minutes Played Value",
                message=f"The minutes played you entered ({minutes}) is outside the typical range of 1-{max_minutes} minutes. Are you sure this is correct?"
            )
        return True
    
    def validate_xg(self, xg: Optional[float], max_xg: float = 8.0) -> bool:
        if xg is not None and (xg > max_xg or xg < 0):
            return self.soft_validate(
                warning_key="xg",
                value=xg,
                title="Unusual xG Value",
                message=f"The xG you entered ({xg}) is outside the typical range of 0-{max_xg}. Are you sure this is correct?"
            )
        return True
    
    def validate_pair_hard(
        self,
        data: Dict[str, Any],
        constraints: List[Tuple[str, str, str, str]]) -> bool:
        violations = []
        for key_a, label_a, key_b, label_b in constraints:
            val_a = data.get(key_a)
            val_b = data.get(key_b)
            if val_a is not None and val_b is not None and val_a > val_b:
                violations.append((label_a, val_a, label_b, val_b))
        
        if violations:
            self.show_warning(
                title="Invalid stat pairs",
                message="The following stat pairs are inconsistent: \n\n"
                        + "\n".join(f"- {label_a} ({val_a}) should not be greater than {label_b} ({val_b})" for label_a, val_a, label_b, val_b in violations)
                        + "\n\nPlease correct these before proceeding."
            )
            return False
        return True
    
    def validate_stat_max(self, data: Dict[str, Any], stat_key: str, stat_label: str, max_value: int) -> bool:
        value = data.get(stat_key)
        if value is not None and value > max_value:
            return self.soft_validate(
                warning_key=stat_key,
                value=value,
                title=f"Unusually High {stat_label}",
                message=f"The {stat_label} you entered ({value}) is unusually high (greater than {max_value}).\nAre you sure this is correct?"
            )
        return True
    
    def validate_in_game_date(self, date_str: str) -> bool:
        date_str = date_str.strip()
        try:
            datetime.strptime(date_str, "%d/%m/%y")
            return True
        except ValueError:
            logger.warning(f"Date validation failed for input: {date_str}")
            self.show_warning(
                title="Invalid Date Format",
                message="The 'In-game Date' field must be in the format dd/mm/yy. Please correct it before proceeding.",
            )
            return False