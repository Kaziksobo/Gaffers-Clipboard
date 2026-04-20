"""UI frame for reviewing and buffering goalkeeper match performance.

This module defines GKStatsFrame, a match-workflow view that captures
goalkeeper performance values, validates consistency and range rules, stages
buffered records, and coordinates OCR-driven transitions between player scans
or final match save.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, GKStatsFrameControllerProtocol
from src.exceptions import DataDiscrepancyError, DuplicateRecordError
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import (
    EntryFocusMixin,
    OCRDataMixin,
    PerformanceSidebarMixin,
    PlayerDropdownMixin,
)
from src.views.widgets.scrollable_dropdown import ScrollableDropdown
from src.views.widgets.scrollable_sidebar import ScrollableSidebar

logger = logging.getLogger(__name__)


class GKStatsFrame(
    BaseViewFrame,
    OCRDataMixin,
    PlayerDropdownMixin,
    PerformanceSidebarMixin,
    EntryFocusMixin,
):
    """Frame for entering and validating goalkeeper match statistics.

    The frame supports OCR-assisted review flows, manual correction of missing
    values, and staged buffering of per-player performance data before final
    match persistence.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: GKStatsFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the goalkeeper performance review interface.

        Creates the player selector, stats input grid, navigation controls for
        scanning additional players, and a buffered-performance sidebar.
        Widgets are wired to callbacks that validate, stage, and route match
        data through controller-managed OCR and save flows.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (GKStatsFrameControllerProtocol): The main
                application controller.
            theme (BaseViewThemeProtocol): The application's theme configuration.
        """
        super().__init__(parent, controller, theme)
        self.controller: GKStatsFrameControllerProtocol = controller

        logger.info("Initializing GKStatsFrame")

        self.stats_vars: dict[str, ctk.StringVar] = {}
        self.stat_definitions: list[tuple[str, str]] = [
            ("shots_against", "Shots Against"),
            ("shots_on_target", "Shots On Target"),
            ("saves", "Saves"),
            ("goals_conceded", "Goals Conceded"),
            ("save_success_rate", "Save Success Rate (%)"),
            ("punch_saves", "Punch Saves"),
            ("rush_saves", "Rush Saves"),
            ("penalty_saves", "Penalty Saves"),
            ("penalty_goals_conceded", "Penalty Goals Conceded"),
            ("shoot_out_saves", "Shoot-out Saves"),
            ("shoot_out_goals_conceded", "Shoot-out Goals Conceded"),
        ]

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self, text="Review Goalkeeper Stats", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))

        # Player dropdown (reusable scrollable dropdown)
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=self.theme,
            fonts=self.fonts,
            variable=self.player_list_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player",
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))

        # Info Label
        self.info_label = ctk.CTkLabel(
            self,
            text=(
                "Empty stats couldn't be recognised and require manual entry.\n "
                "Please review and update player attributes as necessary."
            ),
            font=self.fonts["body"],
        )
        self.info_label.grid(row=3, column=1, pady=(0, 20))
        self.register_wrapping_widget(self.info_label, width_ratio=0.8)

        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self)
        self.stats_grid.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        # Configure subgrid
        self.stats_grid.grid_columnconfigure(0, weight=1)
        self.stats_grid.grid_columnconfigure(1, weight=1)
        for row in range(len(self.stat_definitions)):
            self.stats_grid.grid_rowconfigure(row, weight=1)

        # Populate stats grid
        for i, (stat_key, stat_label) in enumerate(self.stat_definitions):
            self.create_data_row(
                parent_widget=self.stats_grid,
                index=i,
                stat_key=stat_key,
                stat_label=stat_label,
                target_dict=self.stats_vars,
                label_col=0,
                entry_col=1,
            )

        # Direction subgrid
        self.direction_frame = ctk.CTkFrame(self)
        self.direction_frame.grid(row=5, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)
        self.direction_frame.grid_columnconfigure(3, weight=1)
        self.direction_frame.grid_columnconfigure(4, weight=1)

        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text="To scan another player, navigate to their in-game stats:",
            font=self.fonts["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.register_wrapping_widget(self.direction_label, width_ratio=0.8)

        # Checkbox to control whether the current player's data should be saved
        self.skip_save_var = ctk.BooleanVar(value=False)
        self.skip_save_checkbox = ctk.CTkCheckBox(
            self.direction_frame,
            text="Skip saving current player",
            variable=self.skip_save_var,
        )
        self.skip_save_checkbox.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan an Outfield Player",
            font=self.fonts["button"],
            command=lambda: self._on_next_outfield_player_button_press(),
        )
        self.next_player_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan a Goalkeeper",
            font=self.fonts["button"],
            command=lambda: self._on_next_goalkeeper_button_press(),
        )
        self.next_goalkeeper_button.grid(row=0, column=3, padx=5, pady=5, sticky="e")

        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="Save all and Finish Match",
            font=self.fonts["button"],
            command=lambda: self._on_done_button_press(),
        )
        self.all_players_added_button.grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.style_submit_button(self.all_players_added_button)

        self.performance_sidebar = ScrollableSidebar(
            parent=self,
            theme=self.theme,
            fonts=self.fonts,
            display_keys=["player_name", "positions_played"],
            remove_button=True,
            remove_callback=self.remove_player_from_buffer,
            id_key="player_name",
            title="Buffered Players",
            responsive=True,
            state_callback=lambda collapsed: self.controller.set_sidebar_collapse_state(
                "performance_sidebar", collapsed
            ),
        )
        self.performance_sidebar.place(
            relx=1.0, rely=0.0, relwidth=0.25, relheight=0.4, anchor="ne", x=-10, y=10
        )
        self.performance_sidebar.store_place_geometry(
            relx=1.0, rely=0.0, relwidth=0.25, relheight=0.4, anchor="ne", x=-10, y=10
        )
        initial_state = self.controller.get_sidebar_collapse_state(
            "performance_sidebar"
        )
        self.performance_sidebar.set_collapse_state(initial_state)

        self.apply_focus_flourishes(self)

    def on_show(self) -> None:
        """Refresh frame state whenever the view is raised.

        Clears prior warning dismissals, refreshes goalkeeper dropdown options,
        restores sidebar collapse state from controller preferences, and
        repopulates the buffered-performance sidebar.
        """
        self._dismissed_warnings.clear()

        self.refresh_player_dropdown(only_gk=True, remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")
        # Ensure the sidebar visual state follows the controller's stored preference
        initial_state: bool = self.controller.get_sidebar_collapse_state(
            "performance_sidebar"
        )
        self.performance_sidebar.set_collapse_state(initial_state)
        self.refresh_performance_sidebar()
        self.skip_save_var.set(False)

    def _collect_data(self) -> bool:
        """Collect, validate, and buffer a single goalkeeper performance row.

        Resolves selected player identity, converts stat inputs to integers,
        validates required fields and percentage bounds, enforces hard and soft
        consistency checks, and applies per-stat maximum rules before adding
        metadata keys required by the performance buffer.

        Returns:
            bool: True when data is valid and buffered successfully; False when
            validation or buffering fails.
        """
        player_name: str | None = self.resolve_selected_player_name(
            self.player_list_var.get()
        )

        # Validate Player Name first
        if player_name is None:
            self.show_warning(
                title="No player selected",
                message="Please select a player from the dropdown before proceeding.",
            )
            return False

        # Convert all stats to integers
        ui_data: dict[str, int | str | None] = {
            stat_key: safe_int_conversion(var.get())
            for stat_key, var in self.stats_vars.items()
        }

        if not self.check_missing_fields(ui_data, dict(self.stat_definitions)):
            return False

        percentage_keys: set[str] = {"save_success_rate"}
        percentage_data: dict[str, int | str | None] = {
            k: v for k, v in ui_data.items() if k in percentage_keys
        }
        percentage_defs: list[tuple[str, str]] = [
            (k, label) for k, label in self.stat_definitions if k in percentage_keys
        ]
        if not self.validate_attr_range(
            percentage_data, percentage_defs, min_val=0, max_val=100
        ):
            return False

        saves: int | None = int(ui_data.get("saves") or 0)
        shots_on_target: int | None = int(ui_data.get("shots_on_target") or 0)
        if not self.validate_pair_hard(
            ui_data,
            [
                ("saves", "Saves", "shots_on_target", "Shots On Target"),
            ],
        ):
            return False

        goals_conceded: int | None = int(ui_data.get("goals_conceded") or 0)
        if (
            saves is not None
            and goals_conceded is not None
            and saves + goals_conceded > shots_on_target
        ) and not self.soft_validate(
            "saves_plus_goals_vs_shots",
            (saves, goals_conceded, shots_on_target),
            "Data Inconsistency",
            (
                f"The combined total of saves ({saves}) and goals conceded "
                f"({goals_conceded}) exceeds the number of shots on target "
                f"({shots_on_target}). Please double-check these values."
            ),
        ):
            return False
        if (
            goals_conceded is not None
            and shots_on_target is not None
            and goals_conceded > shots_on_target
        ) and not self.soft_validate(
            "goals_conceded_vs_shots",
            (goals_conceded, shots_on_target),
            "Data Inconsistency",
            (
                f"The number of goals conceded ({goals_conceded}) "
                f"exceeds the number of shots on target ({shots_on_target}). "
                "Please double-check these values."
            ),
        ):
            return False

        stat_max_rules: list[tuple[str, str, int]] = [
            ("shots_against", "Shots Against", 25),
            ("shots_on_target", "Shots On Target", 25),
            ("saves", "Saves", 25),
            ("goals_conceded", "Goals Conceded", 10),
            ("punch_saves", "Punch Saves", 15),
            ("rush_saves", "Rush Saves", 15),
            ("penalty_saves", "Penalty Saves", 5),
            ("penalty_goals_conceded", "Penalty Goals Conceded", 5),
            ("shoot_out_saves", "Shoot-out Saves", 5),
            ("shoot_out_goals_conceded", "Shoot-out Goals Conceded", 5),
        ]
        for stat_key, stat_label, max_val in stat_max_rules:
            if not self.validate_stat_max(ui_data, stat_key, stat_label, max_val):
                return False

        ui_data["player_name"] = player_name
        ui_data["performance_type"] = "GK"

        return self._buffer_player_performance(ui_data, player_name)

    def _buffer_player_performance(
        self, ui_data: dict[str, int | str | None], player_name: str
    ) -> bool:
        """Send validated goalkeeper performance data to the controller buffer.

        Handles duplicate-record protection and generic persistence failures by
        surfacing user-facing dialogs while logging detailed diagnostic context.

        Args:
            ui_data (dict[str, int | str | None]): Validated performance payload
                for the selected player.
            player_name (str): Display name used for status and error messages.

        Returns:
            bool: True when buffering succeeds; False on duplicate or error.
        """
        logger.info(f"Validation passed for {player_name}. Buffering performance data.")
        try:
            self.controller.buffer_player_performance(ui_data)
            logger.debug(f"Buffered data for {player_name}")
            self.show_success(
                "Data Saved",
                f"Performance data for {player_name} has been saved successfully.",
            )
            return True
        except DuplicateRecordError as e:
            logger.error(
                f"Duplicate record error while buffering data for {player_name}: {e}",
                exc_info=True,
            )
            self.show_error(
                "Duplicate Record",
                (
                    f"Performance data for {player_name} has already been buffered. "
                    "Each player's performance can only be added once per match."
                ),
            )
            return False
        except Exception as e:
            logger.error(f"Error buffering player performance data: {e}", exc_info=True)
            self.show_error(
                "Error Saving Data",
                (
                    f"An error occurred while saving the performance data: \n{e!s}. "
                    "\n\nPlease try again."
                ),
            )
            return False

    def _on_next_outfield_player_button_press(self) -> None:
        """Stage current data and transition to outfield-player OCR flow.

        Unless skip-save is enabled, this action validates and buffers current
        goalkeeper stats first, then triggers controller OCR processing for the
        next outfield player and navigates to the corresponding stats frame.
        """
        if not self.collect_data_unless_skipped():
            return
        try:
            # Trigger the controller OCR logic for the next player
            self.controller.process_player_stats(is_goalkeeper=False)
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerStatsFrame")
            )
        except Exception as e:
            logger.error(
                f"Failed to process next outfield player stats: {e}", exc_info=True
            )
            self.show_error(
                "Error Processing Data",
                (
                    "An error occurred while processing the next player's stats: "
                    f"\n{e!s}. \n\nPlease try again."
                ),
            )
            return

    def _on_next_goalkeeper_button_press(self) -> None:
        """Stage current data and transition to next-goalkeeper OCR flow.

        Unless skip-save is enabled, this action validates and buffers current
        stats first, then triggers OCR for the next goalkeeper and reloads the
        goalkeeper stats frame for continued entry.
        """
        if not self.collect_data_unless_skipped():
            return
        try:
            # Trigger the controller OCR logic for the goalkeeper
            self.controller.process_player_stats(is_goalkeeper=True)
            self.controller.show_frame(self.controller.get_frame_class("GKStatsFrame"))
        except Exception as e:
            logger.error(f"Failed to process next goalkeeper stats: {e}", exc_info=True)
            self.show_error(
                "Error Processing Data",
                (
                    "An error occurred while processing the next goalkeeper's stats: "
                    f"\n{e!s}. \n\nPlease try again."
                ),
            )
            return

    def _on_done_button_press(self) -> None:
        """Stage current stats and finalize full match persistence.

        Unless skip-save is enabled, this action validates and buffers the
        active goalkeeper entry before delegating final buffered match save to
        the controller and navigating to the match-added confirmation frame.
        """
        if not self.collect_data_unless_skipped():
            return
        try:
            logger.info("Initiating final match save from GKStatsFrame.")
            self.controller.save_buffered_match()
            self.controller.show_frame(
                self.controller.get_frame_class("MatchAddedFrame")
            )
        except DataDiscrepancyError as e:
            logger.warning("Match discrepancy detected: %s", e.discrepancies)
            if not self.confirm_discrepancy_force_save(e.discrepancies):
                return
            try:
                self.controller.save_buffered_match(force_save=True)
                self.controller.show_frame(
                    self.controller.get_frame_class("MatchAddedFrame")
                )
            except Exception as forced_save_error:
                logger.error(
                    "Error while force-saving match from GKStatsFrame: %s",
                    forced_save_error,
                    exc_info=True,
                )
                self.show_error(
                    "Error Saving Match",
                    (
                        "An error occurred while force-saving the match data: "
                        f"{forced_save_error!s}. Please try again."
                    ),
                )
        except Exception as e:
            # Crucial catch for DataPersistenceError to prevent data loss via hard-crash
            logger.error(
                f"Failed to save the match to persistent storage: {e}", exc_info=True
            )
            self.show_error(
                "Error Saving Match",
                (
                    f"An error occurred while saving the match data: {e!s}. "
                    "Please try again."
                ),
            )
            return

    def collect_data_unless_skipped(self) -> bool:
        """Collect and buffer current player unless skip-save is enabled.

        Returns:
            bool: True when processing can continue; False when validation or
                buffering fails.
        """
        skip_var = getattr(self, "skip_save_var", None)
        if skip_var is not None and bool(skip_var.get()):
            logger.info("Skipping save for current goalkeeper by user request.")
            # Treat skip as a one-shot action for the currently reviewed player.
            skip_var.set(False)
            return True

        return self._collect_data()
