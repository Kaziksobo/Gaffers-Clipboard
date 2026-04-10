"""UI frame for reviewing and buffering outfield player match statistics.

This module defines PlayerStatsFrame, the outfield performance review screen
where OCR-captured values are verified, corrected, buffered, and finally
persisted as part of the match-save workflow.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, PlayerStatsFrameControllerProtocol
from src.exceptions import DuplicateRecordError
from src.utils import safe_float_conversion, safe_int_conversion
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

# Valid positions that match PositionType from custom_types
VALID_POSITIONS = {
    "GK",
    "LB",
    "RB",
    "CB",
    "LWB",
    "RWB",
    "CDM",
    "CM",
    "CAM",
    "LM",
    "RM",
    "LW",
    "RW",
    "ST",
    "CF",
}


class PlayerStatsFrame(
    BaseViewFrame,
    PlayerDropdownMixin,
    OCRDataMixin,
    PerformanceSidebarMixin,
    EntryFocusMixin,
):
    """Collect, validate, and buffer outfield player performance entries.

    The frame presents OCR-populated statistics for manual review, applies
    domain validation rules, and coordinates repeated scan-and-save actions
    until the match payload is complete.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: PlayerStatsFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the outfield player performance interface.

        Creates player-selection controls, editable stat fields, OCR flow
        actions, and a sidebar for buffered performances. The layout is
        optimized for repeated player capture during match entry.

        Args:
            parent (ctk.CTkFrame): Parent container widget hosting this frame.
            controller (PlayerStatsFrameControllerProtocol):
                Controller that provides OCR processing, buffering, and
                navigation services.
            theme (BaseViewThemeProtocol): Theme tokens used for frame styling
                and typography.
        """
        super().__init__(parent, controller, theme)
        self.controller: PlayerStatsFrameControllerProtocol = controller

        logger.info("Initializing PlayerStatsFrame")

        # Attributes to store stat variables
        self.stats_vars: dict[str, ctk.StringVar] = {}

        self.stat_definitions: list[tuple[str, str]] = [
            ("goals", "Goals"),
            ("assists", "Assists"),
            ("shots", "Shots"),
            ("shot_accuracy", "Shot Accuracy (%)"),
            ("passes", "Passes"),
            ("pass_accuracy", "Pass Accuracy (%)"),
            ("dribbles", "Dribbles"),
            ("dribble_success_rate", "Dribbles Success Rate (%)"),
            ("tackles", "Tackles"),
            ("tackle_success_rate", "Tackles Success Rate (%)"),
            ("offsides", "Offsides"),
            ("fouls_committed", "Fouls Committed"),
            ("possession_won", "Possession Won"),
            ("possession_lost", "Possession Lost"),
            ("minutes_played", "Minutes Played"),
            ("distance_covered", "Distance Covered (km)"),
            ("distance_sprinted", "Distance Sprinted (km)"),
        ]

        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Title
        self.grid_rowconfigure(2, weight=0)  # Player dropdown
        self.grid_rowconfigure(3, weight=0)  # Position select
        self.grid_rowconfigure(4, weight=0)  # Info label
        self.grid_rowconfigure(5, weight=1)  # Stats grid
        self.grid_rowconfigure(6, weight=0)  # Direction subgrid
        self.grid_rowconfigure(7, weight=1)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self, text="Review Outfield Player Stats", font=self.fonts["title"]
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
            command=self._on_player_selected,
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))

        # Position select
        self.position_frame = ctk.CTkFrame(self)
        self.position_frame.grid(row=3, column=1, padx=20, pady=(0, 20), sticky="nsew")
        self.position_frame.grid_columnconfigure(0, weight=1)
        self.position_frame.grid_columnconfigure(1, weight=0)
        self.position_frame.grid_columnconfigure(2, weight=0)
        self.position_frame.grid_columnconfigure(3, weight=1)
        self.position_frame.grid_rowconfigure(0, weight=1)
        self.position_label = ctk.CTkLabel(
            self.position_frame,
            text="Position(s) played:",
            font=self.fonts["body"],
        )
        self.position_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.position_entry = ctk.CTkEntry(
            self.position_frame, placeholder_text="e.g. RW, LW", font=self.fonts["body"]
        )
        self.position_entry.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        # Info Label
        self.info_label = ctk.CTkLabel(
            self,
            text=(
                "Please review the captured player performance data."
                "\nFill in any missing fields and correct any inaccuracies."
            ),
            font=self.fonts["body"],
        )
        self.info_label.grid(row=4, column=1, pady=(0, 20))
        self.register_wrapping_widget(self.info_label, width_ratio=0.8)

        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self)
        self.stats_grid.grid(row=5, column=1, pady=(0, 20), sticky="nsew", padx=20)
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
        self.direction_frame.grid(row=6, column=1, pady=(0, 20), sticky="nsew")
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
        self.register_wrapping_widget(self.direction_label, width_ratio=0.3)

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan an Outfield Player",
            font=self.fonts["button"],
            command=lambda: self._on_next_outfield_player_button_press(),
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.next_goalkeeper_button = ctk.CTkButton(
            self.direction_frame,
            text="Scan a Goalkeeper",
            font=self.fonts["button"],
            command=lambda: self._on_next_goalkeeper_button_press(),
        )
        self.next_goalkeeper_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        # Checkbox to control whether the current player's data should be saved
        self.skip_save_var = ctk.BooleanVar(value=False)
        self.skip_save_checkbox = ctk.CTkCheckBox(
            self.direction_frame,
            text="Skip saving current player",
            variable=self.skip_save_var,
        )
        self.skip_save_checkbox.grid(row=0, column=3, padx=5, pady=5, sticky="e")

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
        """Reset frame state and refresh dynamic UI data on activation.

        This lifecycle hook clears warning state, refreshes available players,
        restores sidebar collapse preference, repaints buffered performance
        items, and resets position input guidance.
        """
        self._dismissed_warnings.clear()
        self.refresh_player_dropdown(only_outfield=True, remove_on_loan=True)
        self.player_dropdown.set_value("Click here to select player")
        # Ensure the sidebar visual state follows the controller's stored preference
        initial_state = self.controller.get_sidebar_collapse_state(
            "performance_sidebar"
        )
        self.performance_sidebar.set_collapse_state(initial_state)
        self.refresh_performance_sidebar()

        self.position_entry.delete(0, "end")
        self.position_entry.configure(placeholder_text="e.g. RW, LW")

    def _on_player_selected(self, name: str) -> None:
        """Auto-fill position input from the selected player's bio data.

        If the selected player has known positions and the position field is
        still empty, the most recent position value is inserted to reduce
        repetitive typing.

        Args:
            name (str): Selected player display name from the dropdown.
        """
        bio = self.controller.get_player_bio(name)
        if bio is None:
            return

        positions = bio.get("positions", []) or []
        if not positions:
            return

        # Only auto-fill the position entry if the user hasn't typed anything yet
        try:
            current_value = self.position_entry.get().strip()
        except Exception:
            current_value = ""

        if not current_value:
            self.position_entry.delete(0, "end")
            self.position_entry.insert(0, positions[-1])

    def _on_next_outfield_player_button_press(self) -> None:
        """Save current data, OCR-scan the next outfield player, and reload.

        Unless the skip-save option is enabled, the current player's stats are
        validated and buffered before triggering OCR for the next outfield
        profile and returning to this frame with refreshed data.
        """
        # If the user has enabled skipping, bypass validation and buffering
        if (
            not getattr(self, "skip_save_var", None) or not self.skip_save_var.get()
        ) and not self._collect_data():
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
                    f"An error occurred while processing the next player's stats: "
                    f"\n{e!s}. \n\nPlease try again."
                ),
            )
            return

    def _on_next_goalkeeper_button_press(self) -> None:
        """Save current data, OCR-scan the goalkeeper, and switch frame.

        Unless skip-save is enabled, current outfield stats are validated and
        buffered before OCR is run for goalkeeper statistics and navigation
        continues to the goalkeeper review frame.
        """
        # If the user has enabled skipping, bypass validation and buffering
        if (
            not getattr(self, "skip_save_var", None) or not self.skip_save_var.get()
        ) and not self._collect_data():
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
                    "An error occurred while processing the next "
                    f"goalkeeper's stats: \n{e!s}. \n\nPlease try again."
                ),
            )
            return

    def _on_skip_player_button_press(self) -> None:
        """Provide a placeholder hook for an explicit skip-player action.

        The frame currently uses the skip-save checkbox to bypass validation
        and buffering, so this callback remains intentionally empty.
        """
        pass

    def _on_done_button_press(self) -> None:
        """Validate final data and persist the buffered match payload.

        Collects and buffers the current player's stats, then instructs the
        controller to save all buffered match records and route to the
        confirmation frame.
        """
        if not self._collect_data():
            return
        try:
            logger.info("Initiating final match save from GKStatsFrame.")
            self.controller.save_buffered_match()
            self.controller.show_frame(
                self.controller.get_frame_class("MatchAddedFrame")
            )
        except Exception as e:
            # Crucial catch for DataPersistenceError to prevent data loss via hard-crash
            logger.error(
                f"Failed to save the match to persistent storage: {e}", exc_info=True
            )
            self.show_error(
                "Error Saving Match",
                (
                    "An error occurred while saving the match data: "
                    f"{e!s}. Please try again."
                ),
            )
            return

    def _collect_data(self) -> bool:
        """Collect, validate, and buffer outfield player performance input.

        This method assembles field values from the UI, applies conversion and
        domain validation rules, enriches the payload with player identity and
        performance metadata, then buffers the result through the controller.

        Returns:
            bool: True when the current player data is buffered successfully;
                otherwise False.
        """
        player_name: str | None = self.resolve_selected_player_name(
            self.player_list_var.get()
        )

        # Validate Player Name first
        if player_name is None:
            self.show_warning(
                "Validation Error",
                "Please select a valid player from the dropdown before proceeding.",
            )
            return False

        self.ui_data: dict[str, int | float | str | list[str] | None] = {}
        float_keys: set[str] = {"distance_covered", "distance_sprinted"}

        # Collect and convert stats
        self._collect_and_convert(float_keys)

        if not self.check_missing_fields(self.ui_data, dict(self.stat_definitions)):
            return False

        if not self._validate_percentage_stats():
            return False

        minutes_value = self.ui_data.get("minutes_played") or 0
        if isinstance(minutes_value, (int, float)):
            minutes_int = int(minutes_value)
        else:
            minutes_int = int(minutes_value) if isinstance(minutes_value, str) else 0
        if not self.validate_minutes_played(minutes_int):
            return False

        if not self._validate_pairs():
            return False

        if not self._validate_maximums():
            return False

        self.ui_data["player_name"] = player_name
        self.ui_data["performance_type"] = "Outfield"

        positions_played: str = self.position_entry.get().strip()

        if not self._validate_positions(positions_played):
            return False

        return self._buffer_performance(player_name)

    def _collect_and_convert(self, float_keys: set[str]) -> None:
        """Convert stat entry strings into numeric values for validation.

        Args:
            float_keys (set[str]): Stat keys that should be parsed as floats;
                all others are parsed as integers.
        """
        for stat_key, var in self.stats_vars.items():
            value: str = var.get()
            if stat_key in float_keys:
                self.ui_data[stat_key] = safe_float_conversion(value)
            else:
                self.ui_data[stat_key] = safe_int_conversion(value)

    def _validate_percentage_stats(self) -> bool:
        """Validate percentage-based statistics are within accepted bounds.

        Returns:
            bool: True when all percentage stats are between 0 and 100,
                otherwise False.
        """
        percentage_keys: set[str] = {
            "shot_accuracy",
            "pass_accuracy",
            "dribble_success_rate",
            "tackle_success_rate",
        }
        percentage_data: dict[str, int | float | str | list[str] | None] = {
            k: v for k, v in self.ui_data.items() if k in percentage_keys
        }
        percentage_defs: list[tuple[str, str]] = [
            (k, label) for k, label in self.stat_definitions if k in percentage_keys
        ]
        return self.validate_attr_range(
            percentage_data, percentage_defs, min_val=0, max_val=100
        )

    def _validate_pairs(self) -> bool:
        """Validate logical metric pairs against hard relationship rules.

        Returns:
            bool: True when all configured metric pairs satisfy constraints,
                otherwise False.
        """
        return self.validate_pair_hard(
            self.ui_data,
            [
                ("goals", "Goals", "shots", "Shots"),
                ("assists", "Assists", "passes", "Passes"),
                (
                    "distance_sprinted",
                    "Distance Sprinted",
                    "distance_covered",
                    "Distance Covered",
                ),
            ],
        )

    def _validate_maximums(self) -> bool:
        """Validate each stat does not exceed its configured maximum.

        Returns:
            bool: True when all stat values are at or below their defined
                maxima, otherwise False.
        """
        stat_max_rules: list[tuple[str, str, int]] = [
            ("goals", "Goals", 8),
            ("assists", "Assists", 8),
            ("shots", "Shots", 20),
            ("passes", "Passes", 100),
            ("dribbles", "Dribbles", 50),
            ("tackles", "Tackles", 50),
            ("offsides", "Offsides", 8),
            ("fouls_committed", "Fouls Committed", 8),
            ("possession_won", "Possession Won", 50),
            ("possession_lost", "Possession Lost", 50),
            ("distance_covered", "Distance Covered (km)", 15),
            ("distance_sprinted", "Distance Sprinted (km)", 10),
        ]

        for key, label, max_val in stat_max_rules:
            if not self.validate_stat_max(self.ui_data, key, label, max_value=max_val):
                return False
        return True

    def _validate_positions(self, positions_played: str) -> bool:
        """Validate and normalize the player positions input.

        Parses a comma-separated position list, normalizes case and spacing,
        checks values against allowed positions, and stores the normalized list
        on the UI payload.

        Args:
            positions_played (str): Raw comma-separated positions from the UI
                input field.

        Returns:
            bool: True when positions are present and valid; otherwise False.
        """
        if not positions_played:
            self.show_warning(
                "Validation Warning",
                (
                    "No positions entered. Please specify at "
                    "least one position played (e.g. RW, LW)."
                ),
            )
            return False
        positions = [
            pos.strip().upper() for pos in positions_played.split(",") if pos.strip()
        ]
        if not positions:
            self.show_warning(
                "Validation Warning",
                (
                    "Invalid positions format. Please enter "
                    "positions separated by commas (e.g. RW, LW)."
                ),
            )
            return False
        for pos in positions:
            if pos not in VALID_POSITIONS:
                self.show_warning(
                    "Validation Warning",
                    (
                        f"Invalid position '{pos}'. "
                        "Please enter valid positions (e.g. RW, LW)."
                    ),
                )
                return False
        self.ui_data["positions_played"] = positions
        return True

    def _buffer_performance(self, player_name: str) -> bool:
        """Persist the prepared performance payload into the match buffer.

        Args:
            player_name (str): Name of the player being buffered.

        Returns:
            bool: True when buffering succeeds; otherwise False.
        """
        logger.info(f"Validation passed for {player_name}. Buffering performance data.")
        try:
            self.controller.buffer_player_performance(self.ui_data)
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
            logger.error(
                f"Unexpected error while buffering data for {player_name}: {e}",
                exc_info=True,
            )
            self.show_error(
                "Buffering Error",
                (
                    "An unexpected error occurred while saving data for "
                    f"{player_name}: {e!s}. Please try again."
                ),
            )
            return False
