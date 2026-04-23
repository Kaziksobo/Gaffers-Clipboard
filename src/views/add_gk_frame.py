"""UI frame for entering and saving goalkeeper profiles and attributes.

This module defines AddGKFrame, a CustomTkinter view that supports two input
flows: creating a new goalkeeper profile from scratch or updating an existing
goalkeeper selected from the player dropdown. The frame validates user input,
normalizes text and numeric values, stages data through the controller buffer,
and navigates back to the player library after successful persistence.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import AddGKFrameControllerProtocol, BaseViewThemeProtocol
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, OCRDataMixin, PlayerDropdownMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class AddGKFrame(BaseViewFrame, OCRDataMixin, PlayerDropdownMixin, EntryFocusMixin):
    """Data-entry frame for goalkeeper bio and attribute updates.

    The frame supports both creating a new goalkeeper and updating an existing
    one selected from the dropdown. It centralizes UI validation, normalization,
    and controller handoff so persistence logic remains outside the view layer.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: AddGKFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Initialize the goalkeeper form layout, widgets, and callbacks.

        Builds the full form hierarchy, including player identity widgets,
        in-game date capture, bio fields, and the goalkeeper attribute grid.
        It also configures all callbacks used during interaction: dropdown
        auto-fill behavior, submit handling, and focus flourishes for entry
        widgets.

        Internal dictionaries for dynamic field extraction are initialized here
        so later validation and controller payload construction can operate on
        a single normalized source of form values.

        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (AddGKFrameControllerProtocol): The main application
                controller.
            theme (BaseViewThemeProtocol): The theme dictionary containing
                color and font settings.
        """
        super().__init__(parent, controller, theme)
        self.controller: AddGKFrameControllerProtocol = controller

        logger.info("Initializing AddGKFrame")

        self.attr_vars: dict[str, ctk.StringVar] = {}
        self.attr_definitions: list[tuple[str, str]] = [
            ("diving", "Diving"),
            ("handling", "Handling"),
            ("kicking", "Kicking"),
            ("reflexes", "Reflexes"),
            ("positioning", "Positioning"),
        ]

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct and arrange widgets for goalkeeper data entry.

        Builds name selection, in-game date, bio, and attribute input controls
        so users can create or update goalkeeper profiles in a structured form.
        """
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
            width=200,
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
            command=self._on_player_selected,
        )
        self.player_dropdown.grid(
            row=1, column=2, pady=(10, 5), padx=(10, 0), sticky="w"
        )

        self.in_game_date_label = ctk.CTkLabel(
            self.name_and_date_frame, text="In-game date:", font=self.fonts["body"]
        )
        self.in_game_date_label.grid(
            row=2, column=1, padx=(20, 10), pady=(10, 5), sticky="w"
        )
        self.in_game_date_entry = ctk.CTkEntry(
            self.name_and_date_frame,
            placeholder_text="dd/mm/yy",
            font=self.fonts["body"],
        )
        self.in_game_date_entry.grid(
            row=2, column=2, pady=(10, 5), padx=(10, 20), sticky="ew"
        )

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
            width=160,
        )
        self.age_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (ft'in\")",
            font=self.fonts["body"],
            width=160,
        )
        self.height_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (lbs)",
            font=self.fonts["body"],
            width=160,
        )
        self.weight_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=self.fonts["body"],
            width=160,
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
                target_dict=self.attr_vars,
            )

        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=self.fonts["button"],
            command=lambda: self._on_done_button_press(),
        )
        self.done_button.grid(row=4, column=1, pady=(0, 20), sticky="ew")
        self.style_submit_button(self.done_button)

        self.apply_focus_flourishes(self)

    def on_show(self) -> None:
        """Reset all form controls when the frame becomes active.

        Called by the controller each time this frame is shown. This method
        Clears warning-dismissal state, resets dropdowns, clears text entries,
        and scrolls the attributes grid back to the top to ensure a fresh start
        for the user on each visit. This ensures that any previous data or warnings
        do not persist and interfere with new data entry attempts.
        """
        self._dismissed_warnings.clear()

        self.refresh_player_dropdown(only_gk=True)
        self.player_dropdown.set_value("Or select existing player")

        self.name_entry.delete(0, "end")
        self.name_entry.configure(placeholder_text="Enter name here")

        self.in_game_date_entry.delete(0, "end")
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")

        self.age_entry.delete(0, "end")
        self.age_entry.configure(placeholder_text="Age")

        self.height_entry.delete(0, "end")
        self.height_entry.configure(placeholder_text="Height (ft'in\")")

        self.weight_entry.delete(0, "end")
        self.weight_entry.configure(placeholder_text="Weight (lbs)")

        self.country_entry.delete(0, "end")
        self.country_entry.configure(placeholder_text="Country")

    def _on_player_selected(self, name: str) -> None:
        """Populate bio fields from the selected existing player record.

        When a known goalkeeper is selected, this method hydrates age, height,
        weight, and country fields from controller-provided bio data. If no bio
        is found for the selected name, the method exits without mutating form
        state.

        Args:
            name (str): Display name selected in the player dropdown.
        """
        bio = self.controller.get_player_bio(name)
        if bio is None:
            return
        self.age_entry.delete(0, "end")
        self.age_entry.insert(0, str(bio["age"]))
        self.height_entry.delete(0, "end")
        self.height_entry.insert(0, bio["height"])
        self.weight_entry.delete(0, "end")
        self.weight_entry.insert(0, str(bio["weight"]))
        self.country_entry.delete(0, "end")
        self.country_entry.insert(0, bio["country"])

    def _on_done_button_press(self) -> None:
        """Validate UI inputs, normalize payload values, and trigger save flow.

        This is the submit pipeline for the frame. It converts stat
        entries to integers, validates rating ranges, resolves whether the user
        is targeting an existing or new player, and enforces date and bio
        constraints. Optional values are normalized to ``None`` where needed so
        downstream validation semantics stay consistent.

        If all checks pass, the method delegates to buffering and persistence
        helpers that commit the payload through the controller and navigate back
        to the player library on success. Any failed validation step short-
        circuits the flow immediately.
        """
        # Convert attributes to integers using helper
        ui_data: dict[str, str | int | None] = {
            key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()
        }

        if not self.validate_attr_range(ui_data, self.attr_definitions):
            return

        # Handle Text fields
        # usage of "or None" ensures empty strings become None for consistent validation
        invalid_fields: list[str] = [
            "Enter name here",
            "dd/mm/yy",
            "Height (ft'in\")",
            "Weight (lbs)",
            "Country",
            "Age",
            "",
        ]
        player_name_dropdown: str | None = self.resolve_selected_player_name(
            self.player_dropdown_var.get()
        )
        ui_data["name"] = player_name_dropdown or self.name_entry.get().strip() or None

        if ui_data["name"] is None:
            self.show_error(
                "Validation Error", "Please enter a name or select an existing player."
            )
            return

        is_existing_player = player_name_dropdown is not None

        country: str = self.country_entry.get().strip()
        ui_data["country"] = country if country not in invalid_fields else None

        in_game_date: str = self.in_game_date_entry.get().strip()
        if not self.validate_in_game_date(in_game_date):
            return
        ui_data["in_game_date"] = in_game_date

        ui_data["height"] = self._get_height(invalid_fields)

        # Handle Numeric bio fields (Age/Weight) - Convert to int standardizes them
        age_raw: int | None = safe_int_conversion(self.age_entry.get())
        if age_raw is None:
            ui_data["age"] = None

        elif not self.validate_age(age_raw):
            return
        else:
            ui_data["age"] = age_raw
        weight_raw: int | None = safe_int_conversion(self.weight_entry.get())
        if weight_raw is None:
            ui_data["weight"] = None

        elif not self.validate_weight(weight_raw):
            return
        else:
            ui_data["weight"] = weight_raw

        if not self._validate_required_fields(ui_data, is_existing_player):
            return

        if not self._buffer_and_return(ui_data):
            return

    def _get_height(self, invalid_fields: list[str]) -> str | None:
        """Validate and normalize the height field if the user provided one.

        The height entry is optional for existing-player flows. Placeholder or
        sentinel text values are treated as empty, while non-empty values are
        passed through height-format validation before inclusion in the payload.

        Args:
            invalid_fields (list[str]): Sentinel placeholder values treated as
                empty or invalid for text inputs.

        Returns:
            str | None: Normalized height string when valid, otherwise None.
        """
        height_raw: str = self.height_entry.get().strip()
        if height_raw and height_raw not in invalid_fields:
            height: str | None = self.validate_height(height_raw)
            return None if height is None else height
        return None

    def _validate_required_fields(
        self, ui_data: dict[str, str | int | None], is_existing_player: bool
    ) -> bool:
        """Check whether all required fields are present for the save scenario.

        Required fields differ between existing-player and new-player flows.
        Existing players can reuse stored bio values, while new-player entries
        must provide complete identity and bio data. This method centralizes
        that branching rule and delegates final presence checks to the shared
        base-frame helper.

        Args:
            ui_data (dict[str, str | int | None]): Candidate payload assembled
                from current form values.
            is_existing_player (bool): True when a player was chosen from the
                dropdown; False for a newly entered player.

        Returns:
            bool: True when required fields are present; False otherwise.
        """
        key_to_label: dict[str, str] = dict(self.attr_definitions) | {
            "name": "Name",
            "country": "Country",
            "in_game_date": "In-game Date",
            "height": "Height",
            "age": "Age",
            "weight": "Weight",
        }
        if is_existing_player:
            required_keys: list[str] = [k for k, _ in self.attr_definitions] + [
                "name",
                "in_game_date",
            ]
        else:
            required_keys: list[str] | None = None
        return self.check_missing_fields(
            ui_data, key_to_label, required_keys=required_keys
        )

    def _buffer_and_return(self, ui_data: dict[str, str | int | None]) -> bool:
        # sourcery skip: extract-method
        """Buffer goalkeeper data, persist it, and return to the library view.

        The method stages validated data in the controller buffer and triggers
        the persistent save operation. On success, it emits user feedback and
        navigates to the player library. On failure, it logs full exception
        context and presents an actionable error dialog.

        Args:
            ui_data (dict[str, str | int | None]): Fully validated goalkeeper
                payload composed from form inputs.

        Returns:
            bool: True when save and navigation succeed; False when an error is

        """
        try:
            # Buffer the data and attempt the persistent save
            self.controller.buffer_player_attributes(
                ui_data, is_goalkeeper=True, is_first_page=True
            )
            self.controller.save_player()

            logger.info(
                f"Successfully saved GK {ui_data['name']}. Navigating to Library."
            )
            self.show_success(
                "Goalkeeper Saved", f"Goalkeeper {ui_data['name']} saved successfully!"
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
            return True
        except Exception as e:
            # Safely catch Pydantic rejections from the Controller
            logger.error(f"Failed to save Goalkeeper data: {e}", exc_info=True)
            self.show_error(
                "Error Saving Data", f"An error occurred: \n{e!s}\n\nPlease try again."
            )
            return False
