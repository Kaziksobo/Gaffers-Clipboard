"""UI frame for validating and buffering team-level match statistics.

This module defines MatchStatsFrame, the team-overview stage of the match
entry workflow. It collects home and away team data, enforces numeric and
consistency checks, buffers validated overview payloads, and routes users into
player-performance capture or final match persistence.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, MatchStatsFrameControllerProtocol
from src.schemas import MATCH_YELLOW_CARDS_MAX, MATCH_YELLOW_CARDS_MIN
from src.utils import safe_float_conversion, safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin, OCRDataMixin

logger = logging.getLogger(__name__)


class MatchStatsFrame(BaseViewFrame, OCRDataMixin, EntryFocusMixin):
    """Data-entry frame for team match overview validation and staging.

    The frame supports OCR-assisted correction of match-level fields and acts
    as the gate before player-level performance capture or final save.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: MatchStatsFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the team match-statistics review interface.

        Creates team identity and score inputs, a paired home/away statistics
        grid, and navigation controls for branching into player or goalkeeper
        performance capture flows. Widgets are wired to callbacks that validate
        and stage overview data before downstream workflow transitions.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (MatchStatsFrameControllerProtocol):
                The main application controller.
            theme (BaseViewThemeProtocol): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        self.controller: MatchStatsFrameControllerProtocol = controller

        logger.info("Initializing MatchStatsFrame")

        # Attributes to store stat variables
        self.home_stats_vars: dict[str, ctk.StringVar] = {}
        self.away_stats_vars: dict[str, ctk.StringVar] = {}

        self.stat_definitions: list[tuple[str, str]] = [
            ("possession", "Possession (%)"),
            ("ball_recovery", "Ball Recovery Time (seconds)"),
            ("shots", "Shots"),
            ("xg", "xg"),
            ("passes", "Passes"),
            ("tackles", "Tackles"),
            ("tackles_won", "Tackles Won"),
            ("interceptions", "Interceptions"),
            ("saves", "Saves"),
            ("fouls_committed", "Fouls Committed"),
            ("offsides", "Offsides"),
            ("corners", "Corners"),
            ("free_kicks", "Free Kicks"),
            ("penalty_kicks", "Penalty Kicks"),
            ("yellow_cards", "Yellow Cards"),
        ]

        # Variables for team names and scores
        self.home_team_name_var = ctk.StringVar(value="Home Team")
        self.away_team_name_var = ctk.StringVar(value="Away Team")
        self.home_team_score_var = ctk.StringVar(value="0")
        self.away_team_score_var = ctk.StringVar(value="0")

        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Title
        self.grid_rowconfigure(2, weight=0)  # Info label
        self.grid_rowconfigure(3, weight=1)  # Stats grid
        self.grid_rowconfigure(4, weight=0)  # Direction subgrid
        self.grid_rowconfigure(5, weight=1)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self, text="Review Match Statistics", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))

        # Info Label
        self.info_label = ctk.CTkLabel(
            self,
            text=(
                "Please review the captured match data. Fill in any missing fields "
                "and correct any inaccuracies."
            ),
            font=self.fonts["body"],
        )
        self.info_label.grid(row=2, column=1, pady=(0, 20))
        self.register_wrapping_widget(self.info_label, width_ratio=0.6)

        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self)
        self.stats_grid.grid(row=3, column=1, pady=(0, 20), sticky="nsew")

        # Configure subgrid
        for col in range(5):
            self.stats_grid.grid_columnconfigure(col, weight=1)
        for row in range(len(self.stat_definitions)):
            self.stats_grid.grid_rowconfigure(row, weight=1)

        # Populate subgrid with entry fields
        self.home_team_name = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.home_team_name_var,
            width=200,
            font=self.fonts["body"],
        )
        self.home_team_name.grid(row=0, column=0, padx=5, pady=5)

        self.home_team_score = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.home_team_score_var,
            width=80,
            font=self.fonts["body"],
        )
        self.home_team_score.grid(row=0, column=1, padx=5, pady=5)

        self.score_dash = ctk.CTkLabel(
            self.stats_grid, text="-", font=self.fonts["body"]
        )
        self.score_dash.grid(row=0, column=2, padx=5, pady=5)
        self.away_team_score = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.away_team_score_var,
            width=80,
            font=self.fonts["body"],
        )
        self.away_team_score.grid(row=0, column=3, padx=5, pady=5)

        self.away_team_name = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.away_team_name_var,
            width=200,
            font=self.fonts["body"],
        )
        self.away_team_name.grid(row=0, column=4, padx=5, pady=5)

        for i, (stat_key, stat_label) in enumerate(self.stat_definitions):
            self._create_home_away_stat_row(i + 1, stat_key, stat_label)

        # Direction subgrid
        self.direction_frame = ctk.CTkFrame(self)
        self.direction_frame.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)
        self.direction_frame.grid_columnconfigure(3, weight=1)

        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text=(
                "To log individual performances, "
                "navigate to the in-game player performance screen:"
            ),
            font=self.fonts["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.register_wrapping_widget(self.direction_label, width_ratio=0.3)

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan Outfield Player",
            font=self.fonts["button"],
            command=lambda: self._on_next_outfield_player_button_press(),
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan Goalkeeper",
            font=self.fonts["button"],
            command=lambda: self._on_next_goalkeeper_button_press(),
        )
        self.next_goalkeeper_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="Save Match Only",
            font=self.fonts["button"],
            command=lambda: self._on_done_button_press(),
        )
        self.all_players_added_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")
        self.style_submit_button(self.all_players_added_button)

    def on_show(self) -> None:
        """Reset match overview fields whenever the frame becomes active.

        Clears warning dismissal state and restores default team placeholders so
        each visit starts from a known baseline.
        """
        self._dismissed_warnings.clear()
        # Reset team names
        self.home_team_name_var.set("Home Team")
        self.away_team_name_var.set("Away Team")

        self.apply_focus_flourishes(self)

    def _create_home_away_stat_row(
        self, row: int, stat_key: str, stat_label: str
    ) -> None:
        """Create one paired home/away input row for a statistic.

        Registers separate StringVar bindings for home and away values, then
        places entry widgets and a centered label into the stats grid.

        Args:
            row (int): Grid row index for this stat line.
            stat_key (str): Internal key used for payload mapping.
            stat_label (str): Human-readable label displayed in the grid.
        """
        home_stat_value = ctk.StringVar(value="")
        self.home_stats_vars[stat_key] = home_stat_value
        self.home_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=home_stat_value,
            width=80,
            font=self.fonts["body"],
        )
        self.home_stat_entry.grid(row=row, column=0, padx=5, pady=5)
        self.stat_label = ctk.CTkLabel(
            self.stats_grid, text=stat_label, font=self.fonts["body"]
        )
        self.stat_label.grid(row=row, column=2, padx=5, pady=5)
        away_stat_value = ctk.StringVar(value="")
        self.away_stats_vars[stat_key] = away_stat_value
        self.away_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=away_stat_value,
            width=80,
            font=self.fonts["body"],
        )
        self.away_stat_entry.grid(row=row, column=4, padx=5, pady=5)

    def get_ocr_mapping(self) -> dict[str, dict[str, ctk.StringVar]]:
        """Return nested OCR mapping expected by this frame's home/away model.

        The OCR payload for match overview data is keyed by team scope, so this
        override maps ``home_team`` and ``away_team`` prefixes to the matching
        StringVar dictionaries.

        Returns:
            dict[str, dict[str, ctk.StringVar]]: Prefix-to-variable mapping for
            OCR population.
        """
        return {"home_team": self.home_stats_vars, "away_team": self.away_stats_vars}

    def _on_next_outfield_player_button_press(self) -> None:
        """Stage overview data and navigate to outfield player capture flow.

        Runs match-overview validation/buffering and, on success, triggers
        controller OCR processing for outfield player stats before navigation.
        """
        if not self._collect_data():
            return
        try:
            self.controller.process_player_stats()
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerStatsFrame")
            )
        except Exception as e:
            logger.error(
                f"Error during transition to PlayerStatsFrame: {e}", exc_info=True
            )
            self.show_error(
                "Error Processing Data",
                (
                    "An error occurred while processing the next player's stats: "
                    f"\n{e!s}. \n\nPlease try again."
                ),
            )

    def _on_next_goalkeeper_button_press(self) -> None:
        """Stage overview data and navigate to goalkeeper capture flow.

        Runs match-overview validation/buffering and, on success, triggers
        controller OCR processing for goalkeeper stats before navigation.
        """
        if not self._collect_data():
            return
        try:
            self.controller.process_player_stats(is_goalkeeper=True)
            self.controller.show_frame(self.controller.get_frame_class("GKStatsFrame"))
        except Exception as e:
            logger.error(f"Error during transition to GKStatsFrame: {e}", exc_info=True)
            self.show_error(
                "Error Processing Data",
                (
                    "An error occurred while processing the goalkeeper's stats: "
                    f"\n{e!s}. \n\nPlease try again."
                ),
            )

    def _on_done_button_press(self) -> None:
        """Stage overview data and finalize full match persistence.

        Ensures the current overview payload is valid and buffered before
        delegating final match save and navigating to the confirmation screen.
        """
        if not self._collect_data():
            return
        try:
            self.controller.save_buffered_match()
            self.controller.show_frame(
                self.controller.get_frame_class("MatchAddedFrame")
            )
        except Exception as e:
            logger.error(f"Error during finalizing match addition: {e}", exc_info=True)
            self.show_error(
                "Error Saving Match",
                (
                    f"An error occurred while saving the match data: \n{e!s}. "
                    "\n\nPlease try again."
                ),
            )

    def _collect_data(self) -> bool:
        """Execute full match-overview validation and buffering pipeline.

        Verifies team identifiers, converts and aggregates form values, runs
        required-field checks, validates possession and tackle constraints,
        validates expected stat ceilings, and buffers the final overview
        payload when all checks pass.

        Returns:
            bool: True when overview data is successfully validated and
            buffered; False when any validation or persistence step fails.
        """
        # Ensure team names aren't the default placeholders
        if self.home_team_name_var.get().strip() in ["", "Home Team"]:
            self.show_warning(
                "Missing Home Team Name",
                "Please enter the home \nteam name before proceeding.",
            )
            return False
        if self.away_team_name_var.get().strip() in ["", "Away Team"]:
            self.show_warning(
                "Missing Away Team Name",
                "Please enter the away \nteam name before proceeding.",
            )
            return False

        self._collect_and_convert()

        if not self._general_validation():
            return False

        if not self._validate_possession():
            return False

        if not self.validate_pair_hard(
            self.ui_data["home_stats"],
            [
                ("tackles_won", "Home Tackles Won", "tackles", "Home Tackles"),
            ],
        ):
            return False
        if not self.validate_pair_hard(
            self.ui_data["away_stats"],
            [
                ("tackles_won", "Away Tackles Won", "tackles", "Away Tackles"),
            ],
        ):
            return False

        home_xg: int | float | None = self.ui_data["home_stats"].get("xg")
        if not self.validate_xg(home_xg):
            return False

        away_xg: int | float | None = self.ui_data["away_stats"].get("xg")
        if not self.validate_xg(away_xg):
            return False

        return self._buffer_data() if self._validate_maximum() else False

    def _collect_and_convert(self) -> None:
        """Collect form values and normalize them into the overview payload.

        Converts ``xg`` as float while other numeric fields are parsed as
        integers, then assembles ``self.ui_data`` in the schema-compatible
        structure expected by downstream validation and buffering helpers.
        """

        # Helper to convert stat based on key (xG is float, others are int)
        def convert_stat(key: str, value: str) -> int | float | None:
            if key == "xg":
                return safe_float_conversion(value)
            return safe_int_conversion(value)

        # Collect match overview with type conversion
        self.ui_data: dict[
            str, str | int | float | dict[str, int | float | None] | None
        ] = {
            "home_team_name": self.home_team_name_var.get().strip() or None,
            "away_team_name": self.away_team_name_var.get().strip() or None,
            "home_score": safe_int_conversion(self.home_team_score_var.get()),
            "away_score": safe_int_conversion(self.away_team_score_var.get()),
            "home_stats": {
                k: convert_stat(k, v.get()) for k, v in self.home_stats_vars.items()
            },
            "away_stats": {
                k: convert_stat(k, v.get()) for k, v in self.away_stats_vars.items()
            },
        }

    def _general_validation(self) -> bool:
        """Validate required match overview fields across teams and stat groups.

        Flattens top-level and nested home/away stats into a single validation
        dictionary so shared missing-field checks can produce consistent user
        feedback.

        Returns:
            bool: True when all required fields are present; False otherwise.
        """
        validation_dict: dict[str, str | float | int | None] = {
            "Home Team Name": self.ui_data["home_team_name"],
            "Away Team Name": self.ui_data["away_team_name"],
            "Home Score": self.ui_data["home_score"],
            "Away Score": self.ui_data["away_score"],
        }

        key_to_label: dict[str, str] = dict(self.stat_definitions)
        for k, v in self.ui_data["home_stats"].items():
            validation_dict[f"Home {key_to_label.get(k, k)}"] = v
        for k, v in self.ui_data["away_stats"].items():
            validation_dict[f"Away {key_to_label.get(k, k)}"] = v

        if not self.check_missing_fields(
            validation_dict, {k: k for k in validation_dict}
        ):
            self.show_warning(
                "Missing Fields",
                "Please fill in all required fields before proceeding.",
            )
            return False
        return True

    def _validate_possession(self) -> bool:
        """Validate possession bounds and soft-check combined possession totals.

        Ensures each possession value is within 0-100, then performs a
        confirmation-gated soft validation when the combined possession exceeds
        100 percent.

        Returns:
            bool: True when possession checks pass or are user-confirmed;
            False when validation fails.
        """
        percentage_data: dict[str, int | float | None] = {
            "Home Possession": self.ui_data["home_stats"]["possession"],
            "Away Possession": self.ui_data["away_stats"]["possession"],
        }
        percentage_defs: list[tuple[str, str]] = [
            ("Home Possession", "Home Possession (%)"),
            ("Away Possession", "Away Possession (%)"),
        ]
        if not self.validate_attr_range(
            percentage_data, percentage_defs, min_val=0, max_val=100
        ):
            return False

        home_poss: int | float | None = self.ui_data["home_stats"]["possession"]
        away_poss: int | float | None = self.ui_data["away_stats"]["possession"]
        return not (
            (
                home_poss is not None
                and away_poss is not None
                and home_poss + away_poss > 100
            )
            and not self.soft_validate(
                "possession_sum",
                home_poss + away_poss,
                "Possession Total Exceeds 100%",
                f"Home possession ({home_poss}%) and Away possession "
                f"({away_poss}%) total {home_poss + away_poss}%, which exceeds 100%. "
                "Are you sure?",
            )
        )

    def _validate_maximum(self) -> bool:
        """Validate upper bounds for selected high-variance match statistics.

        Applies per-stat maximum thresholds to guard against OCR artifacts and
        obvious outlier values before buffer persistence.

        Returns:
            bool: True when all capped stat checks pass; False otherwise.
        """
        # Yellow cards are schema-bounded and should always be hard-validated.
        yellow_card_data: dict[str, int | float | None] = {
            "Home Yellow Cards": self.ui_data["home_stats"]["yellow_cards"],
            "Away Yellow Cards": self.ui_data["away_stats"]["yellow_cards"],
        }
        yellow_card_defs: list[tuple[str, str]] = [
            ("Home Yellow Cards", "Home Yellow Cards"),
            ("Away Yellow Cards", "Away Yellow Cards"),
        ]
        if not self.validate_attr_range(
            yellow_card_data,
            yellow_card_defs,
            min_val=MATCH_YELLOW_CARDS_MIN,
            max_val=MATCH_YELLOW_CARDS_MAX,
        ):
            return False

        stat_max_rules: list[tuple[str, str, int]] = [
            ("ball_recovery", "Ball Recovery Time", 50),
            ("shots", "Shots", 50),
            ("passes", "Passes", 1000),
            ("tackles", "Tackles", 100),
            ("interceptions", "Interceptions", 100),
            ("saves", "Saves", 50),
            ("fouls_committed", "Fouls Committed", 100),
            ("offsides", "Offsides", 50),
            ("corners", "Corners", 50),
            ("free_kicks", "Free Kicks", 100),
            ("penalty_kicks", "Penalty Kicks", 20),
        ]
        return all(
            self.validate_stat_max(self.ui_data, stat_key, stat_label, max_val)
            for stat_key, stat_label, max_val in stat_max_rules
        )

    def _buffer_data(self) -> bool:
        """Persist validated match overview data into the controller buffer.

        Delegates buffering to the controller and surfaces success or error
        feedback to the user.

        Returns:
            bool: True when buffering succeeds; False when an exception occurs.
        """
        # Buffer match overview. The controller merges this payload with
        # previously staged context (e.g., in_game_date and competition).
        logger.info("Match overview validation passed. Buffering data.")
        try:
            self.controller.buffer_match_overview(self.ui_data)
            logger.debug("Match overview buffered successfully.")
            self.show_success(
                "Data Saved",
                "Match overview data Saved successfully! Proceed to add player stats.",
            )
            return True
        except Exception as e:
            logger.error(f"Error buffering match overview: {e}")
            self.show_error(
                "Error Saving Data",
                (
                    f"An error occurred while saving the match overview data: \n{e!s}. "
                    "\n\nPlease try again."
                ),
            )
            return False
