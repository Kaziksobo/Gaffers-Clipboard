"""Match review view.

Provides the MatchReviewFrame CTk frame used to surface and resolve
discrepancies between team-level match overview data and individual
player performance records. The frame renders a scrollable comparison
grid of team totals and per-player editable entries, validates user
corrections, and delegates re-validation and save operations to a
controller implementing `MatchReviewControllerProtocol`.

Exports:
- MatchReviewFrame: UI for reviewing and correcting OCR-derived match data.

Dependencies: `customtkinter`, controller protocols from `src.contracts`,
and `DataDiscrepancyError` from `src.exceptions`.
"""

import logging
from typing import cast

import customtkinter as ctk

from src.contracts.backend import MatchOverviewPayload, PlayerPerformancePayload
from src.contracts.ui import BaseViewThemeProtocol, MatchReviewControllerProtocol
from src.exceptions import DataDiscrepancyError, PlayerNotFoundInBufferError
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin

logger = logging.getLogger(__name__)


class MatchReviewFrame(BaseViewFrame, EntryFocusMixin):
    """Review discrepancies between team-level data and player performances.

    If discrepancies exist, shows the team-level data alongside that data point
    in all player entries, allowing the user to identify and correct OCR errors
    before saving. Users are prompted to review all players if discrepancies
    exist, but can bypass the review if they choose to trust the OCR data as-is.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: MatchReviewControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Initialize the match-discrepancy review interface and state.

        Wires the frame into the controller, prepares per-stat tracking
        structures for team and player values, and builds the base layout used
        to display discrepancy rows and review actions.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (MatchReviewControllerProtocol): Controller responsible
                for supplying discrepancy data and handling re-validation and
                save operations.
            theme (BaseViewThemeProtocol): Theme tokens used for styling this
                review frame.
        """
        super().__init__(parent, controller, theme)

        logger.info("Initializing MatchReviewFrame")

        # State tracking for the dynamically generated variables
        self.team_vars: dict[str, ctk.StringVar] = {}
        # Structure: { "stat_name": { player_index: ("Player Name", StringVar) } }
        self.player_vars: dict[str, dict[int, tuple[str, ctk.StringVar]]] = {}

        self.stat_definitions: list[tuple[str, str]] = [
            ("goals", "Goals"),
            ("shots", "Shots"),
            ("passes", "Passes"),
            ("tackles", "Tackles"),
            ("offsides", "Offsides"),
            ("fouls_committed", "Fouls Committed"),
        ]

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct and arrange widgets for the match discrepancy review view.

        Builds headings, the scrollable discrepancy grid, and action buttons so
        users can inspect mismatched team/player stats, adjust values, and
        either cancel review or re-validate and save the match.
        """
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(6):
            self.grid_rowconfigure(i, weight=1 if i in [0, 5] else 0)

        self.main_heading = ctk.CTkLabel(
            self, text="Match Review", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))

        self.sub_heading = ctk.CTkLabel(
            self,
            text=(
                "Review discrepancies between team-level data and player performances."
            ),
            font=self.fonts["body"],
        )
        self.sub_heading.grid(row=2, column=1, pady=(0, 30))

        self.discrepancy_frame = ctk.CTkFrame(self)
        self.discrepancy_frame.grid(row=3, column=1, pady=(0, 30), sticky="nsew")
        self.discrepancy_frame.grid_rowconfigure(0, weight=1)
        self.discrepancy_frame.grid_columnconfigure(0, weight=1)
        self.discrepancy_frame.grid_columnconfigure(1, weight=0)
        self.discrepancy_frame.grid_columnconfigure(2, weight=1)

        self.discrepancy_grid = ctk.CTkFrame(
            self.discrepancy_frame, fg_color="transparent"
        )
        self.discrepancy_grid.grid(row=0, column=1, sticky="nsew")

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=4, column=1, pady=(0, 30), sticky="nsew")
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=0)
        self.button_frame.grid_columnconfigure(2, weight=0)
        self.button_frame.grid_columnconfigure(3, weight=0)
        self.button_frame.grid_columnconfigure(4, weight=1)
        self.button_frame.grid_rowconfigure(0, weight=1)

        self.cancel_exit_button = ctk.CTkButton(
            self.button_frame,
            text="Cancel Review and Exit",
            font=self.fonts["button"],
            command=self._on_cancel_exit_review,
        )
        self.cancel_exit_button.grid(row=0, column=1, padx=(0, 10))

        self.cancel_save_button = ctk.CTkButton(
            self.button_frame,
            text="Cancel Review and Force save",
            font=self.fonts["button"],
            command=self._on_cancel_save_review,
        )
        self.cancel_save_button.grid(row=0, column=2, padx=(10, 10))

        self.submit_button = ctk.CTkButton(
            self.button_frame,
            text="Re-Validate & Save",
            font=self.fonts["button"],
            command=self._on_submit_review,
        )
        self.submit_button.grid(row=0, column=3, padx=(10, 0))

    def on_show(self) -> None:
        """Refresh discrepancy context whenever the frame becomes visible.

        Retrieves the latest match overview, player performances, and
        discrepancy set from the controller, then rebuilds the review grid so
        users always act on up-to-date data.
        """
        match_overview, player_performances, discrepancies = (
            self.controller.get_match_review_context()
        )
        self.populate_review_grid(match_overview, player_performances, discrepancies)

    def populate_review_grid(
        self,
        overview_data: MatchOverviewPayload,
        performances_data: list[PlayerPerformancePayload],
        discrepancies: dict[str, dict[str, int | float]],
    ) -> None:
        """Populate the discrepancy grid with team and player stat comparisons.

        Clears any existing rows, rebuilds the grid for each discrepant stat,
        and wires editable entries so users can adjust team totals and per-
        player values prior to re-validation.

        Args:
            overview_data (MatchOverviewPayload): Current team-level overview
                values used as the authoritative baseline.
            performances_data (list[PlayerPerformancePayload]): Collection of
                player performance records contributing to each stat.
            discrepancies (dict[str, dict[str, int | float]]): Mapping of stat
                keys to discrepancy details that should be surfaced for review.
        """
        # Clear existing widgets if re-populated
        for widget in self.discrepancy_grid.winfo_children():
            widget.destroy()

        self.team_vars.clear()
        self.player_vars.clear()

        outfield_performances: list[PlayerPerformancePayload] = [
            performance
            for performance in performances_data
            if performance.get("performance_type") == "Outfield"
        ]

        max_columns = 4
        stat_columns = min(max_columns, max(1, len(discrepancies)))
        for col in range(max_columns):
            weight = 1 if col < stat_columns else 0
            self.discrepancy_grid.grid_columnconfigure(col, weight=weight)

        for stat_index, stat in enumerate(discrepancies):
            stat_row = stat_index // stat_columns
            stat_col = stat_index % stat_columns
            display_name: str = next(
                (name for key, name in self.stat_definitions if key == stat),
                stat.replace("_", " ").title(),
            )

            stat_frame = ctk.CTkFrame(self.discrepancy_grid)
            stat_frame.grid(row=stat_row, column=stat_col, padx=20, pady=10, sticky="n")
            stat_frame.grid_columnconfigure(0, weight=1)
            stat_frame.grid_columnconfigure(1, weight=0)

            row_idx = 0

            stat_label = ctk.CTkLabel(
                stat_frame,
                text=display_name,
                font=self.fonts["body"],
            )
            stat_label.grid(
                row=row_idx, column=0, columnspan=2, pady=(0, 5), sticky="w"
            )
            row_idx += 1

            team_label = ctk.CTkLabel(
                stat_frame, text="Team Total:", font=self.fonts["body"]
            )
            team_label.grid(row=row_idx, column=0, padx=(10, 20), pady=2, sticky="w")

            expected_total = discrepancies.get(stat, {}).get("expected")
            team_val = str(
                expected_total
                if expected_total is not None
                else overview_data.get(stat, 0)
            )
            team_var = ctk.StringVar(value=team_val)
            self.team_vars[stat] = team_var
            team_entry = ctk.CTkEntry(
                stat_frame,
                textvariable=team_var,
                width=60,
                font=self.fonts["body"],
            )
            team_entry.grid(row=row_idx, column=1, pady=2, sticky="w")
            row_idx += 1

            self.player_vars[stat] = {}
            for p_idx, performance in enumerate(outfield_performances):
                player_name: str = performance.get("player_name", f"Player {p_idx + 1}")
                player_val = str(performance.get(stat, 0))

                player_label = ctk.CTkLabel(
                    stat_frame,
                    text=f"  ↳ {player_name}:",
                    font=self.fonts["body"],
                )
                player_label.grid(
                    row=row_idx, column=0, padx=(20, 20), pady=2, sticky="w"
                )

                p_var = ctk.StringVar(value=player_val)
                self.player_vars[stat][p_idx] = (player_name, p_var)

                player_entry = ctk.CTkEntry(
                    stat_frame,
                    textvariable=p_var,
                    width=60,
                    font=self.fonts["body"],
                )
                player_entry.grid(row=row_idx, column=1, pady=2, sticky="w")
                row_idx += 1

        self.apply_focus_flourishes(self.discrepancy_grid)

    def _on_submit_review(self) -> None:
        try:
            updated_overview, updated_performances, stat_keys = (
                self._collect_updated_review_values()
            )
        except ValueError:
            self.show_error(
                "Invalid Input",
                (
                    "All corrected stats must be valid whole numbers. "
                    "Please check your inputs and remove any letters or symbols."
                ),
            )
            return

        if errs := self._validate_discrepancy_inputs(
            updated_overview, updated_performances, stat_keys
        ):
            self.show_error("Invalid Input", "\n".join(errs))
            return

        try:
            self._submit_manual_corrections(updated_overview, updated_performances)

        except PlayerNotFoundInBufferError as e:
            logger.warning("Player not found when applying corrections: %s", e)
            self.show_error(
                "Player Not Found",
                (
                    "One or more corrected player names could not be matched to the "
                    "current buffered players. Please verify "
                    "the player names and try again."
                ),
            )
            return

        except DataDiscrepancyError as e:
            logger.warning(
                "Manual corrections submitted, but discrepancies still exist."
            )
            self._handle_remaining_discrepancies(
                discrepancies=e.discrepancies,
                updated_performances=updated_performances,
            )

        except Exception as e:
            # Catch file IO errors or other unexpected crashes
            logger.error(
                f"Critical error during correction submission: {e}", exc_info=True
            )
            self.show_error("Save Failed", f"An unexpected error occurred: {e}")

    def _collect_updated_review_values(
        self,
    ) -> tuple[dict[str, int], dict[str, dict[str, int | float]], list[str]]:
        updated_overview: dict[str, int] = {
            stat: int(var.get().strip()) for stat, var in self.team_vars.items()
        }
        updated_performances: dict[str, dict[str, int | float]] = {}
        stat_keys = list(updated_overview.keys())

        for stat, players in self.player_vars.items():
            for _, (player_name, var) in players.items():
                if player_name not in updated_performances:
                    updated_performances[player_name] = {}
                updated_performances[player_name][stat] = int(var.get().strip())

        return updated_overview, updated_performances, stat_keys

    def _submit_manual_corrections(
        self,
        updated_overview: dict[str, int],
        updated_performances: dict[str, dict[str, int | float]],
    ) -> None:
        logger.info("Attempting to submit manual corrections...")
        self.controller.submit_match_corrections(updated_overview, updated_performances)
        self.controller.show_frame(self.controller.get_frame_class("MatchAddedFrame"))

    def _handle_remaining_discrepancies(
        self,
        discrepancies: dict[str, dict[str, int | float]],
        updated_performances: dict[str, dict[str, int | float]],
    ) -> None:
        if self.show_discrepancy_alert(discrepancies):
            try:
                self.controller.save_buffered_match(force_save=True)
                self.controller.show_frame(
                    self.controller.get_frame_class("MatchAddedFrame")
                )
            except Exception as e:
                logger.error(f"Critical error during forced save: {e}", exc_info=True)
                self.show_error("Save Failed", f"An unexpected error occurred: {e}")
            return

        self._repopulate_review_grid(
            discrepancies=discrepancies,
            updated_performances=updated_performances,
        )

    def _repopulate_review_grid(
        self,
        discrepancies: dict[str, dict[str, int | float]],
        updated_performances: dict[str, dict[str, int | float]],
    ) -> None:
        # Fetch latest buffered payloads so the review grid reflects
        # the controller's current, side-specific overview state.
        overview_payload, orig_performances, _ = (
            self.controller.get_match_review_context()
        )

        # Build lookup for outfield performances only.
        orig_by_name: dict[str, PlayerPerformancePayload] = {}
        for performance in orig_performances:
            if performance.get("performance_type") != "Outfield":
                continue
            name = performance.get("player_name")
            if isinstance(name, str) and name.strip():
                orig_by_name[name] = performance

        performances_payloads: list[PlayerPerformancePayload] = []
        for player_name, stats in updated_performances.items():
            player_name = str(player_name).strip()
            if not player_name:
                logger.error("Empty player name found in corrections.")
                self.show_error(
                    "Invalid Player Name",
                    (
                        "Player names cannot be empty. "
                        "Please verify all player names and try again."
                    ),
                )
                return

            base = orig_by_name.get(player_name, {})
            if base:
                base = cast(PlayerPerformancePayload, base)
            else:
                # This should be rare since we validate player names on submit,
                # but if a name is truly missing, this is a breaking error
                # since we won't have a valid performance record to merge with.
                logger.error(
                    f"Player '{player_name}' not found in original performances."
                )
                self.show_error(
                    "Player Not Found",
                    (
                        f"Player '{player_name}' not found in original "
                        "performances. Please verify the player name "
                        "and try again."
                    ),
                )
                return

            perf_type: str = base.get("performance_type", "Outfield")
            # merge: keep player_name and performance_type,
            # overlay updated stats
            merged_dict = {
                "player_name": player_name,
                "performance_type": perf_type,
                **(base if isinstance(base, dict) else {}),
                **stats,
            }
            merged = cast(PlayerPerformancePayload, merged_dict)
            performances_payloads.append(merged)

        self.populate_review_grid(
            overview_data=overview_payload,
            performances_data=performances_payloads,
            discrepancies=discrepancies,
        )

    def _validate_discrepancy_inputs(
        self,
        updated_overview: dict[str, int],
        updated_performances: dict[str, dict[str, int | float]],
        stat_keys: list[str],
    ) -> list[str]:
        errors = []
        # overview validation
        for k in stat_keys:
            try:
                v = int(updated_overview.get(k, 0))
                if v < 0:
                    errors.append(f"Team {k} must be zero or positive.")
            except (TypeError, ValueError):
                errors.append(f"Team {k} must be a whole number.")
        # per-player validation
        for player, upd in updated_performances.items():
            for k in stat_keys:
                if k in upd:
                    try:
                        val = int(str(upd[k]).strip())
                        if val < 0:
                            errors.append(f"{player}: {k} must be >= 0.")
                    except (TypeError, ValueError):
                        errors.append(f"{player}: {k} must be a whole number.")
        return errors

    def _on_cancel_exit_review(self) -> None:
        self.controller.cancel_match_review()
        self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))

    def _on_cancel_save_review(self) -> None:
        self.controller.cancel_match_review()
        self.controller.save_buffered_match(force_save=True)
        self.controller.show_frame(self.controller.get_frame_class("MatchAddedFrame"))
