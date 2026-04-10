"""UI frame for finalizing outfield technical attributes.

This module defines AddOutfieldFrame2, the second page of the outfield player
entry workflow. It captures technical attribute ratings, validates completeness
and range constraints, buffers page-two values, and triggers final persistence
through the controller before returning to the player library.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import (
    AddOutfieldFrame2ControllerProtocol,
    BaseViewThemeProtocol,
)
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, OCRDataMixin

logger = logging.getLogger(__name__)


class AddOutfieldFrame2(BaseViewFrame, OCRDataMixin, EntryFocusMixin):
    """Second-page frame for outfield technical attribute entry.

    This frame handles the final stage of outfield data capture where
    technical ratings are completed and submitted for persistent save.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: AddOutfieldFrame2ControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the technical-attributes entry form.

        Creates the title, a two-column attributes grid, and a submit button
        for finalizing outfield player creation. Attribute definitions are
        stored in a single mapping list and rendered dynamically so labels,
        payload keys, and validation targets stay in sync.

        Args:
            parent (ctk.CTkFrame): The parent widget for this frame.
            controller (AddOutfieldFrame2ControllerProtocol): The main
                application controller.
            theme (BaseViewThemeProtocol): The theme dictionary containing
                color and font settings.
        """
        super().__init__(parent, controller, theme)
        self.controller: AddOutfieldFrame2ControllerProtocol = controller

        logger.info("Initializing AddOutfieldFrame2")

        self.attr_vars: dict[str, ctk.StringVar] = {}
        self.attr_definitions: list[tuple[str, str]] = [
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
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=5)

        self.title = ctk.CTkLabel(
            self, text="Page 2 - Technical Attributes", font=self.fonts["title"]
        )
        self.title.grid(row=1, column=1, pady=(20, 10))

        self.attributes_grid = ctk.CTkFrame(self)
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
                entry_col=entry_col,
            )

        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=self.fonts["button"],
            command=lambda: self._on_done_button_press(),
        )
        self.done_button.grid(row=3, column=1, pady=(0, 20), sticky="ew")
        self.style_submit_button(self.done_button)

        self.apply_focus_flourishes(self)

    def _on_done_button_press(self) -> None:
        """Validate technical attributes and complete outfield player save.

        This method is the submit pipeline for page two. It converts all
        technical inputs to integers, validates rating ranges, verifies missing
        fields, and then buffers the page-two payload in the controller.

        On successful buffering, it invokes the final save operation, reports
        success to the user, and navigates back to the player library. Any
        exceptions raised during buffer or save operations are logged and
        surfaced through an error dialog.
        """
        # Convert all technical attributes to integers
        ui_data: dict[str, int | None] = {
            key: safe_int_conversion(var.get()) for key, var in self.attr_vars.items()
        }

        # Validate that all attributes are within the expected range (1-99)
        if not self.validate_attr_range(ui_data, self.attr_definitions):
            return

        # Check for missing fields
        if not self.check_missing_fields(ui_data, dict(self.attr_definitions)):
            return

        try:
            logger.info(
                "Validation passed. Buffering Outfield Page 2 "
                "and initiating final save."
            )

            # Step 1: Push Page 2 data to the buffer
            self.controller.buffer_player_attributes(
                ui_data, is_goalkeeper=False, is_first_page=False
            )

            # Step 2: Tell the Controller to cross the Pydantic boundary
            self.controller.save_player()

            # Step 3: Only navigate if the save was successful!
            logger.info(
                "Outfield player successfully saved. Returning to Player Library."
            )
            self.show_success(
                "Player Saved",
                (
                    "Outfield player data saved successfully! "
                    "Returning to Player Library..."
                ),
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )

        except Exception as e:
            # Catch Pydantic Validation errors or Database locks safely
            logger.error(f"Failed to save outfield player data: {e}", exc_info=True)
            self.show_error(
                "Error Saving Player",
                (
                    f"An error occurred while saving the player data: \n{e!s} "
                    "\n\nPlease try again."
                ),
            )
            return
