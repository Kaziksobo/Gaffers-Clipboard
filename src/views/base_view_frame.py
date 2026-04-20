"""Shared base view infrastructure for form-driven CustomTkinter screens.

This module defines `BaseViewFrame`, the common superclass for most view
frames in Gaffer's Clipboard. It consolidates cross-cutting UI concerns that
would otherwise be repeated in each screen, including main-menu navigation,
semantic button styling, popup routing, responsive label wrapping, and common
input validation.

Primary responsibilities:
- Provide a typed controller/theme boundary for MVC-safe interactions.
- Coordinate unsaved-work checks before navigation transitions.
- Expose alert helpers with consistent styling and interaction behavior.
- Generate standard label-and-entry rows backed by `ctk.StringVar` values.
- Supply hard and soft validation helpers for common form inputs.

Design notes:
- Feature frames are expected to compose domain-specific UI behavior on top of
    this base class rather than duplicating generic layout and validation code.
- Validation concerns stay in the UI layer, while persistence and schema
    enforcement remain delegated to controller and service boundaries.
"""

import logging
import re
import tkinter as tk
from datetime import datetime
from typing import Any

import customtkinter as ctk

from src.contracts.ui import (
    AlertOption,
    BaseViewControllerProtocol,
    BaseViewThemeProtocol,
    LatestMatchDateControllerProtocol,
    WarningValue,
    WidthEventProtocol,
)
from src.schemas import (
    ATTRIBUTE_RATING_MAX,
    ATTRIBUTE_RATING_MIN,
    CAREER_HALF_LENGTH_MAX,
    CAREER_HALF_LENGTH_MIN,
    PLAYER_AGE_MAX,
    PLAYER_AGE_MIN,
    PLAYER_WEIGHT_MAX,
    PLAYER_WEIGHT_MIN,
)
from src.views.widgets.custom_alert import CustomAlert

logger = logging.getLogger(__name__)


class BaseViewFrame(ctk.CTkFrame):
    """Shared parent frame for navigation and data-entry oriented views.

    Subclasses inherit common fonts, theme access, alert routing, and
    unsaved-work safeguards, then add only screen-specific controls and
    workflows. This keeps feature views focused on their domain logic while
    preserving consistent UX patterns across the application.

    Key capabilities:
    - Main-menu navigation with optional unsaved-work confirmation.
    - Semantic style hooks for submit and remove actions.
    - Responsive wraplength registration for long instructional labels.
    - Utility constructors for labeled data-entry rows.
    - Hard and soft validation helpers for frequently used input types.
    """

    _show_main_menu_nav = True

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: BaseViewControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Initialize the BaseViewFrame layout and common UI elements.

        Configure shared frame state, font references, responsive wrapping
        bindings, and optional main-menu navigation controls.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (BaseViewControllerProtocol): The main application controller.
            theme (BaseViewThemeProtocol): The application's theme configuration.
        """
        super().__init__(parent)
        self.controller: BaseViewControllerProtocol = controller
        self.theme: BaseViewThemeProtocol = theme
        self.fonts: dict[str, ctk.CTkFont] = self.controller.dynamic_fonts

        self.data_vars: dict[str, ctk.StringVar] = {}
        self._dismissed_warnings: list[tuple[str, WarningValue]] = []

        # Stores tuples of (widget_instance, width_ratio)
        self._wrapping_widgets: list[tuple[ctk.CTkLabel, float]] = []

        self.bind("<Configure>", self._apply_dynamic_wraps)

        if self._show_main_menu_nav:
            self._main_menu_button = ctk.CTkButton(
                self,
                text="← Main Menu",
                font=self.fonts["button"],
                command=self._on_main_menu_press,
            )
            self._main_menu_button.place(x=10, y=10)
            # Capture defaults so we can temporarily toggle visible fg on hover
            try:
                self._main_menu_button_default_fg: str | None = (
                    self._main_menu_button.cget("fg_color")
                )
            except Exception:
                self._main_menu_button_default_fg: str | None = None
            try:
                self._main_menu_button_default_hover: str | None = (
                    self._main_menu_button.cget("hover_color")
                )
            except Exception:
                self._main_menu_button_default_hover: str | None = None

            # Ensure hover state is always set; refresh on enter/leave
            self._main_menu_button.bind("<Enter>", self._on_main_menu_enter)
            self._main_menu_button.bind("<Leave>", self._on_main_menu_leave)
            self._refresh_main_menu_button_style()

    def style_submit_button(self, button: ctk.CTkButton) -> None:
        """Apply semantic hover styling for submit-action buttons.

        Args:
            button (ctk.CTkButton): Button widget to style.
        """
        button.configure(hover_color=self.theme.semantic_colors.submit_hover)

    def style_remove_button(self, button: ctk.CTkButton) -> None:
        """Apply semantic hover styling for remove-action buttons.

        Args:
            button (ctk.CTkButton): Button widget to style.
        """
        button.configure(hover_color=self.theme.semantic_colors.remove_hover)

    def _refresh_main_menu_button_style(self) -> None:
        """Refresh main-menu hover color based on unsaved-work state.

        Chooses a warning-style hover color when there is unsaved session data;
        otherwise uses the standard accent hover color.
        """
        if not self._show_main_menu_nav or not hasattr(self, "_main_menu_button"):
            return
        # Resolve safe color fallbacks in case theme entries are missing
        sc: BaseViewThemeProtocol = self.theme.semantic_colors
        accent: str = getattr(sc, "accent", "#00bfff")
        unsaved: str = getattr(
            sc, "unsaved_nav_hover", getattr(sc, "warning", "#ffcc00")
        )

        hover_color: str = (
            unsaved if self.controller.has_unsaved_work() else accent
        ) or accent

        try:
            self._main_menu_button.configure(hover_color=hover_color)
        except Exception:
            # Best-effort: ignore if widget doesn't accept hover_color on this platform
            logger.debug(
                "Could not configure main menu button hover color", exc_info=True
            )

    def _on_main_menu_enter(self, _event: tk.Event | None = None) -> None:
        """Apply a visible foreground color when the cursor enters navigation.

        Uses unsaved-work semantics to choose either warning or accent color.

        Args:
            _event (tk.Event | None, optional): Tkinter event payload for the
                enter binding.
        """
        sc: BaseViewThemeProtocol = self.theme.semantic_colors
        accent: str = getattr(sc, "accent", "#00bfff")
        unsaved: str = getattr(
            sc, "unsaved_nav_hover", getattr(sc, "warning", "#ffcc00")
        )
        fg: str = (unsaved if self.controller.has_unsaved_work() else accent) or accent
        try:
            self._main_menu_button.configure(fg_color=fg)
        except Exception:
            logger.debug(
                "Could not set main menu button fg_color on enter", exc_info=True
            )

    def _on_main_menu_leave(self, _event: tk.Event | None = None) -> None:
        """Restore the main-menu button foreground color on cursor leave.

        Args:
            _event (tk.Event | None, optional): Tkinter event payload for the
                leave binding.
        """
        try:
            if getattr(self, "_main_menu_button_default_fg", None) is not None:
                self._main_menu_button.configure(
                    fg_color=self._main_menu_button_default_fg
                )
        except Exception:
            logger.debug(
                "Could not restore main menu button fg_color on leave", exc_info=True
            )

    def refresh_semantic_styles(self) -> None:
        """Re-apply semantic styling for shared navigation controls."""
        self._refresh_main_menu_button_style()

    # --- Dynamic Wrapping for Responsiveness ---
    def register_wrapping_widget(
        self, widget: ctk.CTkLabel, width_ratio: float = 0.8
    ) -> None:
        """Register a label for automatic wraplength updates on resize.

        Args:
            widget (ctk.CTkLabel): Label widget whose wraplength should scale.
            width_ratio (float): Portion of frame width used for wraplength.
                Defaults to 0.8.
        """
        self._wrapping_widgets.append((widget, width_ratio))

    def _apply_dynamic_wraps(self, event: WidthEventProtocol) -> None:
        """Update registered label wraplengths in response to resize events.

        Args:
            event (WidthEventProtocol): Configure event containing current
                frame width.
        """
        if event.width > 100 and self._wrapping_widgets:
            for widget, ratio in self._wrapping_widgets:
                try:
                    dynamic_limit = int(event.width * ratio)
                    widget.configure(wraplength=dynamic_limit)
                except Exception as e:
                    logger.debug(f"Error applying dynamic wrap to widget {widget}: {e}")

    # --- Navigation ---
    def _on_main_menu_press(self) -> None:
        """Handle navigation back to the main menu with unsaved-work safeguards.

        Shows a confirmation warning when staged data exists, clears session
        buffers on confirmation, and routes the user to `MainMenuFrame`.
        """
        if self.controller.has_unsaved_work():
            result = self.show_warning(
                title="Unsaved Work",
                message=(
                    "You have unsaved work in progress. Returning to the main "
                    "menu will discard it.\n\nAre you sure you want to continue?"
                ),
                options=["Yes, Discard It", "No, Stay Here"],
            )
            if result != "Yes, Discard It":
                self._refresh_main_menu_button_style()
                return
            self.controller.clear_session_buffers()
            self._refresh_main_menu_button_style()

        self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))

    # --- Popup Managers ---
    def show_info(
        self,
        title: str,
        message: str,
        options: list[AlertOption] | None = None,
    ) -> str | None:
        """Display an informational alert dialog.

        The `options` argument supports label-only entries and hover-color
        overrides for individual buttons. Supported option shapes:
        - `"Undo"`
        - `(label, hover_color)`
        - `{'label': ..., 'hover_color': ...}`

        When an option does not provide a custom hover color, the dialog uses
        the alert's semantic accent color as the fallback hover color.

        Args:
            title (str): Alert title text.
            message (str): Alert body text.
            options (list[AlertOption] | None): Optional button definitions
                for custom actions.

        Returns:
            str | None: The selected option label, or None when no selection is
            returned by the dialog.
        """
        alert = CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="info",
            options=options,
        )
        return alert.get_result()

    def show_error(self, title: str, message: str) -> None:
        """Display a blocking error alert dialog.

        Args:
            title (str): Alert title text.
            message (str): Alert body text.
        """
        CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="error",
        )

    def show_success(self, title: str, message: str, timeout: int = 2) -> None:
        """Display a success alert that automatically closes after a timeout.

        Args:
            title (str): Alert title text.
            message (str): Alert body text.
            timeout (int): Auto-close duration in seconds. Defaults to 2.
        """
        CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="success",
            success_timeout=timeout,
        )

    def show_warning(
        self, title: str, message: str, options: list[str] | None = None
    ) -> str | None:
        """Display a warning alert dialog.

        Args:
            title (str): Alert title text.
            message (str): Alert body text.
            options (list[str] | None): Optional button labels for custom actions.

        Returns:
            str | None: The selected option label, or None when no selection is
            returned by the dialog.
        """
        alert = CustomAlert(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            title=title,
            message=message,
            alert_type="warning",
            options=options,
        )
        return alert.get_result()

    def confirm_discrepancy_force_save(
        self, discrepancies: dict[str, dict[str, int]]
    ) -> bool:
        """Ask whether to force-save when overview and player totals mismatch.

        Args:
            discrepancies (dict[str, dict[str, int]]): Per-stat discrepancy
                details collected by match stat cohesion checks.

        Returns:
            bool: True when the user confirms force-save; otherwise False.
        """
        lines: list[str] = []
        for stat, details in discrepancies.items():
            expected = details.get("expected", 0)
            actual = details.get("actual", 0)
            strict = bool(details.get("strict", True))
            severity = "strict" if strict else "warning"
            label = stat.replace("_", " ").title()
            lines.append(
                f"- {label}: team total = {expected}, player sum = {actual} ({severity})"
            )

        discrepancy_block = "\n".join(lines) if lines else "- No details available."
        result = self.show_warning(
            title="Stat Discrepancies Found",
            message=(
                "Team totals do not match the sum of scanned outfield player "
                "statistics.\n\n"
                f"{discrepancy_block}\n\n"
                "Select 'Force Save Match' to continue anyway, or 'Review Match "
                "Data' to correct the entries."
            ),
            options=["Force Save Match", "Review Match Data"],
        )
        return result == "Force Save Match"

    # --- UI Generators ---
    def create_data_row(
        self,
        parent_widget: ctk.CTkBaseClass,
        index: int,
        stat_key: str,
        stat_label: str,
        target_dict: dict[str, ctk.StringVar],
        label_col: int = 1,
        entry_col: int = 2,
        entry_width: int = 140,
    ) -> None:
        """Create a row in the UI for a specific stat, with a label and entry field.

        Creates and grids a label plus a bound entry widget, then stores the
        entry variable in `target_dict` under `stat_key`.

        Args:
            parent_widget (ctk.CTkBaseClass): Parent widget to which the row
                will be added.
            index (int): The row index for grid placement.
            stat_key (str): The key used to store the stat value in data_vars.
            stat_label (str): The label text to display for the stat.
            target_dict (dict[str, ctk.StringVar]): Destination mapping for the
                created entry variable.
            label_col (int): Grid column for the label. Defaults to 1.
            entry_col (int): Grid column for the entry. Defaults to 2.
            entry_width (int): Entry width in pixels. Defaults to 140.
        """
        label = ctk.CTkLabel(parent_widget, text=stat_label, font=self.fonts["body"])
        label.grid(row=index, column=label_col, sticky="w", padx=5, pady=5)

        entry_var = ctk.StringVar(value="")
        target_dict[stat_key] = entry_var
        entry = ctk.CTkEntry(
            parent_widget,
            textvariable=entry_var,
            width=entry_width,
            font=self.fonts["body"],
        )
        entry.grid(row=index, column=entry_col, sticky="ew", pady=5, padx=5)

    # --- Validation Helpers ---
    def check_missing_fields(
        self,
        data: dict[str, Any],
        key_to_label: dict[str, str],
        required_keys: list[str] | None = None,
        zero_invalid_keys: list[str] | None = None,
    ) -> bool:
        """Validate that required keys are present and non-empty.

        Optionally treats zero-like values as invalid for selected fields and
        surfaces a warning dialog listing all missing or invalid inputs.

        Args:
            data (dict[str, Any]): Input mapping to validate.
            key_to_label (dict[str, str]): Display labels keyed by data field.
            required_keys (list[str] | None): Specific keys to enforce. Defaults
                to all keys from `key_to_label`.
            zero_invalid_keys (list[str] | None): Keys for which zero-like values
                should be treated as invalid.

        Returns:
            bool: True when validation passes, False when it fails.
        """

        def is_zero_value(value: int | float | str | bool | None) -> bool:
            if value is None:
                return False
            if isinstance(value, bool):
                return False
            if isinstance(value, (int, float)):
                return value == 0

            normalized: str = str(value).strip().lower().replace(",", "")
            if normalized in {"", "none", "null", "n/a"}:
                return False
            try:
                return float(normalized) == 0
            except ValueError:
                return False

        if required_keys is None:
            required_keys: list[str] = list(key_to_label.keys())
        if zero_invalid_keys is None:
            zero_invalid_keys: list[str] = []

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
            missing_fields_text: str = ", ".join(
                key_to_label.get(key, key) for key in missing_fields
            )
            self.show_warning(
                title="Missing Information",
                message=(
                    "The following required fields are missing: "
                    f"{missing_fields_text}. "
                    "Please fill them in before proceeding."
                ),
            )
            return False
        return True

    def validate_attr_range(
        self,
        data: dict[str, Any],
        data_definitions: list[tuple[str, str]],
        min_val: int = ATTRIBUTE_RATING_MIN,
        max_val: int = ATTRIBUTE_RATING_MAX,
    ) -> bool:  # sourcery skip: extract-method
        """Validate numeric attribute values fall within an allowed range.

        Accepts int/float inputs directly and attempts string-to-float parsing
        for textual numeric inputs. Any non-numeric or out-of-range values are
        reported in a warning dialog.

        Args:
            data (dict[str, Any]): Attribute mapping to validate.
            data_definitions (list[tuple[str, str]]): Key/label pairs used for
                user-facing error messages.
            min_val (int): Inclusive minimum accepted value. Defaults to 1.
            max_val (int): Inclusive maximum accepted value. Defaults to 99.

        Returns:
            bool: True when all values are valid, otherwise False.
        """
        invalid_attrs: list[str] = []

        for key, value in data.items():
            if value is None:
                continue

            if isinstance(value, (int, float)):
                numeric_value = float(value)
            elif isinstance(value, str):
                normalized: str = value.strip().replace(",", "")
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
            key_to_label: dict[str, str] = dict(data_definitions)
            invalid_labels: list[str] = [
                key_to_label.get(key, key) for key in invalid_attrs
            ]
            invalid_labels_text: str = ", ".join(invalid_labels)
            logger.warning(
                "Validation failed: Invalid or non-numeric attribute values for %s",
                invalid_labels_text,
            )
            self.show_warning(
                title="Invalid Attribute Values",
                message=(
                    "The following attributes have invalid values (must be "
                    f"numeric and between {min_val} and {max_val}): "
                    f"{invalid_labels_text}. "
                    "Please correct them before proceeding."
                ),
            )
            return False
        return True

    def validate_season(self, season: str) -> str | None:
        """Validate and normalize season input to `YY/YY` format.

        Accepts either short form (`24/25`) or long form (`2024/2025`) and
        returns the standardized short representation.

        Args:
            season (str): Raw season string entered by the user.

        Returns:
            str | None: Normalized `YY/YY` season string, or None when invalid.
        """
        season: str = season.strip()
        if re.match(r"^(\d{2})/(\d{2})$", season):
            return season

        if long_match := re.match(r"^(\d{2})\d{2}/(\d{2})\d{2}$", season):
            start_suffix, end_suffix = long_match.groups()
            return f"{start_suffix}/{end_suffix}"

        logger.warning(f"Season validation failed for input: {season}")
        self.show_warning(
            title="Invalid Season Format",
            message=(
                "Season must be in the format '24/25' or '2024/2025'. "
                "Please correct it before proceeding."
            ),
        )
        return None

    def validate_half_length(
        self,
        half_length: int | None,
        min_length: int = CAREER_HALF_LENGTH_MIN,
        max_length: int = CAREER_HALF_LENGTH_MAX,
    ) -> bool:
        """Validate match half length against supported gameplay bounds.

        Args:
            half_length (int | None): Parsed half length value in minutes.
            min_length (int): Inclusive minimum allowed value. Defaults to 4.
            max_length (int): Inclusive maximum allowed value. Defaults to 20.

        Returns:
            bool: True when value is present and within range, otherwise False.
        """
        if half_length is None:
            logger.warning("Half length validation failed: value is missing")
            self.show_warning(
                title="Invalid Half Length",
                message=(
                    "Half length must be a whole number between "
                    f"{min_length} and {max_length} minutes."
                ),
            )
            return False

        if min_length <= half_length <= max_length:
            return True

        logger.warning(
            "Half length validation failed for value: %s (expected %s-%s)",
            half_length,
            min_length,
            max_length,
        )
        self.show_warning(
            title="Invalid Half Length",
            message=(
                f"Half length must be between {min_length} and {max_length} minutes."
            ),
        )
        return False

    def validate_height(self, height: str) -> str | None:
        """Validate and normalize height input to feet-and-inches format.

        Supports normalized form (`6'2"`) and alternate textual input
        (`6ft 2in`) with range checks for realistic feet/inches values.

        Args:
            height (str): Raw height string entered by the user.

        Returns:
            str | None: Normalized height string (`X'Y"`) or None when invalid.
        """
        height = height.strip()
        if normalized_match := re.match(r'^(\d{1,2})\'(\d{1,2})"$', height):
            feet = int(normalized_match[1])
            inches = int(normalized_match[2])
            if 1 <= feet <= 8 and 0 <= inches < 12:
                return f"{feet}'{inches}\""

        if match := re.match(r"^(\d{1,2})ft\s?(\d{1,2})in$", height):
            feet = int(match[1])
            inches = int(match[2])
            if 1 <= feet <= 8 and 0 <= inches < 12:
                return f"{feet}'{inches}\""

        logger.warning(f"Height validation failed for input: {height}")
        self.show_warning(
            title="Invalid Height Format",
            message=(
                "Height must be in the format '6'2\"' or '6ft 2in'. "
                "Please correct it before proceeding."
            ),
        )
        return None

    def soft_validate(
        self, warning_key: str, value: WarningValue, title: str, message: str
    ) -> bool:
        """Run an overridable validation warning with per-value dismissal memory.

        If the same `(warning_key, value)` pair has already been acknowledged,
        the check passes silently. Otherwise, the user can confirm the value or
        reject and return to editing.

        Args:
            warning_key (str): Stable identifier for the warning category.
            value (WarningValue): Value being validated and potentially
                remembered.
            title (str): Warning dialog title.
            message (str): Warning dialog body text.

        Returns:
            bool: True when validation is accepted, False when user chooses to fix.
        """
        if (warning_key, value) in self._dismissed_warnings:
            return True

        result = self.show_warning(
            title=title,
            message=message,
            options=["Yes, it's correct", "No, I'll fix it"],
        )
        if result == "Yes, it's correct":
            self._dismissed_warnings.append((warning_key, value))
            return True
        else:
            return False

    def validate_age(
        self,
        age: int | None,
        min_age: int = PLAYER_AGE_MIN,
        max_age: int = PLAYER_AGE_MAX,
    ) -> bool:
        """Hard-validate age against schema-backed bounds.

        Args:
            age (int | None): Age value to validate.
            min_age (int): Lower bound for accepted ages.
            max_age (int): Upper bound for accepted ages.

        Returns:
            bool: True when valid or empty, otherwise False.
        """
        if age is None:
            return True

        if min_age <= age <= max_age:
            return True

        logger.warning(
            "Age validation failed for value: %s (expected %s-%s)",
            age,
            min_age,
            max_age,
        )
        self.show_warning(
            title="Invalid Age",
            message=(
                f"Age must be between {min_age} and {max_age}. "
                "Please correct it before proceeding."
            ),
        )
        return False

    def validate_weight(
        self,
        weight: int | None,
        min_weight: int = PLAYER_WEIGHT_MIN,
        max_weight: int = PLAYER_WEIGHT_MAX,
    ) -> bool:
        """Hard-validate weight against schema-backed bounds.

        Args:
            weight (int | None): Weight in pounds.
            min_weight (int): Lower bound for accepted values.
            max_weight (int): Upper bound for accepted values.

        Returns:
            bool: True when valid or empty, otherwise False.
        """
        if weight is None:
            return True

        if min_weight <= weight <= max_weight:
            return True

        logger.warning(
            "Weight validation failed for value: %s (expected %s-%s)",
            weight,
            min_weight,
            max_weight,
        )
        self.show_warning(
            title="Invalid Weight",
            message=(
                f"Weight must be between {min_weight} and {max_weight} lbs. "
                "Please correct it before proceeding."
            ),
        )
        return False

    def validate_minutes_played(
        self, minutes: int | None, max_minutes: int = 150
    ) -> bool:
        """Soft-validate minutes played for positive and realistic bounds.

        Args:
            minutes (int | None): Minutes played value.
            max_minutes (int): Upper bound for expected match minutes.
                Defaults to 150.

        Returns:
            bool: True when valid or user-confirmed, otherwise False.
        """
        if minutes is not None and (minutes > max_minutes or minutes <= 0):
            return self.soft_validate(
                warning_key="minutes_played",
                value=minutes,
                title="Unusual Minutes Played Value",
                message=(
                    f"The minutes played you entered ({minutes}) is outside "
                    f"the typical range of 1-{max_minutes} minutes. "
                    "Are you sure this is correct?"
                ),
            )
        return True

    def validate_xg(self, xg: float | None, max_xg: float = 8.0) -> bool:
        """Soft-validate expected-goals value within plausible bounds.

        Args:
            xg (float | None): xG value to validate.
            max_xg (float): Upper bound for typical xG values. Defaults to 8.0.

        Returns:
            bool: True when valid or user-confirmed, otherwise False.
        """
        if xg is not None and (xg > max_xg or xg < 0):
            return self.soft_validate(
                warning_key="xg",
                value=xg,
                title="Unusual xG Value",
                message=(
                    f"The xG you entered ({xg}) is outside the typical range "
                    f"of 0-{max_xg}. Are you sure this is correct?"
                ),
            )
        return True

    def validate_pair_hard(
        self, data: dict[str, Any], constraints: list[tuple[str, str, str, str]]
    ) -> bool:
        """Hard-validate stat ordering constraints between paired fields.

        Each constraint enforces that value A must be less than or equal to
        value B when both are present.

        Args:
            data (dict[str, Any]): Source mapping containing numeric values.
            constraints (list[tuple[str, str, str, str]]): Constraint tuples in
                the form `(key_a, label_a, key_b, label_b)`.

        Returns:
            bool: True when all constraints pass, otherwise False.
        """
        violations: list[tuple[str, int, str, int]] = []
        for key_a, label_a, key_b, label_b in constraints:
            val_a: int | None = data.get(key_a)
            val_b: int | None = data.get(key_b)
            if val_a is not None and val_b is not None and val_a > val_b:
                violations.append((label_a, val_a, label_b, val_b))

        if violations:
            self.show_warning(
                title="Invalid stat pairs",
                message="The following stat pairs are inconsistent: \n\n"
                + "\n".join(
                    f"- {label_a} ({val_a}) should not be greater than "
                    f"{label_b} ({val_b})"
                    for label_a, val_a, label_b, val_b in violations
                )
                + "\n\nPlease correct these before proceeding.",
            )
            return False
        return True

    def validate_stat_max(
        self, data: dict[str, Any], stat_key: str, stat_label: str, max_value: int
    ) -> bool:
        """Soft-validate that a single stat does not exceed a threshold.

        Args:
            data (dict[str, Any]): Source mapping containing the target stat.
            stat_key (str): Data key for the stat value.
            stat_label (str): User-facing label used in warning text.
            max_value (int): Upper bound for typical values.

        Returns:
            bool: True when valid or user-confirmed, otherwise False.
        """
        value: int | None = data.get(stat_key)
        if value is not None and value > max_value:
            return self.soft_validate(
                warning_key=stat_key,
                value=value,
                title=f"Unusually High {stat_label}",
                message=(
                    f"The {stat_label} you entered ({value}) is unusually high "
                    f"(greater than {max_value}).\n"
                    "Are you sure this is correct?"
                ),
            )
        return True

    def validate_in_game_date(
        self, date_str: str, disallow_older_than_last: bool = False
    ) -> bool:
        """Validate in-game date format and optionally enforce chronology.

        Accepts `dd/mm/yy` and `dd/mm/yyyy` formats. When chronological
        enforcement is enabled, compares the parsed date against the latest
        saved match date provided by controllers supporting
        `LatestMatchDateControllerProtocol`.

        Args:
            date_str (str): The user-provided date string.
            disallow_older_than_last (bool): If True, block dates earlier than
                the latest stored match date.

        Returns:
            bool: True if valid (and passes chronological check when enabled),
            otherwise False.
        """
        date_str: str = date_str.strip()
        parsed: datetime | None = None
        for fmt in ("%d/%m/%y", "%d/%m/%Y"):
            try:
                parsed: datetime = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue

        if parsed is None:
            logger.warning(f"Date validation failed for input: {date_str}")
            self.show_warning(
                title="Invalid Date Format",
                message=(
                    "The 'In-game Date' field must be in the format dd/mm/yy "
                    "or dd/mm/yyyy. Please correct it before proceeding."
                ),
            )
            return False

        if disallow_older_than_last:
            latest: datetime | None = None
            try:
                if isinstance(self.controller, LatestMatchDateControllerProtocol):
                    latest: datetime | None = (
                        self.controller.get_latest_match_in_game_date()
                    )
            except Exception as e:
                logger.debug(
                    f"Could not retrieve latest match date for validation: {e}"
                )

            if latest is not None and parsed < latest:
                self.show_warning(
                    title="Date Earlier Than Last Match",
                    message=(
                        f"The date you entered ({date_str}) is earlier than "
                        "the most recent stored match "
                        f"({latest.strftime('%d/%m/%y')}).\n\n"
                        "Please enter a date on or after the most recent match date."
                    ),
                )
                return False

        return True
