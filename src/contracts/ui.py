"""UI-layer typing contracts for controller/view interactions.

This module intentionally contains framework-specific typing helpers used by
CustomTkinter controllers and views. Keep cross-layer payload contracts in
src.contracts and persistence models in src.schemas.
"""

from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

import customtkinter as ctk

from src.contracts.backend import (
    DisplayRows,
    FinancialDataPayload,
    InjuryDataPayload,
    MatchOverviewPayload,
    OCRStatsResult,
    PlayerAttributePayload,
    PlayerBioDict,
    PlayerPerformancePayload,
)

type AppFrameClass = type[ctk.CTkFrame]
type AppFrameRegistry = dict[AppFrameClass, ctk.CTkFrame]
type OCRStatsPayload = OCRStatsResult
type WarningScalar = str | int | float | bool | None
type WarningValue = WarningScalar | tuple[WarningScalar, ...]
type AlertOption = str | list[str] | tuple[str, str] | dict[str, str]
type PlaceGeometryValue = float | int | str


@runtime_checkable
class WidthEventProtocol(Protocol):
    """Minimal configure-event surface required for wrap calculations."""

    width: int


@runtime_checkable
class SemanticColorsProtocol(Protocol):
    """Theme semantic colors used by shared view helpers."""

    accent: str
    info: str
    warning: str
    success: str
    submit_hover: str
    remove_hover: str
    unsaved_nav_hover: str


@runtime_checkable
class BaseViewThemeProtocol(Protocol):
    """Theme capability contract required by BaseViewFrame."""

    semantic_colors: SemanticColorsProtocol


@runtime_checkable
class DelayOverlayHostProtocol(Protocol):
    """Host capability contract required by delay overlay helper."""

    fonts: dict[str, ctk.CTkFont]
    _theme: BaseViewThemeProtocol


@runtime_checkable
class ThemeProtocol(BaseViewThemeProtocol, Protocol):
    """Backward-compatible alias for generic view theme contracts."""


@runtime_checkable
class DynamicFontsControllerProtocol(Protocol):
    """Controller capability for shared dynamic font access."""

    dynamic_fonts: dict[str, ctk.CTkFont]


@runtime_checkable
class UnsavedWorkControllerProtocol(Protocol):
    """Controller capability for unsaved-work checks and buffer clearing."""

    def has_unsaved_work(self) -> bool:
        """Return whether there is currently unsaved staged work."""

    def clear_session_buffers(self) -> None:
        """Clear staged in-memory session buffers."""


@runtime_checkable
class NavigationControllerProtocol(Protocol):
    """Controller capability for frame class lookup and navigation."""

    def show_frame(self, page_class: AppFrameClass) -> None:
        """Raise the requested frame in the main content area."""

    def get_frame_class(self, name: str) -> AppFrameClass:
        """Resolve a frame class by its registered class name."""


@runtime_checkable
class LatestMatchDateControllerProtocol(Protocol):
    """Optional controller capability for chronology validation flows."""

    def get_latest_match_in_game_date(self) -> datetime | None:
        """Return the latest saved in-game match date, if available."""


@runtime_checkable
class BaseViewControllerProtocol(
    DynamicFontsControllerProtocol,
    UnsavedWorkControllerProtocol,
    NavigationControllerProtocol,
    Protocol,
):
    """Composed controller contract required by BaseViewFrame."""


@runtime_checkable
class ViewControllerProtocol(
    BaseViewControllerProtocol,
    LatestMatchDateControllerProtocol,
    Protocol,
):
    """Backward-compatible superset for legacy view controller annotations."""


@runtime_checkable
class WarningDialogProtocol(Protocol):
    """Host capability for warning popups used by mixins."""

    def show_warning(
        self,
        title: str,
        message: str,
        options: list[str] | None = None,
    ) -> str | None:
        """Display a warning dialog and optionally return a selected option."""


@runtime_checkable
class PlayerLookupControllerProtocol(Protocol):
    """Controller capability for player listing and identity lookups."""

    def get_all_player_names(
        self,
        only_outfield: bool = False,
        only_gk: bool = False,
        remove_on_loan: bool = False,
    ) -> list[str]:
        """Return filtered player names for dropdown selection."""

    def get_player_bio(self, name: str) -> PlayerBioDict | None:
        """Return player bio details when a matching player exists."""


@runtime_checkable
class PlayerDropdownControllerProtocol(
    NavigationControllerProtocol,
    PlayerLookupControllerProtocol,
    Protocol,
):
    """Composed controller capability required by PlayerDropdownMixin."""


@runtime_checkable
class FinancialSaveControllerProtocol(Protocol):
    """Controller capability for persisting player financial updates."""

    def save_financial_data(
        self,
        player_name: str,
        financial_data: FinancialDataPayload,
        in_game_date: str,
    ) -> None:
        """Persist financial data for the selected player."""


@runtime_checkable
class InjuryRecordControllerProtocol(Protocol):
    """Controller capability for persisting player injury records."""

    def add_injury_record(
        self,
        player_name: str,
        injury_data: InjuryDataPayload,
    ) -> None:
        """Persist an injury record for the selected player."""


@runtime_checkable
class CareerDetailsControllerProtocol(Protocol):
    """Controller capability for retrieving current career metadata."""

    def get_current_career_details(self):
        """Return the currently active career metadata, if any."""


@runtime_checkable
class CompetitionControllerProtocol(Protocol):
    """Controller capability for managing active-career competitions."""

    def add_competition(self, competition: str) -> None:
        """Add a competition to the active career."""

    def remove_competition(self, competition: str) -> None:
        """Remove a competition from the active career."""


@runtime_checkable
class CareerMetadataControllerProtocol(Protocol):
    """Controller capability for metadata patch updates."""

    def update_career_metadata(self, updates: dict[str, object]) -> None:
        """Apply metadata updates to the active career."""


@runtime_checkable
class CareerSelectionControllerProtocol(Protocol):
    """Controller capability for career listing and activation."""

    def get_all_career_names(self) -> list[str]:
        """Return all available career names."""

    def activate_career(self, career_name: str) -> None:
        """Load and activate the selected career."""


@runtime_checkable
class CareerCreationControllerProtocol(Protocol):
    """Controller capability for creating new careers."""

    PROJECT_ROOT: Path

    def save_new_career(
        self,
        club_name: str,
        manager_name: str,
        starting_season: str,
        half_length: int,
        match_difficulty: str,
        league: str,
    ) -> None:
        """Create and save a new career with the provided details."""


@runtime_checkable
class MatchOverviewControllerProtocol(Protocol):
    """Controller capability for match-overview staging and OCR kickoff."""

    screenshot_delay: int

    def buffer_match_overview(self, overview_data: MatchOverviewPayload) -> None:
        """Stage global match overview statistics."""

    def process_match_stats(self) -> None:
        """Trigger screenshot and OCR for match overview stats."""


@runtime_checkable
class PlayerAttributeProcessorControllerProtocol(Protocol):
    """Controller capability for OCR-driven player attribute extraction."""

    def process_player_attributes(
        self,
        is_goalkeeper: bool,
        is_first_page: bool,
    ) -> None:
        """Trigger screenshot and OCR for player attribute capture."""


@runtime_checkable
class PlayerTransferControllerProtocol(Protocol):
    """Controller capability for selling and loan-state player actions."""

    def sell_player(self, player_name: str, in_game_date: str) -> None:
        """Sell the selected player on the provided in-game date."""

    def loan_out_player(self, player_name: str) -> None:
        """Loan out the selected player."""

    def return_loan_player(self, player_name: str) -> None:
        """Return the selected player from loan."""


@runtime_checkable
class SidebarStateControllerProtocol(Protocol):
    """Controller capability for sidebar collapse state management."""

    def set_sidebar_collapse_state(self, sidebar_id: str, collapsed: bool) -> None:
        """Store collapsed state for a sidebar."""

    def get_sidebar_collapse_state(self, sidebar_id: str) -> bool:
        """Read collapsed state for a sidebar."""


@runtime_checkable
class PlayerPerformanceControllerProtocol(Protocol):
    """Controller capability for per-player match performance staging and OCR."""

    def buffer_player_performance(
        self,
        performance_data: PlayerPerformancePayload,
    ) -> None:
        """Stage one player's performance payload."""

    def process_player_stats(self, is_goalkeeper: bool = False) -> None:
        """Trigger OCR flow for player performance stats."""


@runtime_checkable
class SaveBufferedMatchControllerProtocol(Protocol):
    """Controller capability for committing buffered match payloads."""

    def save_buffered_match(self, force_save: bool = False) -> None:
        """Persist staged match data, optionally bypassing discrepancy checks."""


@runtime_checkable
class AddFinancialFrameControllerProtocol(
    BaseViewControllerProtocol,
    PlayerDropdownControllerProtocol,
    FinancialSaveControllerProtocol,
    Protocol,
):
    """Composed controller capability required by AddFinancialFrame."""


@runtime_checkable
class PlayerBufferSaveControllerProtocol(Protocol):
    """Controller capability for buffering and saving player attributes."""

    def buffer_player_attributes(
        self,
        data: PlayerAttributePayload,
        is_goalkeeper: bool,
        is_first_page: bool = True,
    ) -> None:
        """Stage player attributes for later persistence."""

    def save_player(self) -> None:
        """Persist the buffered player payload."""


@runtime_checkable
class AddGKFrameControllerProtocol(
    BaseViewControllerProtocol,
    PlayerDropdownControllerProtocol,
    PlayerBufferSaveControllerProtocol,
    Protocol,
):
    """Composed controller capability required by AddGKFrame."""


@runtime_checkable
class AddInjuryFrameControllerProtocol(
    BaseViewControllerProtocol,
    PlayerDropdownControllerProtocol,
    InjuryRecordControllerProtocol,
    Protocol,
):
    """Composed controller capability required by AddInjuryFrame."""


@runtime_checkable
class AddMatchFrameControllerProtocol(
    BaseViewControllerProtocol,
    CareerDetailsControllerProtocol,
    MatchOverviewControllerProtocol,
    Protocol,
):
    """Composed controller capability required by AddMatchFrame."""


@runtime_checkable
class AddOutfieldFrame1ControllerProtocol(
    BaseViewControllerProtocol,
    PlayerDropdownControllerProtocol,
    PlayerBufferSaveControllerProtocol,
    PlayerAttributeProcessorControllerProtocol,
    Protocol,
):
    """Composed controller capability required by AddOutfieldFrame1."""


@runtime_checkable
class AddOutfieldFrame2ControllerProtocol(
    BaseViewControllerProtocol,
    PlayerBufferSaveControllerProtocol,
    Protocol,
):
    """Composed controller capability required by AddOutfieldFrame2."""


@runtime_checkable
class CareerConfigFrameControllerProtocol(
    BaseViewControllerProtocol,
    CareerDetailsControllerProtocol,
    CompetitionControllerProtocol,
    CareerMetadataControllerProtocol,
    Protocol,
):
    """Composed controller capability required by CareerConfigFrame."""


@runtime_checkable
class CareerSelectFrameControllerProtocol(
    BaseViewControllerProtocol,
    CareerSelectionControllerProtocol,
    Protocol,
):
    """Composed controller capability required by CareerSelectFrame."""


@runtime_checkable
class CreateCareerFrameControllerProtocol(
    BaseViewControllerProtocol,
    CareerCreationControllerProtocol,
    Protocol,
):
    """Composed controller capability required by CreateCareerFrame."""


@runtime_checkable
class MainMenuFrameControllerProtocol(
    BaseViewControllerProtocol,
    CareerDetailsControllerProtocol,
    Protocol,
):
    """Composed controller capability required by MainMenuFrame."""


@runtime_checkable
class LeftPlayerFrameControllerProtocol(
    BaseViewControllerProtocol,
    PlayerDropdownControllerProtocol,
    PlayerTransferControllerProtocol,
    Protocol,
):
    """Composed controller capability required by LeftPlayerFrame."""


@runtime_checkable
class MatchAddedFrameControllerProtocol(
    BaseViewControllerProtocol,
    Protocol,
):
    """Composed controller capability required by MatchAddedFrame."""


@runtime_checkable
class MatchStatsFrameControllerProtocol(
    BaseViewControllerProtocol,
    Protocol,
):
    """Composed controller capability required by MatchStatsFrame."""

    def buffer_match_overview(self, overview_data: MatchOverviewPayload) -> None:
        """Stage global match overview statistics."""

    def process_player_stats(self, is_goalkeeper: bool = False) -> None:
        """Trigger OCR flow for player performance stats."""

    def save_buffered_match(self, force_save: bool = False) -> None:
        """Persist staged match data, optionally bypassing discrepancy checks."""


@runtime_checkable
class PlayerLibraryFrameControllerProtocol(
    BaseViewControllerProtocol,
    PlayerAttributeProcessorControllerProtocol,
    Protocol,
):
    """Composed controller capability required by PlayerLibraryFrame."""

    screenshot_delay: int


@runtime_checkable
class DropdownValuesWidgetProtocol(Protocol):
    """Widget capability for replacing dropdown value collections."""

    def set_values(self, values: list[str]) -> None:
        """Replace available dropdown values with the provided list."""


@runtime_checkable
class PlayerDropdownMixinHostProtocol(WarningDialogProtocol, Protocol):
    """Host object contract required by PlayerDropdownMixin methods."""

    controller: PlayerDropdownControllerProtocol
    player_dropdown: DropdownValuesWidgetProtocol

    def enforce_player_database(
        self,
        only_gk: bool = False,
        only_outfield: bool = False,
        remove_on_loan: bool = False,
    ) -> list[str]:
        """Validate and return player names suitable for dropdown population."""


@runtime_checkable
class PerformanceBufferControllerProtocol(Protocol):
    """Controller capability for staged player-performance sidebar actions."""

    def get_buffered_player_performances(
        self,
        display_keys: list[str],
        id_key: str = "player_name",
        default: str = "-",
    ) -> DisplayRows:
        """Return currently buffered player performances for display."""

    def remove_player_from_buffer(self, player_name: str) -> None:
        """Remove a single player from the staged performance buffer."""


@runtime_checkable
class GKStatsFrameControllerProtocol(
    BaseViewControllerProtocol,
    PlayerDropdownControllerProtocol,
    SidebarStateControllerProtocol,
    PlayerPerformanceControllerProtocol,
    SaveBufferedMatchControllerProtocol,
    PerformanceBufferControllerProtocol,
    Protocol,
):
    """Composed controller capability required by GKStatsFrame."""


@runtime_checkable
class PlayerStatsFrameControllerProtocol(
    BaseViewControllerProtocol,
    PlayerDropdownControllerProtocol,
    SidebarStateControllerProtocol,
    PlayerPerformanceControllerProtocol,
    SaveBufferedMatchControllerProtocol,
    PerformanceBufferControllerProtocol,
    Protocol,
):
    """Composed controller capability required by PlayerStatsFrame."""


@runtime_checkable
class SidebarPopulateWidgetProtocol(Protocol):
    """Sidebar widget capability for refreshing display rows."""

    def populate(self, rows: DisplayRows) -> None:
        """Populate the sidebar with display-ready rows."""


@runtime_checkable
class PerformanceSidebarMixinHostProtocol(Protocol):
    """Host object contract required by PerformanceSidebarMixin methods."""

    controller: PerformanceBufferControllerProtocol
    performance_sidebar: SidebarPopulateWidgetProtocol

    def refresh_performance_sidebar(self) -> None:
        """Refresh the sidebar from the current staged performance buffer."""


@runtime_checkable
class EntryFocusMixinHostProtocol(Protocol):
    """Host object contract required by EntryFocusMixin methods."""

    theme: BaseViewThemeProtocol

    def _theme_color(self, widget: str, key: str) -> str:
        """Resolve an appearance-aware CTk theme token."""

    def apply_focus_flourishes(self, parent_widget: ctk.CTkBaseClass) -> None:
        """Apply recursive entry focus effects to child widgets."""


@runtime_checkable
class SemanticStyleRefreshable(Protocol):
    """Frame protocol for semantic theme/style refresh hooks."""

    def refresh_semantic_styles(self) -> None:
        """Refresh frame semantic styles after theme or state changes."""


@runtime_checkable
class OnShowLifecycle(Protocol):
    """Frame protocol for on-show lifecycle hooks."""

    def on_show(self) -> None:
        """Run per-frame lifecycle logic when a frame is raised."""


@runtime_checkable
class StatsPopulatable(Protocol):
    """Frame protocol for OCR-driven stat population hooks."""

    def populate_stats(self, stats: OCRStatsPayload) -> None:
        """Populate the frame with OCR-detected values."""
