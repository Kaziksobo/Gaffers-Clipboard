import contextlib
import customtkinter as ctk
import logging
from typing import Dict, Any

from src.views.base_view_frame import BaseViewFrame
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class AddMatchFrame(BaseViewFrame):
    """Frame for adding a match.

    Collects the 'in-game date' and competition for the upcoming capture,
    buffers them into the controller, then initiates the screenshot/OCR flow.
    """

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        super().__init__(parent, controller, theme)

        logger.info("Initializing AddMatchFrame")

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

        # In-game date
        self.in_game_date_label = ctk.CTkLabel(self.form_frame, text="In-game date:", font=self.fonts["body"])
        self.in_game_date_label.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.in_game_date_entry = ctk.CTkEntry(self.form_frame, placeholder_text="dd/mm/yy", font=self.fonts["body"])
        self.in_game_date_entry.grid(row=0, column=1, pady=5, sticky="ew")
        self.form_frame.grid_columnconfigure(1, weight=1)

        # Competition dropdown
        self.competition_var = ctk.StringVar(value="Select Competition")
        comps = []
        # Try to prefetch from current career metadata
        try:
            if getattr(self.controller, "get_current_career_details", None):
                meta = self.controller.get_current_career_details()
                if meta and getattr(meta, "competitions", None):
                    comps = meta.competitions
        except Exception:
            comps = []

        self.competition_dropdown = ScrollableDropdown(
            self.form_frame,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.competition_var,
            values=comps,
            width=350,
            dropdown_height=200,
            placeholder="Select Competition"
        )
        self.competition_dropdown.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        # If no competitions are configured for this career, make the intent clear
        if not comps:
            self.competition_dropdown.set_value("No competitions available")

        # Info label
        delay_seconds = getattr(self.controller, "screenshot_delay", 3)
        self.sub_label = ctk.CTkLabel(
            self.container,
            text=f"Once you click Done, you have {delay_seconds} seconds to switch to the game and the correct screen.",
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
            command=lambda: self.on_done_button_press()
        )
        self.done_button.pack(pady=10)
        self.style_submit_button(self.done_button)

    def on_done_button_press(self) -> None:
        """Validate inputs, buffer match overview, then start OCR capture flow."""
        # Validate career loaded
        career_meta = None
        try:
            career_meta = self.controller.get_current_career_details()
        except Exception:
            career_meta = None

        if not career_meta:
            self.show_warning("No Career Loaded", "Please select or create a career before adding matches.")
            return

        # Validate competition list exists
        comps = getattr(career_meta, "competitions", []) or []
        if not comps:
            self.show_warning("No Competitions", "Your career has no competitions. Add competitions in Career Settings before adding a match.")
            return

        # Validate in-game date
        in_game_date = self.in_game_date_entry.get().strip()
        if not self.validate_in_game_date(in_game_date):
            return

        # Validate competition selection
        competition = self.competition_var.get()
        invalid_states = ["Select Competition", "", None]
        if competition in invalid_states:
            self.show_warning("No Competition Selected", "Please select a competition for this match.")
            return

        # Buffer partial overview so MatchStatsFrame can prefill
        ui_data = {
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
            logger.error(f"Failed to buffer match overview: {e}", exc_info=True)
            self.show_error("Error", f"Failed to save match overview: {e}")
            return

        # Start capture and navigate to MatchStatsFrame
        try:
            logger.info("Initiating match stats capture process.")
            self.controller.process_match_stats()
            self.controller.show_frame(self.controller.get_frame_class("MatchStatsFrame"))
        except Exception as e:
            logger.error(f"Match stats OCR process aborted. Navigation cancelled: {e}", exc_info=True)
            self.show_error("OCR Process Aborted", f"An error occurred while processing the match stats:\n{str(e)}\n\nPlease try again.")

    def on_show(self) -> None:
        """Lifecycle hook: refresh competitions from current career when displayed."""
        # Attempt to load competitions from current career metadata
        comps = []
        try:
            meta = self.controller.get_current_career_details()
            if meta and getattr(meta, "competitions", None):
                comps = meta.competitions
        except Exception:
            comps = []

        # Update dropdown options
        with contextlib.suppress(Exception):
            self.competition_dropdown.set_values(comps)
        # Update placeholder / current value
        if not comps:
            self.competition_dropdown.set_value("No competitions available")
            self.competition_var.set("No competitions available")
        else:
            # Reset to placeholder to force user selection each time
            self.competition_var.set("Select Competition")
            self.competition_dropdown.set_value("Select Competition")