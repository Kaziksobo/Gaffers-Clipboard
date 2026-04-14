"""UI frame for first-page outfield player entry.

This module defines AddOutfieldFrame1, the first step of the outfield player
capture flow. It collects bio information and physical/mental attributes,
validates and normalizes form input, then buffers staged data before
transitioning to page two for technical attributes.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import (
    AddOutfieldFrame1ControllerProtocol,
    BaseViewThemeProtocol,
)
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, OCRDataMixin, PlayerDropdownMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class AddOutfieldFrame1(
    BaseViewFrame, OCRDataMixin, PlayerDropdownMixin, EntryFocusMixin
):
    """A data entry frame for the first page of Outfield player attributes."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: AddOutfieldFrame1ControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Initialize the AddOutfieldFrame1 layout and input fields.

        Builds a structured form with fields for player bio and attributes, along with
        a player selection dropdown. The layout is designed for clarity and ease of
        use, with responsive resizing and clear labeling.

        Internal dictionaries define the expected attributes and their labels,
        which are used to dynamically generate the input fields and
        validate the data on submission.

        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (AddOutfieldFrame1ControllerProtocol): The main
                application controller.
            theme (BaseViewThemeProtocol): The theme dictionary containing
                color and font settings.
        """
        super().__init__(parent, controller, theme)
        self.controller: AddOutfieldFrame1ControllerProtocol = controller

        logger.info("Initializing AddOutfieldFrame1")

        self.attr_vars: dict[str, ctk.StringVar] = {}
        self.attr_definitions_physical: list[tuple[str, str]] = [
            ("acceleration", "Acceleration"),
            ("agility", "Agility"),
            ("balance", "Balance"),
            ("jumping", "Jumping"),
            ("sprint_speed", "Sprint Speed"),
            ("stamina", "Stamina"),
            ("strength", "Strength"),
        ]
        self.attr_definitions_mental: list[tuple[str, str]] = [
            ("aggression", "Aggression"),
            ("att_position", "Att. Position"),
            ("composure", "Composure"),
            ("interceptions", "Interceptions"),
            ("reactions", "Reactions"),
            ("vision", "Vision"),
        ]

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(7):
            self.grid_rowconfigure(i, weight=1 if i in [0, 6] else 0)

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
        self.base_attr_row.grid(row=3, column=1, pady=(5, 10), sticky="nsew")
        for i in range(7):
            self.base_attr_row.grid_columnconfigure(i, weight=1 if i in [0, 6] else 0)
        self.base_attr_row.grid_rowconfigure(0, weight=1)

        self.position_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Position",
            font=self.fonts["body"],
            width=160,
        )
        self.position_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.age_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Age",
            font=self.fonts["body"],
            width=160,
        )
        self.age_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (ft'in\")",
            font=self.fonts["body"],
            width=160,
        )
        self.height_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (lbs)",
            font=self.fonts["body"],
            width=160,
        )
        self.weight_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=self.fonts["body"],
            width=160,
        )
        self.country_entry.grid(row=0, column=5, padx=5, pady=5, sticky="ew")

        self.attributes_grid = ctk.CTkScrollableFrame(self)
        self.attributes_grid.grid(row=4, column=1, pady=(0, 10), sticky="nsew")

        for i in range(6):
            self.attributes_grid.grid_columnconfigure(i, weight=1 if i in [0, 5] else 0)
        for i in range(
            max(len(self.attr_definitions_physical), len(self.attr_definitions_mental))
        ):
            self.attributes_grid.grid_rowconfigure(i, weight=1)

        for i, (key, label) in enumerate(self.attr_definitions_physical):
            self.create_data_row(
                parent_widget=self.attributes_grid,
                index=i,
                stat_key=key,
                stat_label=label,
                target_dict=self.attr_vars,
                label_col=1,
                entry_col=2,
            )

        for i, (key, label) in enumerate(self.attr_definitions_mental):
            self.create_data_row(
                parent_widget=self.attributes_grid,
                index=i,
                stat_key=key,
                stat_label=label,
                target_dict=self.attr_vars,
                label_col=3,
                entry_col=4,
            )

        self.next_page_button = ctk.CTkButton(
            self,
            text="Next Page",
            font=self.fonts["button"],
            command=lambda: self.on_next_page(),
        )
        self.next_page_button.grid(row=5, column=1, pady=(5, 10), sticky="ew")
        self.style_submit_button(self.next_page_button)

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

        self.refresh_player_dropdown(only_outfield=True)
        self.player_dropdown.set_value("Or select existing player")

        self.name_entry.delete(0, "end")
        self.name_entry.configure(placeholder_text="Enter name here")

        self.in_game_date_entry.delete(0, "end")
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")

        self.position_entry.delete(0, "end")
        self.position_entry.configure(placeholder_text="Position")

        self.age_entry.delete(0, "end")
        self.age_entry.configure(placeholder_text="Age")

        self.height_entry.delete(0, "end")
        self.height_entry.configure(placeholder_text="Height (ft'in\")")

        self.weight_entry.delete(0, "end")
        self.weight_entry.configure(placeholder_text="Weight (lbs)")

        self.country_entry.delete(0, "end")
        self.country_entry.configure(placeholder_text="Country")

        # Reset scrollbar to top
        self.attributes_grid._parent_canvas.yview_moveto(0)

    def _on_player_selected(self, name: str) -> None:
        """Populate bio fields from the selected existing player record.

        When a known player is selected, this method auto-fills position,
        age, height, weight, and country fields from the controller-provided
        bio data. If no bio is found for the selected name, the method exits
        without making any changes.

        Args:
            name (str): Display name selected in the player dropdown.
        """
        bio = self.controller.get_player_bio(name)
        if bio is None:
            return
        self.position_entry.delete(0, "end")
        self.position_entry.insert(0, bio["positions"][-1])
        self.age_entry.delete(0, "end")
        self.age_entry.insert(0, str(bio["age"]))
        self.height_entry.delete(0, "end")
        self.height_entry.insert(0, bio["height"])
        self.weight_entry.delete(0, "end")
        self.weight_entry.insert(0, str(bio["weight"]))
        self.country_entry.delete(0, "end")
        self.country_entry.insert(0, bio["country"])

    def on_next_page(self) -> None:
        # sourcery skip: remove-redundant-constructor-in-dict-union
        """Validate UI inputs, normalize payload values, buffer data and move to Page 2.

        This is the submit handler for the first page of the outfield player addition
        flow. It converts stat entries to integers, validates attribute ranges, resolves
        whether the user is targeting an existing or new player, and enforces date and
        bio constraints. Optional values are normalized to ``None`` where needed so
        downstream validation semantics stay consistent.

        If all checks pass, the method delegates to buffering and persistence helpers
        that stage the data in the controller and trigger the transition
        to the next page, which includes OCR processing. Any validation failure
        results in an error message and halts the submission process, while exceptions
        during buffering or transition are caught and reported without crashing the app.

        """
        # Convert attributes to int immediately
        ui_data: dict[str, str | int | None] = {
            key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()
        }

        if not self.validate_attr_range(
            ui_data, self.attr_definitions_physical + self.attr_definitions_mental
        ):
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
            "Position",
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

        position: str = self.position_entry.get().strip()
        ui_data["position"] = position if position not in invalid_fields else None

        # Handle Numeric bio fields
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

        if not self._buffer_and_transition(ui_data):
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
    ) -> bool:  # sourcery skip: remove-redundant-constructor-in-dict-union
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
        key_to_label: dict[str, str] = (
            {
                "name": "Name",
                "in_game_date": "In-game Date",
                "position": "Position",
                "height": "Height",
                "country": "Country",
                "age": "Age",
                "weight": "Weight",
            }
            | dict(self.attr_definitions_physical)
            | dict(self.attr_definitions_mental)
        )
        if is_existing_player:
            required_keys: list[str] = (
                [k for k, _ in self.attr_definitions_physical]
                + [k for k, _ in self.attr_definitions_mental]
                + ["name", "in_game_date"]
            )
        else:
            required_keys = None
        return self.check_missing_fields(
            ui_data, key_to_label, required_keys=required_keys
        )

    def _buffer_and_transition(self, ui_data: dict[str, str | int | None]) -> bool:
        """Buffer player data and move on to the next page.

        The method stages validated data in the controller buffer and triggers
        the transition to the next page, which includes OCR processing. Any
        exceptions during buffering or transition are caught and reported without
        crashing the app, allowing the user to attempt to fix any issues and resubmit.

        Args:
            ui_data (dict[str, str  |  int  |  None]): Fully validated outfield player
                                                       data ready for buffering and
                                                       persistence.

        Returns:
            bool: True when buffering and transition succeed;
                  False when an exception occurs.
        """
        try:
            logger.info(
                "Validation passed. Buffering Outfield Page 1 "
                "and triggering Page 2 OCR."
            )
            # Buffer the current page's data
            self.controller.buffer_player_attributes(
                ui_data, is_goalkeeper=False, is_first_page=True
            )
            self.show_success(
                "Page 1 Saved",
                "Outfield Page 1 data saved successfully! Moving to Page 2...",
            )
            # Trigger OCR for the next page
            self.controller.process_player_attributes(
                is_goalkeeper=False, is_first_page=False
            )
            self.controller.show_frame(
                self.controller.get_frame_class("AddOutfieldFrame2")
            )
            return True
        except Exception as e:
            # Safely catch OCR or buffering failures so the
            # app doesn't crash on transition
            logger.error(f"Failed to process transition to Page 2: {e}", exc_info=True)
            self.show_error(
                "Error Processing Data",
                (
                    f"An error occurred while processing the data: {e!s}. "
                    "Please try again."
                ),
            )
            return False
