"""Startup frame for selecting or creating career saves.

This module defines CareerSelectFrame, the first view shown when the
application starts. It presents existing career options, supports refreshing
available saves, validates user selection, and delegates career activation and
navigation to the controller.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import (
    BaseViewThemeProtocol,
    CareerSelectFrameControllerProtocol,
)
from src.views.base_view_frame import BaseViewFrame
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class CareerSelectFrame(BaseViewFrame):
    """Initial startup frame for career selection and new-career entry.

    The frame handles two primary paths: loading an existing career from the
    dropdown or navigating to the career creation flow.
    """

    _show_main_menu_nav = False

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: CareerSelectFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the startup career-selection interface.

        Creates heading and guidance labels, initializes the careers dropdown,
        and wires actions for loading an existing career or navigating to the
        new-career flow.

        Args:
            parent (ctk.CTkFrame): The parent container frame.
            controller (CareerSelectFrameControllerProtocol): The main
                application controller.
            theme (BaseViewThemeProtocol): The application's theme
                configuration dictionary.
        """
        super().__init__(parent, controller, theme)
        self.controller: CareerSelectFrameControllerProtocol = controller

        logger.info("Initializing CareerSelectFrame")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct and lay out the startup career-selection widgets.

        Initializes labels, dropdowns, and buttons, wiring them into the
        controller so users can load an existing career or begin creating a new one.
        """
        # --- Layout Configuration ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)

        for i in range(7):
            self.grid_rowconfigure(i, weight=1 if i in [0, 6] else 0)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self, text="Welcome to Gaffer's Clipboard!", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        self.register_wrapping_widget(self.main_heading, width_ratio=0.8)

        # Info label
        self.info_label = ctk.CTkLabel(
            self,
            text="Select an existing save or start a new journey",
            font=self.fonts["body"],
        )
        self.info_label.grid(row=2, column=1, pady=10)
        self.register_wrapping_widget(self.info_label, width_ratio=0.8)

        # Career select mini-grid
        self.career_select_frame = ctk.CTkFrame(self)
        self.career_select_frame.grid(row=3, column=1, pady=10)

        self.career_select_frame.grid_columnconfigure(0, weight=1)
        self.career_select_frame.grid_columnconfigure(1, weight=1)
        self.career_select_frame.grid_rowconfigure(0, weight=1)

        # Drop down of current careers
        self.careers_list_var = ctk.StringVar(value="Select Career")
        self.careers_dropdown = ScrollableDropdown(
            self.career_select_frame,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.careers_list_var,
            values=self.controller.get_all_career_names(),
            width=350,
            dropdown_height=200,
            placeholder="Select existing career",
        )
        self.careers_dropdown.grid(row=0, column=0, pady=10)

        # Select Career Button
        self.select_career_button = ctk.CTkButton(
            self.career_select_frame,
            text="Load Career",
            font=self.fonts["button"],
            command=self._on_select_button_press,
        )
        self.select_career_button.grid(row=0, column=1, padx=10, pady=10)

        # Or label
        self.or_label = ctk.CTkLabel(self, text="-- OR --", font=self.fonts["body"])
        self.or_label.grid(row=4, column=1, pady=10)

        # New Career Button
        self.new_career_button = ctk.CTkButton(
            self,
            text="Create New Career",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("CreateCareerFrame")
            ),
        )
        self.new_career_button.grid(row=5, column=1, pady=20)

    def on_show(self) -> None:
        """Refresh startup state whenever the frame becomes active.

        Ensures the careers dropdown reflects the latest saves and resets the
        visible prompt to require explicit user selection before load.
        """
        self._refresh_careers_dropdown()
        self.careers_dropdown.set_value("Select existing career")

    def _refresh_careers_dropdown(self) -> None:
        """Reload career options and preserve a sensible current selection.

        Fetches current career names from the controller, updates dropdown
        values, and applies a fallback value when the previous selection is no
        longer valid.
        """
        names: list[str] = self.controller.get_all_career_names()
        self.careers_dropdown.set_values(names)

        prev: str = self.careers_list_var.get()
        if prev not in names:
            # Fallback handling for empty states
            fallback_text: str = (
                names[0]
                if names and names[0] != "No Careers Available"
                else "Select Career"
            )
            self.careers_dropdown.set_value(fallback_text)

    def _on_select_button_press(self) -> None:
        """Validate selected career, activate it, and navigate to main menu.

        Guards against placeholder and invalid dropdown states, then delegates
        career activation to the controller. On success, navigation proceeds to
        MainMenuFrame; on failure, the method logs context and surfaces a
        user-facing error dialog.
        """
        selected_career: str = self.careers_list_var.get()

        invalid_states: list[str] = [
            "Select Career",
            "No Careers Available",
            "Click here to select career",
            "Select existing career",
            "",
        ]
        if selected_career in invalid_states:
            logger.warning(
                f"Invalid career selection attempted: '{selected_career}'. "
                "Aborting navigation."
            )
            self.show_warning(
                "No Career Selected",
                (
                    "Please choose an existing save from the dropdown, "
                    "or click 'Create New Career' to start fresh."
                ),
            )
            return

        logger.info(f"User validated and selected career: {selected_career}")
        try:
            self.controller.activate_career(selected_career)
            self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
        except Exception as e:
            logger.error(
                f"Failed to load career '{selected_career}': {e}", exc_info=True
            )
            self.show_error(
                "Error Loading Career",
                (
                    f"An error occurred while loading the selected career: {e!s}\n\n"
                    "Please try again."
                ),
            )
            return
