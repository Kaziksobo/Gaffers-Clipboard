"""Application controller for Gaffer's Clipboard.

This module owns the top-level CustomTkinter `App` class and wires the main
service graph used by the desktop application. It configures the window,
theme, and fonts; initializes persistence, OCR, screenshot, buffering, and
mutation services; and constructs the frame registry used for navigation.

The `App` class is the central coordinator between views and services:

- Views raise controller actions instead of touching persistence directly.
- OCR and screenshot flows are isolated behind service wrappers.
- Buffered player and match payloads are staged here before commit.
- Shared typed contracts from `src.contracts` define the controller boundary.

The module stays intentionally thin at the top level so the UI bootstrap,
navigation, and orchestration logic remain in one place while the rest of the
codebase focuses on domain-specific behavior.
"""

import logging
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import cast

import customtkinter as ctk

from src.analytics_engine import AnalyticsEngine
from src.contracts.backend import (
    BufferedMatch,
    BufferedPlayer,
    CareerMetadataUpdate,
    DisplayRows,
    FinancialDataPayload,
    InjuryDataPayload,
    MatchOverviewPayload,
    MatchStatsPayload,
    PlayerAttributePayload,
    PlayerBioDict,
    PlayerPerformancePayload,
    UIFlushCallback,
)
from src.contracts.ui import (
    AppFrameClass,
    AppFrameRegistry,
    OCRStatsPayload,
    OnShowLifecycle,
    SemanticStyleRefreshable,
    StatsPopulatable,
)
from src.data_manager import DataManager
from src.exceptions import DataDiscrepancyError, FrameNotFoundError, UIPopulationError
from src.schemas import CareerMetadata, DifficultyLevel

# Service imports
from src.services import app as app_services

# View Imports
from src.theme import theme
from src.views.add_financial_frame import AddFinancialFrame
from src.views.add_gk_frame import AddGKFrame
from src.views.add_injury_frame import AddInjuryFrame
from src.views.add_match_frame import AddMatchFrame
from src.views.add_outfield_frame_1 import AddOutfieldFrame1
from src.views.add_outfield_frame_2 import AddOutfieldFrame2
from src.views.career_config_frame import CareerConfigFrame
from src.views.career_select_frame import CareerSelectFrame
from src.views.create_career_frame import CreateCareerFrame
from src.views.gk_stats_frame import GKStatsFrame
from src.views.left_player_frame import LeftPlayerFrame
from src.views.main_menu_frame import MainMenuFrame
from src.views.match_added_frame import MatchAddedFrame
from src.views.match_review_frame import MatchReviewFrame
from src.views.match_stats_frame import MatchStatsFrame
from src.views.player_library_frame import PlayerLibraryFrame
from src.views.player_stats_frame import PlayerStatsFrame
from src.views.widgets.delay_overlay import show_delay_overlay

logger = logging.getLogger(__name__)


class App(ctk.CTk):
    """The main application controller for Gaffer's Clipboard.

    Manages the global state, window configuration, data manager instance,
    and navigation between different UI frames.
    """

    # Default screenshot delay (seconds) used when no explicit delay is provided
    DEFAULT_SCREENSHOT_DELAY = 3
    PROJECT_ROOT = Path(__file__).parent.parent

    def __init__(self) -> None:
        """Initialize the main application window and core service graph.

        Configures the theme and window, wires up shared services and data
        managers, and eagerly constructs all navigation frames for later use.

        """
        super().__init__()
        logger.info("Application starting up. Project root: %s", App.PROJECT_ROOT)

        # Load CustomTkinter JSON theme
        theme_path = str(App.PROJECT_ROOT / "src" / "themes" / "dark.json")
        ctk.set_default_color_theme(theme_path)
        logger.info("Loaded CTk theme from: %s", theme_path)

        # Set appearance mode
        ctk.set_appearance_mode("dark")

        # Window configuration
        self.title("Gaffer's Clipboard")
        self.geometry("1000x700")
        self.minsize(width=1000, height=700)

        self._theme = theme

        # Initialize dynamic fonts and bind to window resize for responsive scaling
        self.dynamic_fonts: dict[str, ctk.CTkFont] = self._initialize_dynamic_fonts()
        self.bind("<Configure>", self._on_window_resize)
        self.fonts: dict[str, ctk.CTkFont] = self.dynamic_fonts

        # Set sidebar states
        self._sidebar_states = {
            # Shared performance sidebar used by player/GK stats views
            "performance_sidebar": True,
            "player_stats_sidebar": True,
            "gk_stats_sidebar": True,
        }

        # Initialize the data manager
        self._data_manager: DataManager = DataManager(App.PROJECT_ROOT)

        # Initialise the analytics engine
        self._analytics_engine: AnalyticsEngine = AnalyticsEngine(App.PROJECT_ROOT)

        # Initialize services
        def overlay_callback(seconds: int, message: str) -> None:
            show_delay_overlay(self, seconds, message)

        ui_flush_callback: UIFlushCallback = self.update

        self._screenshot_service = app_services.ScreenshotService(
            project_root=App.PROJECT_ROOT,
            screenshot_delay=App.DEFAULT_SCREENSHOT_DELAY,
            overlay_callback=overlay_callback,
            ui_flush_callback=ui_flush_callback,
        )
        self._ocr_service = app_services.OCRService(project_root=App.PROJECT_ROOT)
        self._buffer_service = app_services.BufferService()
        self._player_service = app_services.PlayerService(self._data_manager)
        self._career_service = app_services.CareerService(self._data_manager)
        self._match_service = app_services.MatchService(self._data_manager)

        self._current_discrepancies: dict[str, dict[str, int | float]] = {}

        # Frame configuration
        container: ctk.CTkFrame = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self._frames: AppFrameRegistry = {}

        for frame_cls in (
            CareerSelectFrame,
            CreateCareerFrame,
            MainMenuFrame,
            AddMatchFrame,
            MatchStatsFrame,
            PlayerStatsFrame,
            MatchAddedFrame,
            PlayerLibraryFrame,
            AddGKFrame,
            AddOutfieldFrame1,
            AddOutfieldFrame2,
            AddFinancialFrame,
            LeftPlayerFrame,
            GKStatsFrame,
            AddInjuryFrame,
            CareerConfigFrame,
            MatchReviewFrame,
        ):
            try:
                frame = frame_cls(container, self, self._theme)
                self._frames[frame_cls] = frame
                frame.grid(row=0, column=0, sticky="nsew")
            except Exception as e:
                logger.critical(
                    "Failed to initialize frame %s: %s", frame_cls.__name__, e
                )
                raise

        logger.info("Application initialized. Showing CareerSelectFrame.")
        self.show_frame(CareerSelectFrame)

    # --- UI setup ---

    def _initialize_dynamic_fonts(self) -> dict[str, ctk.CTkFont]:
        """Create live CTkFont instances from the theme's font configuration.

        Reads the font definitions from the active theme and instantiates a
        reusable, named set of fonts that can be dynamically resized at runtime.

        Returns:
            dict[str, ctk.CTkFont]: Mapping of theme font keys to initialized
            CTkFont objects ready for use across the application.
        """
        live_fonts: dict[str, ctk.CTkFont] = {}
        # We expect the theme fonts to be defined as tuples: (family, size, weight)
        for font_name, font_config in vars(self._theme.fonts).items():
            family: str = font_config[0]
            base_size: int = font_config[1]
            weight: str = font_config[2] if len(font_config) > 2 else "normal"

            live_fonts[font_name] = ctk.CTkFont(
                family=family, size=base_size, weight=weight
            )

        return live_fonts

    def _on_window_resize(self, event: tk.Event) -> None:
        """Dynamically scale application fonts in response to window size changes.

        Computes a width-based scale factor when the main window is resized and
        adjusts themed CTkFont instances within configured bounds for readability.

        Args:
            event (tk.Event): Tkinter configure event containing the new window
                dimensions.
        """
        minimum_window_width = 100

        if event.widget == self and event.width > minimum_window_width:
            window_base_width = 800
            scale_factor_divisor = 40
            # Calculate a scale factor based on how much wider the window is
            # than the base width.
            scale_factor: float = max(
                0, (event.width - window_base_width) / scale_factor_divisor
            )

            # Define font scaling configurations:
            # (base_size, scale_multiplier, min_size, max_size)
            font_configs = {
                "title": (24, 1.5, 24, 64),
                "button": (16, 0.5, 14, 24),
                "body": (16, 0.5, 14, 22),
                "sidebar_button": (14, 0.3, 12, 18),
                "sidebar_body": (14, 0.3, 12, 18),
            }

            for font_name, (
                base_size,
                multiplier,
                min_size,
                max_size,
            ) in font_configs.items():
                # Calculate the new font size based on the window width,
                # then clamp it within the defined min and max sizes.
                new_size = base_size + (scale_factor * multiplier)
                clamped_size = max(min_size, min(new_size, max_size))
                self.dynamic_fonts[font_name].configure(size=int(clamped_size))

    # --- Navigation and frame state ---

    def get_frame_class(self, name: str) -> AppFrameClass:
        """Resolve a frame class by its name from the registered frames.

        Iterates over known frame types and returns the one whose class name
        matches the requested identifier, enforcing a clear error if missing.

        Args:
            name (str): The class name of the frame to look up.

        Returns:
            AppFrameClass: The matching frame class registered with the app.

        Raises:
            FrameNotFoundError: If no frame with the given class name is found.
        """
        for cls in self._frames:
            if cls.__name__ == name:
                return cls
        raise FrameNotFoundError(f"No frame class named '{name}' found.")

    def show_frame(self, page_class: AppFrameClass) -> None:
        """Raise a target frame to the front and trigger its lifecycle hooks.

        Validates that the requested frame is registered, brings it into view,
        and invokes any semantic refresh or on-show callbacks exposed by the frame.

        Args:
            page_class (AppFrameClass): The frame class to display.

        Raises:
            FrameNotFoundError: If the requested frame is not registered.
        """
        logger.info("Navigating to frame: %s", page_class.__name__)

        if page_class not in self._frames:
            raise FrameNotFoundError(
                f"No frame class named '{page_class.__name__}' found."
            )

        frame: ctk.CTkFrame = self._frames[page_class]
        frame.tkraise()

        # Trigger a refresh of semantic styles if the frame supports it
        if isinstance(frame, SemanticStyleRefreshable):
            frame.refresh_semantic_styles()

        # Trigger on_show lifecycle method if it exists for the frame
        if isinstance(frame, OnShowLifecycle):
            frame.on_show()

    def get_sidebar_collapse_state(self, sidebar_id: str) -> bool:
        """Return whether a given sidebar is currently collapsed in the UI.

        Looks up the stored sidebar state by identifier and falls back to a
        sensible default when no explicit state has been recorded.

        Args:
            sidebar_id (str): Unique key identifying the sidebar.

        Returns:
            bool: True if the sidebar is collapsed (hidden), False if expanded.
        """
        return self._sidebar_states.get(sidebar_id, True)

    def set_sidebar_collapse_state(self, sidebar_id: str, collapsed: bool) -> None:
        """Update the stored collapse state for a given sidebar.

        Records whether a specific sidebar should be treated as hidden or expanded
        so that views can render consistently with the user's last choice.

        Args:
            sidebar_id (str): Unique key identifying the sidebar.
            collapsed (bool): True if collapsed, False if expanded.
        """
        self._sidebar_states[sidebar_id] = collapsed

    # --- Session safety and reset ---

    def has_unsaved_work(self) -> bool:
        """Check if there is uncommitted data currently staged in memory.

        Used by UI frames (like navigation bars or exit prompts) to warn the user
        before abandoning an in-progress match or player creation. See
        `BufferService.has_unsaved_work` for exactly what constitutes an unsaved state.

        Returns:
            bool: True if buffers contain staged data, False otherwise.
        """
        return self._buffer_service.has_unsaved_work()

    def clear_session_buffers(self) -> None:
        """Purge all temporarily staged data from the current application session.

        Typically triggered by UI cancellation events (e.g., clicking 'Main Menu' or
        'Back') to ensure subsequent data entry operations start with a clean slate.
        Delegates to `BufferService.clear_session_buffers`.
        """
        self._buffer_service.clear_session_buffers()

    # --- Career selection and configuration ---

    def get_all_career_names(self) -> list[str]:
        """Retrieve a list of unique, formatted career display names.

        Used primarily by the application's startup UI (e.g., CareerSelectFrame)
        to populate selection widgets. Note that the returned strings are dynamically
        formatted (e.g., appending the manager's name if multiple saves exist for
        the same club) to guarantee visual uniqueness in the UI.

        Delegates directory scanning and deduplication logic to
        `CareerService.get_all_career_names`.

        Returns:
            list[str]: A list of formatted career display names ready for UI injection.
                       Returns an empty list if no careers exist on disk.
        """
        return self._career_service.get_all_career_names()

    def save_new_career(
        self,
        club_name: str,
        manager_name: str,
        starting_season: str,
        half_length: int,
        match_difficulty: DifficultyLevel,
        league: str,
    ) -> None:
        """Persist a new career profile to disk and set it as active session context.

        Triggered by the CreateCareerFrame submission. This delegates directory
        creation, Pydantic validation, and initial JSON setup to
        `CareerService.save_new_career`. Crucially, a successful save automatically
        alters application state so subsequent reads/writes target this new career.

        Args:
            club_name (str): The display name of the club (used for folder generation).
            manager_name (str): The manager's name associated with the save.
            starting_season (str): The starting season label (e.g., "24/25").
            half_length (int): The in-game match half length in minutes.
            match_difficulty (DifficultyLevel): The user's selected difficulty enum.
            league (str): The league in which the club competes.

        Raises:
            ValidationError: If the career metadata payload fails schema
                validation during creation.
        """
        self._career_service.save_new_career(
            club_name,
            manager_name,
            starting_season,
            half_length,
            match_difficulty,
            league,
        )

    def activate_career(self, career_name: str) -> None:
        """Switch the application's global context to the specified career.

        Updating this state dictates that all subsequent data reads and writes
        will target this specific career's JSON storage. See
        `CareerService.activate_career` for how the underlying data manager is updated.

        Args:
            career_name (str): The exact directory/display name of the target career.

        Raises:
            ValueError: If the target career cannot be loaded.
        """
        self._career_service.activate_career(career_name)

    def get_current_career_details(self) -> CareerMetadata | None:
        """Retrieve the metadata for the currently active career session.

        Used by UI frames to populate headers, sidebars, and configuration screens
        with the active save's context (e.g., club name, manager, difficulty).
        Delegates directly to `CareerService.get_current_career_details`.

        Returns:
            CareerMetadata | None: The active career's metadata, or None if no
                                   career has been activated yet.
        """
        return self._career_service.get_current_career_details()

    def update_career_metadata(self, updates: CareerMetadataUpdate) -> None:
        """Apply partial updates to the active career's configuration.

        Triggered when the user modifies overarching save details (like manager name
        or difficulty) in the settings UI. Because the payload is a partial TypedDict,
        views only need to pass the specific fields that were actually changed.
        Delegates the data merging and disk persistence to
        `CareerService.update_career_metadata`.

        Args:
            updates (CareerMetadataUpdate): A dictionary containing the specific
                                            key-value pairs to update.

        Raises:
            RuntimeError: If no active career context is loaded.
            ValidationError: If the merged metadata fails schema validation.
        """
        self._career_service.update_career_metadata(updates)

    def add_competition(self, competition: str) -> None:
        """Register a new competition to the active career's context.

        Used by the UI (e.g., CareerConfigFrame) to expand the list of available
        competitions users can select when logging new matches. Delegates the
        data validation and persistence to `CareerService.add_competition`.

        Args:
            competition (str): The name of the competition to add (e.g., "FA Cup").

        Raises:
            RuntimeError: If no active career context is loaded.
        """
        self._career_service.add_competition(competition)

    def remove_competition(self, competition: str) -> None:
        """Unregister a competition from the active career's context.

        Triggered by UI settings to prevent this competition from appearing in
        future match-logging dropdowns. Delegates the deletion step to
        `CareerService.remove_competition`.

        Args:
            competition (str): The exact name of the competition to remove.

        Raises:
            RuntimeError: If no active career context is loaded.
            ValueError: If the competition is referenced by existing matches.
        """
        self._career_service.remove_competition(competition)

    # --- Global Timeline Helper ---
    def get_latest_match_in_game_date(self) -> datetime | None:
        """Retrieve the in-game date of the most recently recorded match.

        Typically used by data entry frames to validate that new events
        (matches, injuries, transfers) are occurring chronologically.
        Delegates to `MatchService.get_latest_match_in_game_date`.

        Returns:
            datetime | None: The parsed date of the latest match, or None if the
                             current career has no recorded matches.
        """
        return self._match_service.get_latest_match_in_game_date()

    # --- Squad lookup and identity ---

    def get_all_player_names(
        self,
        only_outfield: bool = False,
        only_gk: bool = False,
        remove_on_loan: bool = False,
    ) -> list[str]:
        """Retrieve a filtered list of registered player names for the active career.

        Used extensively by UI frames to populate selection widgets like scrollable
        dropdowns and library lists. The boolean flags allow views to restrict the
        returned names based on the current context (e.g., hiding loaned out players
        when picking a starting XI). Delegates the actual data traversal and filtering
        to `PlayerService.get_all_player_names`.

        Args:
            only_outfield (bool, optional): If True, excludes goalkeepers from the list.
                                            Defaults to False.
            only_gk (bool, optional): If True, strictly returns goalkeepers.
                                      Defaults to False.
            remove_on_loan (bool, optional): If True, hides players currently on loan
                                             from the list.
                                             Defaults to False.

        Returns:
            list[str]: A list of player names matching the specified UI criteria.
        """
        return self._player_service.get_all_player_names(
            only_outfield=only_outfield, only_gk=only_gk, remove_on_loan=remove_on_loan
        )

    def get_player_bio(self, name: str) -> PlayerBioDict | None:
        """Retrieve the static biographical details for a specific player.

        Used by UI frames (like LeftPlayerFrame or player profile views) to
        populate static information such as age, nationality, and overall rating.
        Delegates the exact data lookup to `PlayerService.get_player_bio`.

        Args:
            name (str): The exact registered name of the player to look up.

        Returns:
            PlayerBioDict | None: A strictly typed dictionary containing the bio, or
                                  None if the player doesn't exist in the active career.
        """
        return self._player_service.get_player_bio(name)

    # --- Player creation workflow (attributes to save) ---

    def process_player_attributes(
        self, is_goalkeeper: bool, is_first_page: bool
    ) -> None:
        """Process player attributes by executing the OCR workflow.

        Captures a screenshot, detects attribute statistics based on the player's
        position and page, and populates the corresponding UI frame with the results.

        Args:
            is_goalkeeper (bool): Identifies if the player is a goalkeeper.
            is_first_page (bool): If an outfield player, identifies if it's the first or
                          second page of attributes.

        Raises:
            UIPopulationError: If the capture, OCR detection, or UI population fails.
        """
        try:
            self._screenshot_service.capture_screenshot()
            latest_screenshot_path: Path = (
                self._screenshot_service.get_latest_screenshot_path()
            )
            stats: OCRStatsPayload = self._ocr_service.detect_player_attributes(
                latest_screenshot_path=latest_screenshot_path,
                is_goalkeeper=is_goalkeeper,
                is_first_page=is_first_page,
            )

            if is_goalkeeper:
                logger.info("Populating AddGKFrame with detected attributes.")
                target_frame: ctk.CTkFrame = self._frames[
                    self.get_frame_class("AddGKFrame")
                ]
            else:
                logger.info(
                    "Populating %s with detected attributes.",
                    "AddOutfieldFrame1" if is_first_page else "AddOutfieldFrame2",
                )
                target_frame: ctk.CTkFrame = self._frames[
                    self.get_frame_class(
                        "AddOutfieldFrame1" if is_first_page else "AddOutfieldFrame2"
                    )
                ]

            if isinstance(target_frame, StatsPopulatable):
                target_frame.populate_stats(stats)
            else:
                logger.error(
                    "%s is missing the 'populate_stats' method.",
                    target_frame.__class__.__name__,
                )
                raise UIPopulationError("Target UI frame cannot accept OCR attributes.")

        except Exception as e:
            # Log the technical trace for the developer
            logger.error(
                "Error processing player attributes (GK=%s, First=%s): %s",
                is_goalkeeper,
                is_first_page,
                e,
                exc_info=True,
            )
            # Re-raise to trigger a GUI warning popup
            raise UIPopulationError(
                f"Failed to extract player attributes from screen: {e}"
            ) from e

    def buffer_player_attributes(
        self,
        data: PlayerAttributePayload,
        is_goalkeeper: bool,
        is_first_page: bool = True,
    ) -> None:
        """Stage extracted player attributes in memory prior to a final save.

        Used by multi-page UI flows (like AddOutfieldFrame1 to AddOutfieldFrame2)
        to hold intermediate OCR data. This does NOT write to disk.

        Delegates to `BufferService.buffer_player_attributes` to handle the merging
        of multi-page payloads.

        Args:
            data (PlayerAttributePayload): Validated structure holding extracted stats.
            is_goalkeeper (bool): True if staging goalkeeper attributes.
            is_first_page (bool, optional): True if this is the first page of outfield
                                            attributes. Defaults to True.
        """
        self._buffer_service.buffer_player_attributes(
            data, is_goalkeeper, is_first_page
        )

    def save_player(self) -> None:
        """Commit fully buffered player data to persistent storage.

        Acts as the final submission step for player creation/updating UIs. It retrieves
        the aggregated state from the BufferService and delegates persistence and
        Pydantic validation to `PlayerService.save_player`.

        Crucially, the UI buffer is only cleared *after* a successful save. If the
        Service raises a validation error, the buffer remains intact so the user
        can correct their UI inputs without losing their progress.

        Raises:
            IncompleteDataError: If required buffered player data is missing.
            DataPersistenceError: If validation or persistence fails while
                saving the player.
        """
        buffered_player: BufferedPlayer = self._buffer_service.get_buffered_player()
        self._player_service.save_player(
            player_name=buffered_player.player_name,
            attributes=buffered_player.attributes,
            position=buffered_player.position,
            in_game_date=buffered_player.in_game_date,
            is_gk=buffered_player.is_goalkeeper,
        )
        # Reset buffer only after a successful save so users can retry on failure.
        self._buffer_service.reset_player_buffer()

    # --- Player status and events workflow ---

    def save_financial_data(
        self,
        player_name: str,
        financial_data: FinancialDataPayload,
        in_game_date: str,
    ) -> None:
        """Directly append or update a player's financial history on disk.

        Triggered by UI frames handling contract renewals, wage changes, or market
        value updates. Unlike player attributes, this data is not buffered and is
        written immediately.

        Delegates Pydantic validation and disk I/O to
        `PlayerService.save_financial_data`.

        Args:
            player_name (str): The exact registered name of the player.
            financial_data (FinancialDataPayload): Structured payload containing wage,
                                                   value, and contract details.
            in_game_date (str): The EA FC in-game date the financial change occurred.

        Raises:
            IncompleteDataError: If required financial context fields are missing.
            DataPersistenceError: If validation or persistence fails while
                saving financial data.
        """
        self._player_service.save_financial_data(
            player_name, financial_data, in_game_date
        )

    def add_injury_record(
        self,
        player_name: str,
        injury_data: InjuryDataPayload,
    ) -> None:
        """Append a new injury event to a player's medical history.

        Triggered by the AddInjuryFrame. Writing this data allows the UI to render
        injury indicators or track historical fitness trends. Delegates payload
        validation and disk I/O to `PlayerService.add_injury_record`.

        Args:
            player_name (str): The exact registered name of the player.
            injury_data (InjuryDataPayload): A strictly typed dictionary containing
                                             injury specifics (e.g., type, duration).

        Raises:
            IncompleteDataError: If required injury context fields are missing.
            DataPersistenceError: If validation or persistence fails while
                saving injury data.
        """
        self._player_service.add_injury_record(player_name, injury_data)

    def loan_out_player(self, player_name: str) -> None:
        """Update a player's status to indicate they are currently out on loan.

        Used by transfer management UI frames. Marking a player as loaned out
        ensures UI filters (like `get_all_player_names(remove_on_loan=True)`)
        correctly omit them from matchday squads. Delegates state mutation
        to `PlayerService.loan_out_player`.

        Args:
            player_name (str): The exact registered name of the player.

        Raises:
            IncompleteDataError: If no player name is provided.
            DataPersistenceError: If persistence fails while updating loan status.
        """
        self._player_service.loan_out_player(player_name)

    def return_loan_player(self, player_name: str) -> None:
        """Reinstate a loaned-out player back into the active squad.

        Triggered when a loan spell ends or is recalled via the UI. This restores
        the player's availability, allowing them to appear in match selections
        again. Delegates the state reversal to `PlayerService.return_loan_player`.

        Args:
            player_name (str): The exact registered name of the player.

        Raises:
            IncompleteDataError: If no player name is provided.
            DataPersistenceError: If persistence fails while restoring loan status.
        """
        self._player_service.return_loan_player(player_name)

    def sell_player(self, player_name: str, in_game_date: str) -> None:
        """Mark a player as sold and remove them from the active squad.

        Triggered by UI frames handling transfers. Calling this alters the player's
        internal status, which actively hides them from future selection widgets
        while preserving their historical stats. Delegates validation and disk
        updates to `PlayerService.sell_player`.

        Args:
            player_name (str): The exact registered name of the player.
            in_game_date (str): The EA FC in-game date the transfer occurred.

        Raises:
            IncompleteDataError: If required sell context fields are missing.
            DataPersistenceError: If persistence fails while marking the player sold.
        """
        self._player_service.sell_player(player_name, in_game_date)

    # --- Match logging workflow (overview to commit) ---

    def process_match_stats(self) -> None:
        """Process match statistics by orchestrating the OCR workflow.

        Captures a screenshot of the current screen, runs the detection algorithm
        configured for the match overview, and populates the MatchStatsFrame
        with the resulting data.

        Raises:
            UIPopulationError: If the screenshot, OCR, or frame population fails.
        """
        try:
            self._screenshot_service.capture_screenshot()
            latest_screenshot_path: Path = (
                self._screenshot_service.get_latest_screenshot_path()
            )
            stats: OCRStatsPayload = self._ocr_service.detect_stats(
                latest_screenshot_path=latest_screenshot_path,
                is_player=False,
            )

            match_stats_frame: ctk.CTkFrame = self._frames[
                self.get_frame_class("MatchStatsFrame")
            ]
            logger.info("Populating MatchStatsFrame with detected stats.")

            if isinstance(match_stats_frame, StatsPopulatable):
                match_stats_frame.populate_stats(stats)
            else:
                logger.error("MatchStatsFrame is missing the 'populate_stats' method.")
                raise UIPopulationError("Target UI frame cannot accept OCR stats.")

        except Exception as e:
            # Log the deep technical trace for the developer
            logger.error("Error processing match stats: %s", e, exc_info=True)
            # Re-raise as a specific GUI error so the frontend can display
            # a user-friendly popup.
            raise UIPopulationError(
                f"Failed to extract match stats from screen: {e}"
            ) from e

    def buffer_match_overview(self, overview_data: MatchOverviewPayload) -> None:
        """Stage the global match statistics in memory.

        Used as the first step in the match-logging UI flow. Staging this data
        allows the user to transition to the player-specific OCR screens without
        losing the overarching match result (e.g., score, possession).
        Delegates to `BufferService.buffer_match_overview`.

        Args:
            overview_data (MatchOverviewPayload): A strictly typed dictionary of
                                                  the OCR-extracted match overview.

        Raises:
            ValueError: If overview_data is not a dictionary-like payload.
        """
        self._buffer_service.buffer_match_overview(overview_data)

    def process_player_stats(self, is_goalkeeper: bool = False) -> None:
        """Process individual player match statistics via the OCR workflow.

        Captures a screenshot of the active screen, detects the player statistics
        based on their role (Goalkeeper vs Outfield), and routes the extracted data
        to the appropriate UI frame for user validation.

        Args:
            is_goalkeeper (bool): If True, processes stats for the GKStatsFrame.
                                  If False, processes stats for the PlayerStatsFrame.

        Raises:
            UIPopulationError: If the screenshot, OCR process, or frame
                population fails.
        """
        try:
            self._screenshot_service.capture_screenshot()
            latest_screenshot_path: Path = (
                self._screenshot_service.get_latest_screenshot_path()
            )
            stats: OCRStatsPayload = self._ocr_service.detect_stats(
                latest_screenshot_path=latest_screenshot_path,
                is_player=True,
                is_goalkeeper=is_goalkeeper,
            )

            if is_goalkeeper:
                logger.info("Populating GKStatsFrame with detected stats.")
                target_frame: ctk.CTkFrame = self._frames[
                    self.get_frame_class("GKStatsFrame")
                ]
            else:
                logger.info("Populating PlayerStatsFrame with detected stats.")
                target_frame: ctk.CTkFrame = self._frames[
                    self.get_frame_class("PlayerStatsFrame")
                ]

            if isinstance(target_frame, StatsPopulatable):
                target_frame.populate_stats(stats)
            else:
                logger.error(
                    "%s is missing the 'populate_stats' method.",
                    target_frame.__class__.__name__,
                )
                raise UIPopulationError("Target UI frame cannot accept OCR stats.")

        except Exception as e:
            # Log the technical trace for the developer
            logger.error(
                "Error processing player stats (GK=%s): %s",
                is_goalkeeper,
                e,
                exc_info=True,
            )
            # Re-raise to trigger a GUI warning popup
            raise UIPopulationError(
                f"Failed to extract player stats from screen: {e}"
            ) from e

    def buffer_player_performance(
        self, performance_data: PlayerPerformancePayload
    ) -> None:
        """Append a single player's match statistics to the current staged match.

        Used repeatedly in a loop by the UI as the user scans individual player
        stats post-match. The data is held in temporary memory until the entire
        match is submitted. Delegates to `BufferService.buffer_player_performance`.

        Args:
            performance_data (PlayerPerformancePayload): A strictly typed dictionary
                                                         of the player's OCR stats.

        Raises:
            ValueError: If performance_data is malformed or missing required keys.
            DuplicateRecordError: If the same player's performance is already
                staged in the buffer.
        """
        self._buffer_service.buffer_player_performance(performance_data)

    def get_buffered_player_performances(
        self, display_keys: list[str], id_key: str = "player_name", default: str = "-"
    ) -> DisplayRows:
        """Retrieve a formatted summary of all players currently staged for this match.

        Used by the UI to render a live-updating table (e.g., in MatchStatsFrame)
        showing the user exactly which players have been successfully scanned so far.
        Delegates the row formatting and key extraction to
        `BufferService.get_buffered_player_performances`.

        Args:
            display_keys (list[str]): The specific stats to extract for the UI columns.
            id_key (str, optional): The unique identifier key for the row.
                                    Defaults to "player_name".
            default (str, optional): Fallback string if a stat is missing.
                                     Defaults to "-".

        Returns:
            DisplayRows: A list of dictionaries pre-formatted for UI table consumption.
        """
        return self._buffer_service.get_buffered_player_performances(
            display_keys, id_key, default
        )

    def remove_player_from_buffer(self, player_name: str) -> None:
        """Delete a specific player's staged performance from the current match buffer.

        Triggered by UI 'Delete' or 'Retake' buttons in the staging table. It allows
        users to correct OCR mistakes for a single player without having to scrap
        and restart the entire match logging process. Delegates to
        `BufferService.remove_player_from_buffer`.

        Args:
            player_name (str): The exact name of the player to remove from the buffer.

        Raises:
            ValueError: If player_name is empty or invalid.
        """
        logger.info(
            "Received request to remove buffered player performance for: %s",
            player_name,
        )
        self._buffer_service.remove_player_from_buffer(player_name)
        logger.debug(
            "Completed buffered player removal request for: %s",
            player_name,
        )

    def get_match_review_context(
        self,
    ) -> tuple[
        MatchOverviewPayload,
        list[PlayerPerformancePayload],
        dict[str, dict[str, int | float]],
    ]:
        """Retrieve the current buffered data and discrepancies for manual review.

        This method is called by the `MatchReviewFrame` upon loading to populate
        its dynamically generated input grid.

        Returns:
            tuple: A three-item tuple containing the match overview dict,
                the list of player performance dicts, and the dictionary
                of currently flagged discrepancies.
        """
        buffered_match = self._buffer_service.get_buffered_match()
        return (
            buffered_match.match_overview,
            buffered_match.player_performances,
            self._current_discrepancies,
        )

    def submit_match_corrections(
        self,
        updated_overview: dict[str, int],
        updated_performances: dict[str, dict[str, int]],
    ) -> None:
        """Update the match buffers with manual corrections and re-attempt save.

        Args:
            updated_overview: A dictionary of corrected team total stats.
            updated_performances: A nested dictionary mapping each player's
                name in the buffer to their corrected stat values.

        Raises:
            DataDiscrepancyError: If the new manual inputs still do not
                satisfy the cohesion check.
        """
        logger.info("Applying manual corrections from MatchReviewFrame.")

        # Determine which side (home/away) belongs to our career team
        buffered: BufferedMatch = self._buffer_service.get_buffered_match()
        current_overview: MatchOverviewPayload = buffered.match_overview
        career_meta = self.get_current_career_details()
        career_team: str | None = getattr(career_meta, "club_name", None)

        # resolve whether our club is home or away for this buffered match
        home_team: str | None = current_overview.get("home_team_name")
        home_or_away: str = "home" if home_team == career_team else "away"

        # Build normalized overview updates that match
        # DataManager/MatchService expectations
        overview_updates: MatchOverviewPayload = {}
        # ensure we copy/merge existing stats dict so we don't clobber unrelated stats
        side_stats_key: str = f"{home_or_away}_stats"
        raw_side_stats: dict[str, int | float] = current_overview.get(
            side_stats_key, {}
        )
        existing_side_stats: dict[str, int | float] = (
            {
                key: value
                for key, value in raw_side_stats.items()
                if isinstance(key, str) and isinstance(value, (int, float))
            }
            if isinstance(raw_side_stats, dict)
            else {}
        )

        for stat, val in updated_overview.items():
            if stat == "goals":
                # goals map to the _score field
                overview_updates[f"{home_or_away}_score"] = val
            else:
                existing_side_stats[stat] = val

        # attach merged stats dict (only if we changed any stat)
        if existing_side_stats:
            overview_updates[side_stats_key] = cast(
                MatchStatsPayload, existing_side_stats
            )

        # 1. Update the match overview
        self._buffer_service.update_match_overview(overview_updates)

        # 2. Update each player using their name as the lookup key
        for player_name, stats in updated_performances.items():
            self._buffer_service.update_player_performance(player_name, stats)

        # 3. Re-attempt the save
        self.save_buffered_match(force_save=False)

    def cancel_match_review(self) -> None:
        """Abort the review process and return to the standard editing flow."""
        self._current_discrepancies.clear()

    def save_buffered_match(self, force_save: bool = False) -> None:
        """Commit the fully staged match and all associated player performances to disk.

        Acts as the final orchestrator for the match-logging UI wizard. It extracts the
        aggregated `BufferedMatch` state and delegates persistence, validation, and disk
        I/O to `MatchService.save_match`.

        Crucially, the UI buffer is only cleared *after* a successful save. If the
        Service raises a validation error (e.g., missing overview data), the buffer
        remains intact so the user does not lose their scanned OCR data.

        Raises:
            IncompleteDataError: If required buffered match data is missing.
            DataDiscrepancyError: If stat sums do not match overview totals and
                ``force_save`` is False.
            DataPersistenceError: If validation or persistence fails while
                saving the match.
        """
        buffered_match: BufferedMatch = self._buffer_service.get_buffered_match()
        match_overview: MatchOverviewPayload = buffered_match.match_overview
        player_performances: list[PlayerPerformancePayload] = (
            buffered_match.player_performances
        )
        career = self.get_current_career_details()
        half_length: int = getattr(career, "half_length", 10)
        team_name: str = getattr(career, "club_name", "Unknown Club")

        # Enrich each performance with our custom match rating before logging/saving
        for performance in player_performances:
            # Assuming the engine handles the position routing and returns a float
            rating = self._analytics_engine.calculate_match_rating(
                performance=performance,
                match_overview=match_overview,
                half_length=half_length,
                team_name=team_name,
            )
            # Append the rating rounded to 1 decimal place (e.g., 7.4)
            if isinstance(rating, (int, float)):
                performance["match_rating"] = round(rating, 1)
            else:
                performance["match_rating"] = None

        logger.info(
            "Committing buffered match (competition: %s, opponent: %s, "
            "performances: %s, force_save: %s).",
            match_overview.get("competition", "Unknown"),
            match_overview.get("away_team_name", "Unknown"),
            len(player_performances),
            force_save,
        )

        try:
            self._match_service.save_match(
                match_overview=match_overview,
                player_performances=player_performances,
                force_save=force_save,
            )

            logger.info("Buffered match committed successfully.")

            # Clear buffers and state only after a successful save
            self._current_discrepancies.clear()
            logger.debug("Clearing match buffers after successful save.")
            self._buffer_service.reset_match_buffers()

        except DataDiscrepancyError as e:
            # Cache the discrepancies in app.py so the review frame can fetch them
            self._current_discrepancies = e.discrepancies
            # Re-raise so the PlayerStatsFrame can catch it and show the popup
            raise e
