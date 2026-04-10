"""UI frame for post-load primary navigation.

This module defines MainMenuFrame, the central hub shown after a career is
loaded. It personalizes welcome messaging, routes users to core workflows, and
guards match-entry navigation when required career configuration is missing.
"""

import contextlib
import logging

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, MainMenuFrameControllerProtocol
from src.schemas import CareerMetadata
from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)


class MainMenuFrame(BaseViewFrame):
    """Primary navigation frame displayed after career activation.

    The frame provides entry points for player library, match capture, and
    career settings while surfacing state-aware guidance for missing setup.
    """

    _show_main_menu_nav = False

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: MainMenuFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the main menu layout and actions.

        Creates welcome and prompt labels, initializes navigation buttons, and
        wires guarded navigation for match creation when competitions are not
        configured.

        Args:
            parent (ctk.CTkFrame): The parent container.
            controller (MainMenuFrameControllerProtocol):
                The main application controller.
            theme (BaseViewThemeProtocol): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        self.controller: MainMenuFrameControllerProtocol = controller

        logger.info("Initializing MainMenuFrame")

        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(5):
            self.grid_rowconfigure(i, weight=1 if i in [0, 4] else 0)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self, text=self._get_career_welcome_text(), font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, sticky="s", pady=(0, 60))
        self.register_wrapping_widget(self.main_heading, width_ratio=0.6)

        # Question Label
        self.question_label = ctk.CTkLabel(
            self, text="What would you like to do?", font=self.fonts["body"]
        )
        self.question_label.grid(row=2, column=1, sticky="s", pady=(0, 20))

        # Buttons Frame
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=3, column=1, sticky="nsew")
        self.button_frame.grid_columnconfigure((0, 1), weight=1)
        self.button_frame.grid_rowconfigure(0, weight=1)

        # Player Update Button
        self.player_update_button = ctk.CTkButton(
            self.button_frame,
            text="Enter Player Library",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            ),
        )
        self.player_update_button.grid(
            row=0, column=0, sticky="ew", padx=(0, 10), ipady=15
        )

        # Add Match Button
        self.add_match_button = ctk.CTkButton(
            self.button_frame,
            text="Add New Match",
            font=self.fonts["button"],
            command=self._on_add_match,
        )
        self.add_match_button.grid(row=0, column=1, sticky="ew", padx=(10, 0), ipady=15)

        # Career Settings Button
        self.career_settings_button = ctk.CTkButton(
            self,
            text="Career Settings",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("CareerConfigFrame")
            ),
        )
        self.career_settings_button.grid(row=4, column=1, pady=(10, 0), ipady=10)

    def on_show(self) -> None:
        """Refresh heading and state-aware styling when the frame is shown.

        Updates personalized welcome text and highlights the Career Settings
        action when no competitions are configured for the active career.
        """
        welcome_text: str = self._get_career_welcome_text()
        self.main_heading.configure(text=welcome_text)
        # If current career has no competitions, make
        # Career Settings button use the accent color
        meta: CareerMetadata = self.controller.get_current_career_details()
        with contextlib.suppress(Exception):
            if meta and (
                not getattr(meta, "competitions", [])
                or len(getattr(meta, "competitions", [])) == 0
            ):
                # Use accent for both background and hover when
                # emphasizing Career Settings
                self.career_settings_button.configure(
                    fg_color=self.theme.semantic_colors.accent,
                    hover_color=self.theme.semantic_colors.accent,
                )
            else:
                # restore defaults
                cfg: dict[str, str] = {}
                if self._career_settings_default_fg is not None:
                    cfg["fg_color"] = self._career_settings_default_fg
                if self._career_settings_default_hover is not None:
                    cfg["hover_color"] = self._career_settings_default_hover
                if cfg:
                    self.career_settings_button.configure(**cfg)

    def _get_career_welcome_text(self) -> str:
        """Generate the heading message for the current career context.

        Uses active career metadata when available and falls back to a generic
        application welcome message when no career is loaded.

        Returns:
            str: A formatted string including the club and manager name.
        """
        if current_career := self.controller.get_current_career_details():
            return (
                f"Welcome back to {current_career.club_name}, "
                f"{current_career.manager_name}!"
            )

        logger.warning("No active career found while generating welcome text.")
        return "Welcome to Gaffer's Clipboard!"

    def _on_add_match(self) -> None:
        """Validate prerequisites before navigating to AddMatchFrame.

        Ensures a career is loaded and has at least one configured competition
        before allowing navigation to the match-capture workflow.
        """
        meta: CareerMetadata = self.controller.get_current_career_details()
        if not meta:
            self.show_warning(
                "No Career", "Please load a career before adding a match."
            )
            return

        comps: list[str] = getattr(meta, "competitions", []) or []
        if not comps:
            self.show_warning(
                "No Competitions",
                (
                    "This career has no competitions configured. "
                    "Please add at least one competition in Career Settings "
                    "before adding a match."
                ),
            )
            return

        # Safe to navigate
        self.controller.show_frame(self.controller.get_frame_class("AddMatchFrame"))
