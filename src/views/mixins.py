"""Composable mixins for shared view behavior in CustomTkinter frames.

This module groups focused, UI-level behaviors that are reused by multiple
screens without requiring a deep inheritance chain. Each mixin addresses one
interaction concern and relies on host protocols from `src.contracts.ui` so
frames can opt into specific capabilities while preserving static typing.

Mixin scope:
- `PlayerDropdownMixin`: player availability checks, selected-name
    normalization, and dropdown value refresh.
- `OCRDataMixin`: host variable discovery and safe OCR payload mapping into
    bound `ctk.StringVar` entries.
- `PerformanceSidebarMixin`: buffered-performance removal and sidebar
    repopulation.
- `EntryFocusMixin`: recursive entry focus styling and success-flash button
    feedback.

Architectural intent:
- Keep feature frames thin by extracting repeated controller-to-widget glue.
- Preserve MVC boundaries by delegating data operations to controller
    contracts instead of embedding persistence behavior in views.
- Maintain consistent UI interactions across player, match, and career
    configuration workflows.
"""

import contextlib
import logging
from typing import cast

import customtkinter as ctk

from src.contracts.backend import OCRScalar
from src.contracts.ui import (
    EntryFocusMixinHostProtocol,
    OCRStatsPayload,
    PerformanceSidebarMixinHostProtocol,
    PlayerDropdownMixinHostProtocol,
)
from src.exceptions import UIPopulationError

logger = logging.getLogger(__name__)


class PlayerDropdownMixin:
    """A feature pack that adds player dropdown functionality to any frame."""

    def enforce_player_database(
        self: PlayerDropdownMixinHostProtocol,
        only_gk: bool = False,
        only_outfield: bool = False,
        remove_on_loan: bool = False,
    ) -> list[str]:
        """Return available player names or route the user to the library flow.

        Query the active career player library using the provided filters. When
        no players are available, show a warning and navigate to
        `PlayerLibraryFrame` so the user can add players first.

        Args:
            only_gk (bool): When True, include only goalkeeper names.
            only_outfield (bool): When True, include only outfield player names.
            remove_on_loan (bool): When True, exclude players marked as on loan.

        Returns:
            list[str]: Filtered player names, or an empty list when none are found.
        """
        names: list[str] = self.controller.get_all_player_names(
            only_gk=only_gk, only_outfield=only_outfield, remove_on_loan=remove_on_loan
        )
        if not names:
            self.show_warning(
                title="No Players Found",
                message="Add players to the library first",
                options=["Go to Library"],
            )
            self.controller.show_frame(
                self.controller.get_frame_class("PlayerLibraryFrame")
            )
            return []
        return names

    def resolve_selected_player_name(
        self: PlayerDropdownMixinHostProtocol,
        selected_value: str | None,
    ) -> str | None:
        """Resolve a dropdown value to a valid, existing player name.

        Strip the incoming dropdown value and verify that it resolves to a known
        player in the active career context.

        Args:
            selected_value (str | None): Raw value from a player dropdown variable.

        Returns:
            str | None: Normalized player name when it maps to an existing player;
            otherwise None.
        """
        if candidate := (selected_value or "").strip():
            return (
                candidate
                if self.controller.get_player_bio(candidate) is not None
                else None
            )
        else:
            return None

    def refresh_player_dropdown(
        self: PlayerDropdownMixinHostProtocol,
        only_gk: bool = False,
        only_outfield: bool = False,
        remove_on_loan: bool = False,
    ) -> None:
        """Refresh the dropdown options using the current filtered player set.

        Re-query the player database using the provided filters and update the
        bound dropdown widget values when at least one player is available.

        Args:
            only_gk (bool): When True, include only goalkeeper names.
            only_outfield (bool): When True, include only outfield player names.
            remove_on_loan (bool): When True, exclude players marked as on loan.
        """
        if names := self.enforce_player_database(
            only_gk=only_gk,
            only_outfield=only_outfield,
            remove_on_loan=remove_on_loan,
        ):
            self.player_dropdown.set_values(names)


class OCRDataMixin:
    """A feature pack that adds OCR data validation and processing to any frame."""

    def get_ocr_mapping(self) -> dict[str, dict[str, ctk.StringVar]]:
        """Return the active OCR variable mapping exposed by the host frame.

        Probes for common frame attributes used by OCR-populated views and
        returns a normalized mapping keyed by payload prefix. The empty-string
        prefix denotes a flat OCR payload.

        Returns:
            dict[str, dict[str, ctk.StringVar]]: Prefix-to-variable mapping used
            by `populate_stats`, or an empty mapping when no compatible
            variable container is present.
        """
        with contextlib.suppress(AttributeError):
            attr_vars: dict[str, ctk.StringVar] = cast(
                dict[str, ctk.StringVar],
                object.__getattribute__(self, "attr_vars"),
            )
            return {"": attr_vars}
        with contextlib.suppress(AttributeError):
            stats_vars: dict[str, ctk.StringVar] = cast(
                dict[str, ctk.StringVar],
                object.__getattribute__(self, "stats_vars"),
            )
            return {"": stats_vars}
        return {}

    def populate_stats(self, stats: OCRStatsPayload) -> None:
        """Populate bound StringVar fields from OCR statistics payloads.

        Supports both flat payloads and nested payloads where the top-level key
        maps to a prefixed dictionary. Values are coerced to strings for entry
        compatibility, with None rendered as an empty string.

        Args:
            stats (OCRStatsPayload): OCR-derived mapping of stat keys to values.

        Raises:
            UIPopulationError: If an empty payload is provided.
        """
        if not stats:
            raise UIPopulationError("No stats data provided for population")

        def _to_entry_text(value: OCRScalar) -> str:
            return "" if value is None else str(value)

        mapping: dict[str, dict[str, ctk.StringVar]] = self.get_ocr_mapping()

        for prefix, var_dict in mapping.items():
            for key, var in var_dict.items():
                # Case A: Nested dict (e.g. stats["home"]["possession"])
                nested_value = stats.get(prefix) if prefix else None
                if isinstance(nested_value, dict):
                    nested_stats = nested_value
                    if key in nested_stats:
                        var.set(_to_entry_text(nested_stats[key]))
                    else:
                        logger.warning(f"Key '{key}' not found in stats['{prefix}']")

                # Case B: Flat dict (e.g. stats["possession"])
                elif not prefix and key in stats:
                    flat_value = stats[key]
                    if isinstance(flat_value, dict):
                        continue
                    var.set(_to_entry_text(flat_value))


class PerformanceSidebarMixin:
    """A feature pack for syncing buffered performance rows with sidebar widgets."""

    def remove_player_from_buffer(
        self: PerformanceSidebarMixinHostProtocol, player_name: str
    ) -> None:
        """Remove a buffered player and immediately refresh sidebar rows.

        Args:
            player_name (str): Player identifier used by the buffer service.
        """
        self.controller.remove_player_from_buffer(player_name)
        self.refresh_performance_sidebar()

    def refresh_performance_sidebar(self: PerformanceSidebarMixinHostProtocol) -> None:
        """Reload and display buffered performance rows in the sidebar widget.

        Requests display-ready rows from the controller with fixed display keys
        and repopulates the bound performance sidebar.
        """
        buffered_players = self.controller.get_buffered_player_performances(
            display_keys=["player_name", "positions_played"], id_key="player_name"
        )
        self.performance_sidebar.populate(buffered_players)


class EntryFocusMixin:
    """A feature pack for entry focus styling and success-state button flashes."""

    def _theme_color(self: EntryFocusMixinHostProtocol, widget: str, key: str) -> str:
        """Resolve a theme color value for the active appearance mode.

        Reads the requested color token from CustomTkinter's active theme. When
        the token stores light/dark variants as a list, selects the appropriate
        value for the current appearance mode.

        Args:
            widget (str): CustomTkinter widget key in the theme table.
            key (str): Color property key under the widget section.

        Returns:
            str: The resolved color string for the active mode.
        """
        value: str | list[str] = ctk.ThemeManager.theme[widget][key]
        if isinstance(value, list):
            idx = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
            return value[idx]
        return value

    def apply_focus_flourishes(
        self: EntryFocusMixinHostProtocol,
        parent_widget: ctk.CTkBaseClass,
    ) -> None:
        """Bind focus-in and focus-out border styling to entry widgets.

        Walk the widget tree recursively from `parent_widget`, attaching focus
        handlers to each `CTkEntry` so borders highlight with semantic info
        color on focus and reset to themed defaults on blur.

        Args:
            parent_widget (ctk.CTkBaseClass): Root container to traverse.
        """
        for child in parent_widget.winfo_children():
            if isinstance(child, ctk.CTkEntry):
                child.bind(
                    "<FocusIn>",
                    lambda event, w=child: w.configure(
                        border_color=self.theme.semantic_colors.info
                    ),
                )
                child.bind(
                    "<FocusOut>",
                    lambda event, w=child: w.configure(
                        border_color=self._theme_color("CTkEntry", "border_color")
                    ),
                )
            elif isinstance(child, (ctk.CTkFrame, ctk.CTkScrollableFrame)):
                self.apply_focus_flourishes(child)

    def trigger_success_flash(
        self: EntryFocusMixinHostProtocol,
        button: ctk.CTkButton,
        original_text: str,
    ) -> None:
        """Temporarily style a button as successful, then restore defaults.

        Immediately applies semantic success colors and an "Added!" label, then
        schedules a one-second reset to the widget's theme-driven colors and the
        provided original label.

        Args:
            button (ctk.CTkButton): Button to animate.
            original_text (str): Label text to restore after the flash period.
        """
        button.configure(
            fg_color=self.theme.semantic_colors.success,
            hover_color=self.theme.semantic_colors.success,
            text="Added!",
        )
        button.after(
            1000,
            lambda: button.configure(
                fg_color=self._theme_color("CTkButton", "fg_color"),
                hover_color=self._theme_color("CTkButton", "hover_color"),
                text=original_text,
            ),
        )
