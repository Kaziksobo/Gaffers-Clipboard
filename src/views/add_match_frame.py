"""UI frame for initiating match capture and overview staging.

This module defines AddMatchFrame, a CustomTkinter view used to capture the
minimum metadata required before match-stat OCR begins. It validates career
context, date, and competition selection, buffers a partial overview payload,
and then hands control to the controller-driven capture and navigation flow.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import AddMatchFrameControllerProtocol, BaseViewThemeProtocol
from src.schemas import CareerMetadata
from src.views.base_view_frame import BaseViewFrame
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class AddMatchFrame(BaseViewFrame):
    """Data-entry frame for pre-capture match setup.

    Collects the in-game date and competition for the upcoming capture,
    buffers them into the controller, then initiates the screenshot and OCR
    workflow that feeds the match-stats entry frame.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: AddMatchFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the pre-capture match setup interface.

        Constructs the centered form layout, in-game date input, competition
        dropdown, and instructional labels shown before capture begins. During
        initialization, the frame attempts to prefetch competition values from
        the current career context so users can proceed with fewer manual steps.

        Args:
            parent (ctk.CTkFrame): Parent container that hosts the frame.
            controller (AddMatchFrameControllerProtocol): Controller handling
                buffering, OCR orchestration, and frame navigation.
            theme (BaseViewThemeProtocol): Theme tokens used for widget
                appearance and typography.
        """
        super().__init__(parent, controller, theme)
        self.controller: AddMatchFrameControllerProtocol = controller

        logger.info("Initializing AddMatchFrame")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct and arrange widgets for pre-match capture setup.

        Builds the centered container, in-game date field, competition dropdown,
        instructional text, and submit button so users can stage match metadata
        before OCR-based capture begins.
        """
        # Center container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(expand=True)

        # Instruction heading
        self.label = ctk.CTkLabel(
            self.container,
            text="Prepare to capture match overview",
            font=self.fonts["title"],
            anchor="center",
        )
        self.label.pack(pady=(0, 10))
        self.register_wrapping_widget(self.label, width_ratio=0.8)

        # Date + Competition subframe
        self.form_frame = ctk.CTkFrame(self.container)
        self.form_frame.pack(pady=(0, 10))
        self.form_frame.grid_columnconfigure(1, weight=1)

        # In-game date
        self.in_game_date_label = ctk.CTkLabel(
            self.form_frame, text="In-game date:", font=self.fonts["body"]
        )
        self.in_game_date_label.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.in_game_date_entry = ctk.CTkEntry(
            self.form_frame, placeholder_text="dd/mm/yy", font=self.fonts["body"]
        )
        self.in_game_date_entry.grid(row=0, column=1, pady=5, sticky="ew")

        # Competition dropdown
        self.competition_var = ctk.StringVar(value="Select Competition")
        comps = []
        # Try to prefetch from current career metadata
        try:
            if getattr(self.controller, "get_current_career_details", None):
                meta = self.controller.get_current_career_details()
                if meta and getattr(meta, "competitions", None):
                    comps = meta.competitions
        except Exception as e:
            logger.debug(
                "Competition prefetch failed during AddMatchFrame init: %s",
                e,
                exc_info=True,
            )
            comps = []
        logger.debug(
            "Loaded %s competition option(s) during AddMatchFrame init.",
            len(comps),
        )

        self.competition_dropdown = ScrollableDropdown(
            self.form_frame,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.competition_var,
            values=comps,
            width=350,
            dropdown_height=200,
            placeholder="Select Competition",
        )
        self.competition_dropdown.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        # If no competitions are configured for this career, make the intent clear
        if not comps:
            self.competition_dropdown.set_value("No competitions available")

        # Info label
        delay_seconds = getattr(self.controller, "screenshot_delay", 3)
        self.sub_label = ctk.CTkLabel(
            self.container,
            text=(
                f"Once you click Done, you have {delay_seconds} seconds to "
                "switch to the game and the correct screen."
            ),
            font=self.fonts["body"],
            anchor="center",
        )
        self.sub_label.pack()
        self.register_wrapping_widget(self.sub_label, width_ratio=0.8)

        # Done button
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=self.fonts["button"],
            command=lambda: self._on_done_button_press(),
        )
        self.done_button.pack(pady=10)
        self.style_submit_button(self.done_button)

    def on_show(self) -> None:
        """Refresh frame state when the view is raised.

        Reloads competition options from the currently active career, resets
        dropdown value state, and clears the in-game date field. This keeps
        pre-capture inputs synchronized with latest career metadata each time
        the frame is displayed.
        """
        # Attempt to load competitions from current career metadata
        comps: list[str] = []
        try:
            meta: CareerMetadata | None = self.controller.get_current_career_details()
            if meta and getattr(meta, "competitions", None):
                comps: list[str] = meta.competitions
        except Exception as e:
            logger.debug(
                "Failed to refresh competition list in AddMatchFrame.on_show: %s",
                e,
                exc_info=True,
            )
            comps: list[str] = []
        logger.debug(
            "Loaded %s competition option(s) in AddMatchFrame.on_show.",
            len(comps),
        )

        # Update dropdown options
        try:
            self.competition_dropdown.set_values(comps)
        except Exception as e:
            logger.debug(
                "Failed to set competition dropdown options in AddMatchFrame: %s",
                e,
                exc_info=True,
            )
        # Update placeholder / current value
        if not comps:
            self.competition_dropdown.set_value("No competitions available")
            self.competition_var.set("No competitions available")
        else:
            # Reset to placeholder to force user selection each time
            self.competition_var.set("Select Competition")
            self.competition_dropdown.set_value("Select Competition")

        # reset in-game date field
        self.in_game_date_entry.delete(0, "end")
        self.in_game_date_entry.configure(placeholder_text="dd/mm/yy")

    def _on_done_button_press(self) -> None:
        """Validate setup inputs, stage match overview, and start capture.

        This method is the submit pipeline for AddMatchFrame. It verifies that
        a career is loaded and has configured competitions, validates the
        in-game date against chronology rules, and enforces a valid competition
        selection. It then buffers a partial overview payload so downstream
        match-stats screens can prefill context.

        After buffering succeeds, the method triggers controller-managed OCR
        capture flow and navigates to MatchStatsFrame. Any validation, buffer,
        or OCR errors short-circuit with explicit user-facing feedback.
        """
        # Validate career loaded
        career_meta: CareerMetadata | None = None
        try:
            career_meta: CareerMetadata | None = (
                self.controller.get_current_career_details()
            )
        except Exception as e:
            logger.debug(
                "Failed to load current career metadata in AddMatchFrame: %s",
                e,
                exc_info=True,
            )
            career_meta = None

        if not career_meta:
            logger.warning("AddMatchFrame blocked: no active career loaded.")
            self.show_warning(
                "No Career Loaded",
                "Please select or create a career before adding matches.",
            )
            return

        # Validate competition list exists
        comps: list[str] = getattr(career_meta, "competitions", []) or []
        if not comps:
            logger.warning(
                "AddMatchFrame blocked: career '%s' has no competitions configured.",
                career_meta.club_name,
            )
            self.show_warning(
                "No Competitions",
                (
                    "Your career has no competitions. "
                    "Add competitions in Career Settings before adding a match."
                ),
            )
            return

        # Validate in-game date
        in_game_date: str = self.in_game_date_entry.get().strip()
        if not self.validate_in_game_date(in_game_date, disallow_older_than_last=True):
            return

        # Validate competition selection
        competition: str = self.competition_var.get()
        invalid_states: list[str | None] = ["Select Competition", "", None]
        if competition in invalid_states:
            logger.warning(
                "AddMatchFrame blocked: no competition selected. value='%s'",
                competition,
            )
            self.show_warning(
                "No Competition Selected", "Please select a competition for this match."
            )
            return

        # Buffer partial overview so MatchStatsFrame can prefill
        ui_data: dict[str, str | int | dict[str, int | float] | None] = {
            "in_game_date": in_game_date,
            "competition": competition,
            # other fields will be populated/validated in MatchStatsFrame
            "home_team_name": None,
            "away_team_name": None,
            "home_score": None,
            "away_score": None,
            "home_stats": {},
            "away_stats": {},
        }

        try:
            self.controller.buffer_match_overview(ui_data)
            logger.info("Buffered match overview from AddMatchFrame.")
        except Exception as e:
            logger.error("Failed to buffer match overview: %s", e, exc_info=True)
            self.show_error("Error", f"Failed to save match overview: {e}")
            return

        # Start capture and navigate to MatchStatsFrame
        try:
            logger.info("Initiating match stats capture process.")
            self.controller.process_match_stats()
            self.controller.show_frame(
                self.controller.get_frame_class("MatchStatsFrame")
            )
        except Exception as e:
            logger.error(
                "Match stats OCR process aborted. Navigation cancelled: %s",
                e,
                exc_info=True,
            )
            self.show_error(
                "OCR Process Aborted",
                (
                    "An error occurred while processing the "
                    f"match stats:\n{e!s}\n\nPlease try again."
                ),
            )
