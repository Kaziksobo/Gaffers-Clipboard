import customtkinter as ctk
import time
import pyautogui
import json
import cv2 as cv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
from datetime import datetime

# Internal imports
from src import ocr
from src.theme import theme
from src.utils import get_screen_resolution, scale_coordinates
from src.exceptions import ScreenshotError, FrameNotFoundError, ConfigurationError, UIPopulationError, IncompleteDataError, DataPersistenceError, DuplicateRecordError
from src.data_manager import DataManager
from src.custom_types import CareerMetadata, DifficultyLevel, PlayerBioDict

# View imports
from src.views.career_select_frame import CareerSelectFrame
from src.views.create_career_frame import CreateCareerFrame
from src.views.main_menu_frame import MainMenuFrame
from src.views.add_match_frame import AddMatchFrame
from src.views.match_stats_frame import MatchStatsFrame
from src.views.player_stats_frame import PlayerStatsFrame
from src.views.match_added_frame import MatchAddedFrame
from src.views.player_library_frame import PlayerLibraryFrame
from src.views.add_gk_frame import AddGKFrame
from src.views.add_outfield_frame_1 import AddOutfieldFrame1
from src.views.add_outfield_frame_2 import AddOutfieldFrame2
from src.views.add_financial_frame import AddFinancialFrame
from src.views.left_player_frame import LeftPlayerFrame
from src.views.gk_stats_frame import GKStatsFrame
from src.views.add_injury_frame import AddInjuryFrame
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
        """The main application controller and root window for Gaffer's Clipboard.
    
        This class acts as the central orchestrator (the Controller in MVC) for the 
        entire application. It manages three primary responsibilities:
        
        1.  **Window Management:** Controls the root Tkinter window geometry and theming.
        2.  **View Routing:** Acts as a router holding all initialized UI frames in memory,
            allowing seamless switching between screens via `show_frame`.
        3.  **State & Data Orchestration:** Holds the active instance of the `DataManager` 
            and maintains temporary session buffers. It bridges the gap between raw UI 
            inputs (dictionaries) and the strict data layer (Pydantic models).
        """
        super().__init__()
        logger.info(f"Application starting up. Project root: {App.PROJECT_ROOT}")
        
        # Load CustomTkinter JSON theme
        theme_path = str(App.PROJECT_ROOT / "src" / "themes" / "dark.json")
        ctk.set_default_color_theme(theme_path)
        logger.info(f"Loaded CTk theme from: {theme_path}")
        
        # Set appearance mode
        ctk.set_appearance_mode("dark")
        
        # Window configuration
        self.title("Gaffer's Clipboard")
        self.geometry("1000x700")
        self.minsize(width=1000, height=700)
        
        self.theme = theme
        
        # Initialize dynamic fonts and bind to window resize for responsive scaling
        self.dynamic_fonts: Dict[str, ctk.CTkFont] = self._initialize_dynamic_fonts()
        self.bind("<Configure>", self._on_window_resize)
        self.fonts = self.dynamic_fonts
        
        # Set sidebar states
        self.sidebar_states = {
            "player_stats_sidebar": True,      # collapsed by default
            "gk_stats_sidebar": True,
        }
        
        # Initialize the data manager
        data_path = App.PROJECT_ROOT / "data"
        self.data_manager: DataManager = DataManager(data_path)
        
        self.current_career: Optional[str] = None
        
        # Buffers to allow data to be collected by multiple frames before entering into data manager
        self.player_attributes_buffer: Dict[str, Any] = {}
        self.match_overview_buffer: Dict[str, Any] = {}
        self.player_performances_buffer: list[Dict[str, Any]] = []
        
        self.full_competitions_list: list[str] = [
            "Premier League", "FA Cup", "EFL Cup", "Community Shield",
            "Ligue 1", "Coupe de France", "Trophée des Champions",
            "La Liga", "Copa del Rey", "Supercopa de España",
            "Bundesliga", "DFB-Pokal", "DFL-Supercup",
            "Serie A", "Coppa Italia", "Supercoppa Italiana",
            "UEFA Champions League", "UEFA Europa League", "UEFA Europa Conference League", "UEFA Super Cup"
        ]

        # Frame configuration
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        self.frames: Dict[Type[ctk.CTkFrame], ctk.CTkFrame] = {}
        
        for F in (CareerSelectFrame, CreateCareerFrame, MainMenuFrame, AddMatchFrame, 
                  MatchStatsFrame, PlayerStatsFrame, MatchAddedFrame, PlayerLibraryFrame, 
                  AddGKFrame, AddOutfieldFrame1, AddOutfieldFrame2, AddFinancialFrame, 
                  LeftPlayerFrame, GKStatsFrame, AddInjuryFrame):
            try:
                frame = F(container, self, self.theme)
                self.frames[F] = frame
                frame.grid(row=0, column=0, sticky="nsew")
            except Exception as e:
                logger.critical(f"Failed to initialize frame {F.__name__}: {e}")
                raise
        
        logger.info("Application initialized. Showing CareerSelectFrame.")
        self.show_frame(CareerSelectFrame)
        
    def get_frame_class(self, name: str) -> Type[ctk.CTkFrame]:
        """Retrieve a registered frame class by its string name.

        This method resolves circular import issues in the views by allowing
        frames to request navigation via string names instead of direct class imports.

        Args:
            name (str): The exact class name of the frame (e.g., "AddMatchFrame").

        Raises:
            FrameNotFoundError: If the requested frame name is not registered in the application.

        Returns:
            Type[ctk.CTkFrame]: The class reference for the requested frame.
        """
        for cls in self.frames:
            if cls.__name__ == name:
                return cls
        raise FrameNotFoundError(f"No frame class named '{name}' found.")
    
    def show_frame(self, page_class: Type[ctk.CTkFrame]) -> None:
        """Bring the specified frame class to the front of the UI stack.

        If the target frame implements an `on_show` method, it will be executed
        after the frame is raised. This acts as a lifecycle hook for views to 
        refresh data or clear buffers when they become active.

        Args:
            page_class (Type[ctk.CTkFrame]): The class reference of the frame to show.

        Raises:
            FrameNotFoundError: If the provided class is not registered in the application.
        """
        logger.info(f"Navigating to frame: {page_class.__name__}")
        
        if page_class not in self.frames:
            raise FrameNotFoundError(f"No frame class named '{page_class.__name__}' found.")
        
        frame = self.frames[page_class]
        frame.tkraise()
        
        # Trigger on_show lifecycle method if it exists for the frame
        if hasattr(frame, "on_show"):
            frame.on_show()
    
    def _initialize_dynamic_fonts(self) -> Dict[str, ctk.CTkFont]:
        live_fonts = {}
        for font_name, font_config in vars(self.theme.fonts).items():
            family = font_config[0]
            base_size = font_config[1]
            weight = font_config[2] if len(font_config) > 2 else "normal"

            live_fonts[font_name] = ctk.CTkFont(family=family, size=base_size, weight=weight)
            
        return live_fonts
    
    def _on_window_resize(self, event: Any) -> None:
        if event.widget == self and event.width > 100:
            scale_factor = max(0, (event.width - 800) / 40)
            
            self.dynamic_fonts["title"].configure(size=int(max(24, min(32 + scale_factor * 1.5, 64))))
            self.dynamic_fonts["button"].configure(size=int(max(14, min(16 + scale_factor * 0.5, 24))))
            self.dynamic_fonts["body"].configure(size=int(max(14, min(16 + scale_factor * 0.5, 22))))
            self.dynamic_fonts["sidebar_button"].configure(size=int(max(12, min(14 + scale_factor * 0.3, 18))))
            self.dynamic_fonts["sidebar_body"].configure(size=int(max(12, min(14 + scale_factor * 0.3, 18))))
    
    def get_sidebar_collapse_state(self, sidebar_id: str) -> bool:
        """Get collapse state for a sidebar. Defaults to True (collapsed)."""
        return self.sidebar_states.get(sidebar_id, True)

    def set_sidebar_collapse_state(self, sidebar_id: str, collapsed: bool) -> None:
        """Save collapse state for a sidebar."""
        self.sidebar_states[sidebar_id] = collapsed

    def has_unsaved_work(self) -> bool:
        """Check if there are any unsaved changes in the session buffers.
        
        Returns:
            bool: True if any of the buffers contain data, indicating potential unsaved work.
        """
        return bool(
            self.player_attributes_buffer
            or self.match_overview_buffer
            or self.player_performances_buffer
        )
        
    def clear_session_buffers(self) -> None:
        """Clear all session buffers."""
        logger.info("Clearing session buffers.")
        self.player_attributes_buffer = {}
        self.match_overview_buffer = {}
        self.player_performances_buffer = []

    def set_current_career_by_name(self, career_name: str) -> None:
        """Load the specified career and set it as the active context.

        This method orchestrates the DataManager to read the specific career's
        files, hydrates the player and match lists in memory, and updates the 
        application's active state.

        Args:
            career_name (str): The display name of the career (e.g., "Arsenal" 
                               or "Arsenal (Arteta)").
        """
        logger.info(f"Setting current career to: {career_name}")
        
        self.data_manager.load_career(career_name)
        self.data_manager.refresh_players()
        self.data_manager.refresh_matches()
        
        self.current_career = career_name
    
    def save_new_career(
        self, 
        club_name: str, 
        manager_name: str, 
        starting_season: str, 
        half_length: int, 
        match_difficulty: DifficultyLevel) -> None:
        """Create a new career profile and immediately activate it.

        This routes the initial settings to the DataManager for persistence,
        before setting the newly created career as the active context.

        Args:
            club_name (str): The club associated with the new career.
            manager_name (str): The manager controlling the career.
            starting_season (str): The season in which the career begins.
            half_length (int): The duration of each half in minutes.
            match_difficulty (DifficultyLevel): The strict difficulty level applied.
        """
        self.data_manager.create_new_career(
            club_name, manager_name, starting_season, half_length, match_difficulty
        )
        self.set_current_career_by_name(club_name)
    
    def get_current_career_details(self) -> Optional[CareerMetadata]:
        """Retrieve the metadata model for the currently active career.

        Returns:
            Optional[CareerMetadata]: The strictly typed Pydantic model containing 
                                      career details, or None if no career is loaded.
        """
        if not self.current_career:
            logger.warning("Attempted to get career details, but no career is active.")
            return None
            
        return self.data_manager.get_career_details(self.current_career)

    def get_latest_match_in_game_date(self) -> Optional[datetime]:
        """Return the most recent stored match in-game date for the active career.

        This delegates to the DataManager and returns None when no career or
        matches exist.
        """
        try:
            return self.data_manager.get_latest_match_in_game_date()
        except Exception as e:
            logger.debug(f"Failed to get latest match date from DataManager: {e}")
            return None
    
    def get_all_player_names(self, only_outfield: bool = False, only_gk: bool = False, remove_on_loan: bool = False) -> list[str]:
        """Retrieve a sorted list of active player names for UI dropdowns.

        Filters out players marked as 'sold'. Can optionally filter by 
        goalkeepers or outfield players using the Player model's properties.

        Args:
            only_outfield (bool): If True, excludes goalkeepers.
            only_gk (bool): If True, strictly returns goalkeepers.
            remove_on_loan (bool): If True, excludes players marked as on loan.

        Returns:
            List[str]: Alphabetically sorted list of player names (by surname). 
                       Returns ["No players found"] if the filtered list is empty.
        """
        # Ensure memory is synced with disk before building the list
        self.data_manager.refresh_players()
        
        if not self.data_manager.players:
            return ["No players found"]

        # Filter out sold players
        active_players = [
            player for player in self.data_manager.players
            if not player.sold and not (remove_on_loan and player.loaned)
        ]

        # Apply positional filters using the Player model's `is_goalkeeper` property
        if only_outfield:
            active_players = [player for player in active_players if not player.is_goalkeeper]
        elif only_gk:
            active_players = [player for player in active_players if player.is_goalkeeper]

        # Extract and sort player names by surname
        if active_players:
            return sorted(
                [player.name.title() for player in active_players], 
                key=lambda name: name.split()[-1]
            )
        else:
            return ["No players found"]

    def get_player_bio(self, name: str) -> Optional[PlayerBioDict]:
        """Retrieve the high-level details of a player by name for display in the UI.

        Args:
            name (str): The full name of the player (e.g., "John Doe") to look up.

        Returns:
            Optional[PlayerBioDict]: A dictionary containing the player's high-level details, or None if the player is not found.
        """
        player = self.data_manager._find_player_by_name(name)
        if player is None:
            return None
        return {
            "age": player.age,
            "height": player.height,
            "weight": player.weight,
            "country": player.nationality,
            "positions": player.positions,
        }

    def buffer_player_attributes(self, data: dict[str, Any], gk: bool, first: bool = True) -> None:
        """Store captured player attribute data during multi-step entry flows.

        This method routes raw data from goalkeeper and outfield pages into 
        their respective buffer slots. This data remains raw (unvalidated) 
        until the final save step pushes it across the Pydantic boundary in 
        the DataManager.

        Args:
            data (Dict[str, Any]): The raw attribute values collected from the UI or OCR.
            gk (bool): Indicates whether the data belongs to a goalkeeper.
            first (bool, optional): Distinguishes between the first and second 
                                    outfield attribute pages. Defaults to True.
        """
        logger.info(f"Buffering player data. GK: {gk}, First Page: {first}")
        
        if gk:
            self.player_attributes_buffer['gk_attr'] = data
        elif first:
            self.player_attributes_buffer['outfield_attr_1'] = data
        else:
            self.player_attributes_buffer['outfield_attr_2'] = data
    
    def save_player(self) -> None:
        """Commit buffered attribute data to persistent storage.

        This method reconciles goalkeeper and outfield inputs, merges multi-page 
        outfield attributes, and acts as the gatekeeper pushing raw UI dictionaries 
        across the Pydantic boundary into the DataManager.

        Raises:
            IncompleteDataError: If the buffers are incomplete or missing critical 
                                 context fields (name, position, in-game date) prior to save.
            DataPersistenceError: If the DataManager fails to save the player, 
                                  often due to validation errors or file I/O issues.
        """
        if not self.player_attributes_buffer:
            raise IncompleteDataError("Cannot save: No player data found in buffer.")
        
        # If gk, then only gk_attr will be present
        # If outfield first, then outfield_attr_1 and outfield_attr_2 will be present
        # in_game_date is always in the first page of attributes; season is derived from it
        
        player_name = ""
        position = ""
        in_game_date = ""
        attributes: dict[str, Any] = {}
        
        if 'gk_attr' in self.player_attributes_buffer:
            gk_data = self.player_attributes_buffer['gk_attr']
            player_name = gk_data.get('name', '').strip()
            position = 'GK'
            in_game_date = gk_data.get('in_game_date', '').strip()
            attributes = gk_data
            
        elif 'outfield_attr_1' in self.player_attributes_buffer and 'outfield_attr_2' in self.player_attributes_buffer:
            out_1 = self.player_attributes_buffer['outfield_attr_1']
            out_2 = self.player_attributes_buffer['outfield_attr_2']
            player_name = out_1.get('name', '').strip()
            position = out_1.get('position') or None
            in_game_date = out_1.get('in_game_date', '').strip()
            
            # Safely merge both pages of attributes
            attributes = {**out_1, **out_2}
        
        else:
            raise IncompleteDataError("Cannot save: Missing page 1 or page 2 of outfield attributes.")
        
        if not player_name or not in_game_date:
            logger.error(f"Save aborted: Missing critical context. Name: '{player_name}', Date: '{in_game_date}'")
            raise IncompleteDataError("Cannot save: Missing required player context fields (Name or In-game Date).")
        
        logger.info(f"Saving player {player_name} at position {position}")
        
        is_gk = 'gk_attr' in self.player_attributes_buffer
        try:
            self.data_manager.add_or_update_player(
                player_ui_data=attributes,
                position=position,
                in_game_date=in_game_date,
                is_gk=is_gk
            )
        except Exception as e:
            # We catch the generic exception (like a Pydantic ValidationError) 
            # and wrap it in our custom DataPersistenceError for the UI to handle.
            logger.error(f"DataManager failed to save player '{player_name}': {e}", exc_info=True)
            raise DataPersistenceError(f"Failed to save player data to the database: {e}") from e
        finally:
            # Reset buffer after saving
            self.player_attributes_buffer = {}
    
    def save_financial_data(self, player_name: str, financial_data: dict[str, Any], in_game_date: str) -> None:
        """Commit the financial data for a specific player to persistent storage.
        
        Acts as the gatekeeper for monetary updates, ensuring the UI has provided 
        the necessary context before passing the raw dictionary to the DataManager 
        for Pydantic validation.

        Args:
            player_name (str): The name of the player to update.
            financial_data (Dict[str, Any]): The raw monetary details supplied by the UI.
            in_game_date (str): The in-game date for the financial snapshot.
            
        Raises:
            IncompleteDataError: If the player name, in-game date, or data dictionary is missing.
            DataPersistenceError: If the backend fails to process or save the data.
        """
        # Validate critical context before hitting the DataManager
        if not player_name or not player_name.strip():
            logger.error("Financial save aborted: Player name is missing.")
            raise IncompleteDataError("Cannot save: No player selected.")

        if not financial_data:
            logger.error(f"Financial save aborted: No data provided for {player_name}.")
            raise IncompleteDataError("Cannot save: Financial data fields are empty.")
        
        if not in_game_date or not in_game_date.strip():
            logger.error("Financial save aborted: In-game date is missing.")
            raise IncompleteDataError("Cannot save: In-game date is required.")

        logger.info(f"Initiating financial save for player '{player_name}'")
        try:
            self.data_manager.add_financial_data(player_name, financial_data, in_game_date)
        except Exception as e:
            logger.error(f"Failed to persist financial data for {player_name}: {e}", exc_info=True)
            raise DataPersistenceError(
                f"Backend failed to save financial data: {e}"
            ) from e
    
    def sell_player(self, player_name: str, in_game_date: str) -> None:
        """Mark a player as sold, permanently removing them from active squad selection.

        Args:
            player_name (str): The name of the player to sell.
            in_game_date (str): The in-game date for the sale.
        Raises:
            IncompleteDataError: If the player name or in-game date are missing or empty.
        """
        if not player_name or not player_name.strip():
            logger.error("Sell action aborted: No player name provided.")
            raise IncompleteDataError("Cannot sell: No player selected.")
        if not in_game_date or not in_game_date.strip():
            logger.error("Sell action aborted: No in-game date provided.")
            raise IncompleteDataError("Cannot sell: In-game date is required.")
            
        logger.info(f"Routing sell request for player: {player_name}")
        self.data_manager.sell_player(player_name, in_game_date)
    
    def loan_out_player(self, player_name: str) -> None:
        """Mark a player as loaned out, temporarily removing them from active squad selection.

        Args:
            player_name (str): The name of the player to loan out.

        Raises:
            IncompleteDataError: If the player name is missing or empty.
        """
        if not player_name or not player_name.strip():
            logger.error("Loan out action aborted: No player name provided.")
            raise IncompleteDataError("Cannot loan out: No player selected.")

        logger.info(f"Routing loan out request for player: {player_name}")
        self.data_manager.loan_out_player(player_name)
    
    def return_loan_player(self, player_name: str) -> None:
        """Mark a player as returned from loan, reinstating them to the active squad.

        Args:
            player_name (str): The name of the player returning from loan.

        Raises:
            IncompleteDataError: If the player name is missing or empty.
        """
        if not player_name or not player_name.strip():
            logger.error("Return loan action aborted: No player name provided.")
            raise IncompleteDataError("Cannot return from loan: No player selected.")

        logger.info(f"Routing return from loan request for player: {player_name}")
        self.data_manager.return_loan_player(player_name)
    
    def add_injury_record(self, player_name: str, injury_data: Dict[str, Any]) -> None:
        """Commit an injury record for a specific player to persistent storage.
        
        Acts as the gatekeeper for injury updates, ensuring the UI has provided 
        the necessary context before passing the raw dictionary to the DataManager 
        for strict Pydantic validation (which enforces date formats and literal enums).

        Args:
            player_name (str): The name of the player who sustained the injury.
            injury_data (Dict[str, Any]): The raw injury details (date, duration, type) from the UI.
            
        Raises:
            IncompleteDataError: If the player name or data dictionary is missing.
            DataPersistenceError: If the backend fails to validate (e.g., bad date format) or save the data.
        """
        # 1. Validate critical context before hitting the DataManager
        if not player_name or not player_name.strip():
            logger.error("Injury save aborted: Player name is missing.")
            raise IncompleteDataError("Cannot save injury: No player selected.")
            
        if not injury_data:
            logger.error(f"Injury save aborted: No data provided for {player_name}.")
            raise IncompleteDataError("Cannot save injury: Injury data fields are empty.")

        logger.info(f"Initiating injury record save for player '{player_name}'")
        
        # 2. Cross the Pydantic Boundary
        try:
            self.data_manager.add_injury_record(player_name, injury_data)
        except Exception as e:
            # We explicitly mention date formatting in the error wrap because 
            # that is the #1 reason this specific Pydantic model will fail.
            logger.error(f"Failed to persist injury data for {player_name}: {e}", exc_info=True)
            raise DataPersistenceError(
                f"Backend failed to save injury data. Please check date formatting (dd/mm/yy): {e}"
            ) from e
    
    def process_match_stats(self) -> None:
        """Process match statistics by orchestrating the OCR workflow.

        Captures a screenshot of the current screen, runs the detection algorithm 
        configured for the match overview, and populates the MatchStatsFrame 
        with the resulting data.

        Raises:
            UIPopulationError: If the screenshot, OCR, or frame population fails.
        """
        try:
            self._capture_screenshot()

            stats: Dict[str, Any] = self._detect_stats(is_it_player=False)

            match_stats_frame = self.frames[self.get_frame_class("MatchStatsFrame")]
            logger.info("Populating MatchStatsFrame with detected stats.")

            if hasattr(match_stats_frame, "populate_stats"):
                match_stats_frame.populate_stats(stats)
            else:
                logger.error("MatchStatsFrame is missing the 'populate_stats' method.")
                raise UIPopulationError("Target UI frame cannot accept OCR stats.")

        except Exception as e:
            # Log the deep technical trace for the developer
            logger.error(f"Error processing match stats: {e}", exc_info=True)
            # Re-raise as a specific GUI error so the frontend can display a user-friendly popup
            raise UIPopulationError(
                f"Failed to extract match stats from screen: {e}"
            ) from e
    
    def process_player_stats(self, gk: bool = False) -> None:
        """Process individual player match statistics via the OCR workflow.

        Captures a screenshot of the active screen, detects the player statistics 
        based on their role (Goalkeeper vs Outfield), and routes the extracted data 
        to the appropriate UI frame for user validation.

        Args:
            gk (bool): If True, processes stats for the GKStatsFrame. 
                       If False, processes stats for the PlayerStatsFrame.

        Raises:
            UIPopulationError: If the screenshot, OCR process, or frame population fails.
        """
        try:
            self._capture_screenshot()
            
            stats: Dict[str, Any] = self._detect_stats(is_it_player=True, gk=gk)
            
            if gk:
                logger.info("Populating GKStatsFrame with detected stats.")
                target_frame = self.frames[self.get_frame_class("GKStatsFrame")]
            else:
                logger.info("Populating PlayerStatsFrame with detected stats.")
                target_frame = self.frames[self.get_frame_class("PlayerStatsFrame")]
            
            if hasattr(target_frame, "populate_stats"):
                target_frame.populate_stats(stats)
            else:
                logger.error(f"{target_frame.__class__.__name__} is missing the 'populate_stats' method.")
                raise UIPopulationError("Target UI frame cannot accept OCR stats.")
        
        except Exception as e:
            # Log the technical trace for the developer
            logger.error(f"Error processing player stats (GK={gk}): {e}", exc_info=True)
            # Re-raise to trigger a GUI warning popup
            raise UIPopulationError(f"Failed to extract player stats from screen: {e}") from e
        
    def process_player_attributes(self, gk: bool, first: bool) -> None:
        """Process player attributes by executing the OCR workflow.

        Captures a screenshot, detects attribute statistics based on the player's 
        position and page, and populates the corresponding UI frame with the results.

        Args:
            gk (bool): Identifies if the player is a goalkeeper.
            first (bool): If an outfield player, identifies if it's the first or 
                          second page of attributes.

        Raises:
            UIPopulationError: If the capture, OCR detection, or UI population fails.
        """
        try:
            self._capture_screenshot()
            
            stats: Dict[str, Any] = self._detect_player_attributes(gk=gk, first=first)
            
            if gk:
                logger.info("Populating AddGKFrame with detected attributes.")
                target_frame = self.frames[self.get_frame_class("AddGKFrame")]
            else:
                logger.info(f"Populating {'AddOutfieldFrame1' if first else 'AddOutfieldFrame2'} with detected attributes.")
                target_frame = self.frames[self.get_frame_class("AddOutfieldFrame1" if first else "AddOutfieldFrame2")]
            
            if hasattr(target_frame, "populate_stats"):
                target_frame.populate_stats(stats)
            else:
                logger.error(f"{target_frame.__class__.__name__} is missing the 'populate_stats' method.")
                raise UIPopulationError("Target UI frame cannot accept OCR attributes.")
        
        except Exception as e:
            # Log the technical trace for the developer
            logger.error(f"Error processing player attributes (GK={gk}, First={first}): {e}", exc_info=True)
            # Re-raise to trigger a GUI warning popup
            raise UIPopulationError(f"Failed to extract player attributes from screen: {e}") from e
    
    def _capture_screenshot(self, delay: int | None = None) -> None:
        """Capture a screenshot of the display after a specified delay.

        Temporarily halts execution to allow the user to bring the EA FC 
        window to the foreground, captures the screen, and stores the resulting 
        file path in the application state.

        Args:
            delay (Optional[int]): The delay in seconds before capture. 
                                   Defaults to App.DEFAULT_SCREENSHOT_DELAY.

        Raises:
            ScreenshotError: If the screenshot capture or file save fails.
        """
        if delay is None:
            delay = App.DEFAULT_SCREENSHOT_DELAY

        logger.info(f"Initiating screenshot (delay: {delay}s)")
        # Force Tkinter to flush any pending graphical updates (like button releases) 
        # before we freeze the main thread with time.sleep.
        self.update()
        self._non_blocking_delay(
            seconds=delay, message="Switch to the game screen now"
        )

        capture_folder = App.PROJECT_ROOT / "screenshots"
        capture_folder.mkdir(parents=True, exist_ok=True)

        filename = f"stats_capture_{int(time.time())}.png"
        self.screenshot_path = capture_folder / filename

        try:
            pyautogui.screenshot(self.screenshot_path)
            logger.info(f"Screenshot saved: {self.screenshot_path}")
            self._cleanup_screenshots()
        except Exception as e:
            logger.error(f"Screenshot engine failed: {e}", exc_info=True)
            raise ScreenshotError(f"Failed to capture screenshot: {e}") from e
    
    def _non_blocking_delay(self, seconds: int, message: str = "Please wait...") -> None:
        """Display a modal overlay with a spinner message while the application processes events.

        Creates a temporary borderless popup window centered over the main application window.
        The popup shows a custom message and an animated spinner for the specified duration.
        Unlike a blocking sleep, this method allows the Tkinter event loop to continue processing,
        keeping the UI responsive (e.g., window repaint, button clicks) while waiting.

        Args:
            seconds (int): The duration to display the overlay, in seconds.
            message (str, optional): The text message to display. Defaults to "Please wait...".

        Note:
            This is primarily used to give the user time to switch to the game window
            before the application captures a screenshot.
        """
        
        # Delegate to widget helper (keeps behavior unchanged)
        show_delay_overlay(self, seconds, message)

    def _get_latest_screenshot_path(self) -> Path:
        """Retrieve the file path of the most recently captured screenshot.

        Scans the dedicated screenshots directory and returns the absolute path 
        to the newest file based on its modification timestamp.

        Raises:
            ScreenshotError: If the directory does not exist or contains no screenshots.

        Returns:
            Path: The absolute path to the latest screenshot file.
        """
        screenshots_dir = App.PROJECT_ROOT / "screenshots"
        
        if not screenshots_dir.exists():
            logger.error(f"Screenshot lookup failed: Directory missing at {screenshots_dir}")
            raise ScreenshotError("Screenshots directory does not exist.")

        if screenshot_files := list(screenshots_dir.glob("stats_capture_*.png")):
            latest_file = max(screenshot_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"Latest screenshot identified: {latest_file.name}")
            return latest_file
        
        logger.error(f"Screenshot lookup failed: No valid images found in {screenshots_dir}")
        raise ScreenshotError("No screenshots found in the screenshots directory.")
    
    def _cleanup_screenshots(self, max_files: int = 5) -> None:
        """Keep the screenshots directory tidy by retaining only the most recent captures.

        Scans the screenshots directory for files generated by the application 
        and deletes the oldest files, keeping only the 'max_files' most recent. 
        Errors during individual file deletion are caught and logged as warnings 
        to prevent background cleanup from crashing the main application thread.

        Args:
            max_files (int): The maximum number of recent screenshots to retain. 
                             Defaults to 5.
        """
        screenshots_dir = App.PROJECT_ROOT / "screenshots"
        if not screenshots_dir.exists():
            return
        
        # Get all screenshot files
        screenshot_files = list(screenshots_dir.glob("stats_capture_*.png"))
        
        # Sort files by modification time (newest first)
        screenshot_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Identify files to delete (everything after the first max_files)
        files_to_delete = screenshot_files[max_files:]
        
        if not files_to_delete:
            return
        
        logger.info(f"Cleanup: Deleting {len(files_to_delete)} old screenshots.")
        for file_path in files_to_delete:
            try:
                file_path.unlink()
                logger.debug(f"Deleted old screenshot: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete screenshot {file_path}. It may be in use: {e}")
    
    def _detect_stats(self, is_it_player: bool, gk: bool = False) -> dict[str, Any]:
        """Detect and extract statistics from the latest screenshot using OCR.

        Loads ROI (Region of Interest) coordinates from the JSON config, maps 
        them based on the requested context (match overview, outfield player, 
        or goalkeeper), and runs the OCR model against the latest screenshot.

        Args:
            is_it_player (bool): True if extracting individual player stats, 
                                 False for team match overview stats.
            gk (bool, optional): True if extracting goalkeeper stats. Defaults to False.

        Raises:
            ConfigurationError: If the coordinates JSON is missing or corrupt.
            ScreenshotError: If the screenshot cannot be loaded by OpenCV.

        Returns:
            Dict[str, Any]: A dictionary containing the strictly typed detected statistics.
        """
        logger.info(f"Starting OCR (player mode: {is_it_player})")
        latest_screenshot_path = self._get_latest_screenshot_path()

        # --- 1. Load Configurations ---
        coordinates_path = App.PROJECT_ROOT / "config" / "coordinates.json"
        if not coordinates_path.exists():
            raise ConfigurationError("Coordinates configuration file is missing.")
    
        try:
            with open(coordinates_path, 'r') as f:
                raw_coordinates = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError("Coordinates configuration file is corrupt.") from e

        # Scale normalised 0-1 coordinates to absolute pixels for the current screen
        screen_w, screen_h = get_screen_resolution()
        coordinates = scale_coordinates(raw_coordinates, screen_w, screen_h)

        # --- 2. Initialize Engine & Load Image ---
        ocr_model = ocr.load_ocr_model()
        screenshot_image = cv.imread(str(latest_screenshot_path))
        
        if screenshot_image is None:
            raise ScreenshotError(f"OpenCV failed to decode image at {latest_screenshot_path}. File may be corrupted or locked.")

        decimal_stats = ['xG', 'distance_covered', 'distance_sprinted']
        debug = False
        results: Dict[str, Any] = {}
        
        # --- 3. Determine Target Screen ---
        if not is_it_player:
            target_screen = "match_overview"
        elif gk:
            target_screen = "gk_performance"
        else:
            target_screen = "player_performance"
        
        screen_data = coordinates.get(target_screen)
        if not screen_data:
            logger.warning(f"No coordinates found in JSON for screen: '{target_screen}'")
            return results

        logger.debug(f"Processing target screen: {target_screen}")
        
        # --- 4. Reusable OCR Execution Engine ---
        def process_roi_dict(data_dict: Dict[str, Any]) -> Dict[str, Any]:
            """Helper function to run OCR on a flat dictionary of stat coordinates."""
            parsed_data = {}
            for stat_name, roi in data_dict.items():
                stat_roi = (roi['x1'], roi['y1'], roi['x2'], roi['y2'])
                logger.debug(f"OCRing {stat_name} at {stat_roi}")
                
                recognised_data = ocr.recognise_number(
                    full_screenshot=screenshot_image,
                    roi=stat_roi,
                    ocr_model=ocr_model,
                    debug=debug
                )
                
                recognised_number = recognised_data[0] if debug else recognised_data
                
                # ocr.recognise_number returns number as a string with no decimal point, e.g. 0.5 is returned as 05, 
                # convert it to a float if in decimal stats otherwise convert to int
                if stat_name in decimal_stats:
                    try:
                        parsed_data[stat_name] = float(recognised_number) / 10
                    except ValueError:
                        logger.warning(f"Failed to parse decimal stat '{stat_name}' from OCR output '{recognised_number}'. Defaulting to 0.0.")
                        parsed_data[stat_name] = 0.0
                else:
                    try:
                        parsed_data[stat_name] = int(recognised_number)
                    except ValueError:
                        logger.warning(f"Failed to parse integer stat '{stat_name}' from OCR output '{recognised_number}'. Defaulting to 0.")
                        parsed_data[stat_name] = 0
            
            return parsed_data

        # --- 5. Route and Execute ---
        # Match overview has nested dictionaries (home vs away team), while player stats are flat
        if target_screen == "match_overview":
            for team_name, team_data in screen_data.items():
                logger.debug(f"Processing team: {team_name}")
                results[team_name] = process_roi_dict(team_data)
        else:
            results = process_roi_dict(screen_data)

        return results
    
    def _detect_player_attributes(self, gk: bool = False, first: bool = True) -> dict[str, Any]:
        """Detect and extract player attribute statistics from the latest screenshot.

        Loads coordinates based on player position and page, processes the screenshot 
        using customized OCR preprocessing (e.g., erosion for colored text), and 
        safely casts all recognized values to integers for Pydantic compatibility.

        Args:
            gk (bool, optional): If True, processes goalkeeper attributes. Defaults to False.
            first (bool, optional): If True, processes the first page of the outfield 
                                    player's attributes. Defaults to True.

        Raises:
            ConfigurationError: If the coordinates JSON is missing or corrupt.
            ScreenshotError: If the screenshot cannot be loaded by OpenCV.

        Returns:
            Dict[str, Any]: A dictionary mapping attribute names to their parsed integer values.
        """
        logger.info(f"Starting Attribute OCR (GK: {gk}, First Page: {first})")
        latest_screenshot_path = self._get_latest_screenshot_path()

        # --- 1. Load Configurations ---
        coordinates_path = App.PROJECT_ROOT / "config" / "coordinates.json"
        if not coordinates_path.exists():
            raise ConfigurationError("Coordinates configuration file is missing.")
        
        try:
            with open(coordinates_path, 'r') as f:
                raw_coordinates = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Coordinates configuration file is corrupt: {e}") from e

        # Scale normalised 0-1 coordinates to absolute pixels for the current screen
        screen_w, screen_h = get_screen_resolution()
        coordinates = scale_coordinates(raw_coordinates, screen_w, screen_h)

        # --- 2. Initialize Engine & Load Image ---
        ocr_model = ocr.load_ocr_model()
        screenshot_image = cv.imread(str(latest_screenshot_path))
        
        if screenshot_image is None:
            raise ScreenshotError(f"OpenCV failed to decode image at {latest_screenshot_path}. File may be corrupted.")
        
        debug = False
        results: Dict[str, Any] = {}
        
        # --- 3. O(1) Dictionary Targeting ---
        # Navigate directly to the required node instead of looping through items
        target_position = "gk" if gk else "outfield_1" if first else "outfield_2"
        
        # Safely drill down. If 'player_attributes' or the target_position is missing, return empty dict
        target_stats = coordinates.get("player_attributes", {}).get(target_position, {})
        
        if not target_stats:
            logger.warning(f"No OCR coordinates found for player attributes -> {target_position}")
            return results
        
        # --- 4. Execute OCR and Safe Casting ---
        for stat_name, roi in target_stats.items():
            stat_roi = (roi['x1'], roi['y1'], roi['x2'], roi['y2'])
            logger.debug(f"OCR'ing {stat_name} at {stat_roi}")
            
            recognised_data = ocr.recognise_number(
                full_screenshot=screenshot_image,
                roi=stat_roi,
                ocr_model=ocr_model,
                preprocess_args={'erode_iterations': 1},
                debug=debug
            )
            
            # Safely extract string from debug tuple if necessary
            raw_value = recognised_data[0] if debug else recognised_data
            
            # Safely cast to integer to satisfy Pydantic models
            try:
                results[stat_name] = int(raw_value)
            except ValueError:
                logger.warning(f"Failed to parse attribute '{stat_name}' from OCR output '{raw_value}'. Defaulting to 0.")
                results[stat_name] = 0

        return results
    
    def buffer_match_overview(self, overview_data: dict[str, Any]) -> None:
        """Store captured match overview data in the temporary session buffer.

        Args:
            overview_data (Dict[str, Any]): The team statistics and match details 
                                            collected from the UI or OCR.
        """
        logger.info("Buffering match overview data.")
        self.match_overview_buffer = overview_data
    
    def buffer_player_performance(self, performance_data: dict[str, Any]) -> None:
        """Store a single player's match performance in the temporary session buffer.

        This method is designed to be called multiple times per match to build up 
        a roster of performances before the final save.

        Args:
            performance_data (Dict[str, Any]): The individual player stats collected 
                                               from the UI or OCR.
        """
        logger.info(f"Buffering player performance data for: {performance_data.get('player_name', 'Unknown')}")
        # Check if data for this player has already been buffered
        for dataset in self.player_performances_buffer:
            if dataset.get('player_name') == performance_data.get('player_name'):
                logger.error(f"Duplicate player performance detected for {performance_data.get('player_name')}. Each player's performance should only be buffered once per match.")
                raise DuplicateRecordError(performance_data.get('player_name'))
                
        self.player_performances_buffer.append(performance_data)
    
    def get_buffered_player_performances(self, display_keys: List[str], id_key: str = "player_name", default: str = "-") -> List[Dict[str, str]]:
        """Format the buffered player performance data for display in the UI, ensuring all required keys are present.

        Produces display-ready dictionaries from ``player_performances_buffer``.
        Includes ``id_key`` plus keys in ``display_keys``; all values become strings.
        Lists are joined with ", ", missing/falsy values use ``default``.
        Entries missing ``id_key`` are skipped; GK entries set ``positions_played`` to "GK".

        Args:
            display_keys (List[str]): The list of keys to include in the formatted output for the UI. This should match the columns expected by the display component.
            id_key (str, optional): The key to use as the identifier for each player's performance. Defaults to "player_name".
            default (str, optional): The default value to use if a required key is missing. Defaults to "-".

        Returns:
            List[Dict[str, str]]: A list of dictionaries, each representing a player's performance with stringified values for display. 
                Only entries that contain the required id_key will be included; others will be logged and skipped.
        """
        formatted_performances = []
        for performance in self.player_performances_buffer:
            formatted_performance = {id_key: str(performance.get(id_key, default))}
            if formatted_performance[id_key] == default:
                logger.warning(f"Buffered performance data is missing the required id_key '{id_key}'. This entry will be skipped in display. Data: {performance}")
                continue
            for key in display_keys:
                if key == id_key:
                    continue
                if performance.get("performance_type") == "gk" and key == "positions_played":
                    formatted_performance[key] = "GK"
                    continue
                value = performance.get(key, default) or default
                if isinstance(value, list):
                    formatted_performance[key] = ", ".join(str(v) for v in value)
                else:
                    formatted_performance[key] = str(value)
            formatted_performances.append(formatted_performance)
        
        return formatted_performances
    
    def remove_player_from_buffer(self, player_name: str) -> None:
        """Remove a player's performance data from the buffer based on their name.

        This is used when a user decides to delete a buffered performance entry 
        before saving the match. It identifies the entry by the player's name 
        and removes it from the list of buffered performances.

        Args:
            player_name (str): The name of the player whose performance data should be removed from the buffer.
        """
        original_count = len(self.player_performances_buffer)
        self.player_performances_buffer = [
            performance for performance in self.player_performances_buffer 
            if performance.get("player_name") != player_name
        ]
        if len(self.player_performances_buffer) < original_count:
            logger.info(f"Removed buffered performance for player: {player_name}")
        else:
            logger.warning(f"No buffered performance found for player: {player_name}. No entries removed.")
    
    def save_buffered_match(self) -> None:
        """Commit the buffered match overview and player performances to persistent storage.

        Acts as the gatekeeper for match data, ensuring the core overview exists 
        before pushing the raw dictionaries across the Pydantic boundary.

        Raises:
            IncompleteDataError: If the match overview buffer is empty.
            DataPersistenceError: If the DataManager fails to validate or save the match.
        """
        if not self.match_overview_buffer:
            logger.error("Match save aborted: Match overview buffer is empty.")
            raise IncompleteDataError("Cannot save match: Missing match overview data.")

        logger.info(
            f"Saving match to database. Overview present, "
            f"with {len(self.player_performances_buffer)} player performances."
        )

        try:
            self.data_manager.add_match(
                match_data=self.match_overview_buffer,
                player_performances=self.player_performances_buffer
            )
        except Exception as e:
            # Catch backend Pydantic validation errors (e.g., tackles_won > tackles)
            logger.error(f"DataManager failed to save match: {e}", exc_info=True)
            raise DataPersistenceError(f"Failed to save match data: {e}") from e
        finally:
            # 3. Always clear the buffers to prevent data leaking into the next match
            logger.debug("Clearing match buffers.")
            self.match_overview_buffer.clear()
            self.player_performances_buffer.clear()
    