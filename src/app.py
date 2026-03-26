import customtkinter as ctk
import time
import pyautogui
import json
import cv2 as cv
import logging
from pathlib import Path
from typing import Optional, Type, Any
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
from src.views.career_config_frame import CareerConfigFrame
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
        """Initialize the application controller and main window.

        Creates the root CustomTkinter window, applies the app theme and appearance mode,
        initializes responsive fonts and sidebar state, sets up the data manager and
        session buffers, and instantiates the application frames.
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
        self.dynamic_fonts: dict[str, ctk.CTkFont] = self._initialize_dynamic_fonts()
        self.bind("<Configure>", self._on_window_resize)
        self.fonts = self.dynamic_fonts
        
        # Set sidebar states
        self.sidebar_states = {
            "player_stats_sidebar": True,
            "gk_stats_sidebar": True,
        }
        
        # Initialize the data manager
        data_path = App.PROJECT_ROOT / "data"
        self.data_manager: DataManager = DataManager(data_path)
        
        self.current_career: Optional[str] = None
        
        # Buffers to allow data to be collected by multiple frames 
        # before entering into data manager
        self.player_attributes_buffer: dict[str, Any] = {}
        self.match_overview_buffer: dict[str, Any] = {}
        self.player_performances_buffer: list[dict[str, Any]] = []

        # Frame configuration
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        self.frames: dict[Type[ctk.CTkFrame], ctk.CTkFrame] = {}
        
        for frame_cls in (CareerSelectFrame, CreateCareerFrame, MainMenuFrame, 
                          AddMatchFrame, MatchStatsFrame, PlayerStatsFrame, 
                          MatchAddedFrame, PlayerLibraryFrame, AddGKFrame, 
                          AddOutfieldFrame1, AddOutfieldFrame2, AddFinancialFrame, 
                          LeftPlayerFrame, GKStatsFrame, AddInjuryFrame, 
                          CareerConfigFrame
                         ):
            try:
                frame = frame_cls(container, self, self.theme)
                self.frames[frame_cls] = frame
                frame.grid(row=0, column=0, sticky="nsew")
            except Exception as e:
                logger.critical(f"Failed to initialize frame {frame_cls.__name__}: {e}")
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
        """Raise the requested frame and run its lifecycle hooks.

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

        # Trigger a refresh of semantic styles if the frame supports it
        if hasattr(frame, "refresh_semantic_styles"):
            frame.refresh_semantic_styles()
        
        # Trigger on_show lifecycle method if it exists for the frame
        if hasattr(frame, "on_show"):
            frame.on_show()
    
    def _initialize_dynamic_fonts(self) -> dict[str, ctk.CTkFont]:
        """Create live, resizable font instances from the theme configuration.

        This converts the static font settings defined in the theme into
        `CTkFont` objects that can be dynamically adjusted at runtime.

        Returns:
            dict[str, ctk.CTkFont]: A mapping of theme font keys to live `CTkFont` instances.
        """
        live_fonts: dict[str, ctk.CTkFont] = {}
        # We expect the theme fonts to be defined as tuples: (family, size, [weight])
        for font_name, font_config in vars(self.theme.fonts).items():
            family = font_config[0]
            base_size = font_config[1]
            weight = font_config[2] if len(font_config) > 2 else "normal"

            live_fonts[font_name] = ctk.CTkFont(
                family=family, 
                size=base_size, 
                weight=weight
                )
            
        return live_fonts
    
    def _on_window_resize(self, event: Any) -> None:
        """Dynamically adjust application font sizes in response to window resizing.

        This keeps text readable and proportionally scaled across different window 
        widths while enforcing sensible minimum and maximum font sizes.

        Args:
            event (Any): The Tkinter event object containing the new window dimensions.
        """
        MINIMUM_WINDOW_WIDTH = 100

        if event.widget == self and event.width > MINIMUM_WINDOW_WIDTH:
            WINDOW_BASE_WIDTH = 800
            SCALE_FACTOR_DIVISOR = 40
            # Calculate a scale factor based on how much wider the window is than the base width.
            scale_factor = max(0, (event.width - WINDOW_BASE_WIDTH) / SCALE_FACTOR_DIVISOR)

            # Define font scaling configurations: (base_size, scale_multiplier, min_size, max_size)
            font_configs = {
                "title": (24, 1.5, 24, 64),
                "button": (16, 0.5, 14, 24),
                "body": (16, 0.5, 14, 22),
                "sidebar_button": (14, 0.3, 12, 18),
                "sidebar_body": (14, 0.3, 12, 18),
            }

            for font_name, (base_size, multiplier, min_size, max_size) in font_configs.items():
                # Calculate the new font size based on the window width, 
                # then clamp it within the defined min and max sizes.
                new_size = base_size + (scale_factor * multiplier)
                clamped_size = max(min_size, min(new_size, max_size))
                self.dynamic_fonts[font_name].configure(size=int(clamped_size))
    
    def get_sidebar_collapse_state(self, sidebar_id: str) -> bool:
        """Get collapse state for a sidebar. Defaults to True (collapsed)."""
        return self.sidebar_states.get(sidebar_id, True)

    def set_sidebar_collapse_state(self, sidebar_id: str, collapsed: bool) -> None:
        """Save collapse state for a sidebar."""
        self.sidebar_states[sidebar_id] = collapsed

    def has_unsaved_work(self) -> bool:
        """Determine whether the current session holds any unsaved data.

        Treats any non-empty player attributes, match overview, or player 
        performance buffers as indicators of unsaved work.

        Returns:
            bool: True if any of the session buffers contain data, otherwise False.
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

    def activate_career(self, career_name: str) -> None:
        """Switch the active application context to the specified career.

        Loads the selected career's data into memory and refreshes related 
        player and match collections before marking it as the current career.

        Args:
            career_name (str): The unique name of the career to activate.
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
        match_difficulty: DifficultyLevel,
        league: str) -> None:
        """Create and immediately activate a new career in the application.

        Delegates persistence to the DataManager, then switches the active context
        so subsequent operations target the newly created career.

        Args:
            club_name (str): The display name of the club for the new career.
            manager_name (str): The manager's name associated with the career.
            starting_season (str): The starting season label (e.g., "2024/25").
            half_length (int): The in-game match half length, in minutes.
            match_difficulty (DifficultyLevel): The difficulty setting for the career.
            league (str): The league in which the club competes.
        """
        self.data_manager.create_new_career(
            club_name, 
            manager_name, 
            starting_season, 
            half_length, 
            match_difficulty, 
            league
        )
        self.activate_career(club_name)
    
    def get_current_career_details(self) -> Optional[CareerMetadata]:
        """Return metadata for the currently active career, if one is selected.

        Acts as a safe accessor for the DataManager, gracefully handling the case
        where no career is active by returning None instead of raising errors.

        Returns:
            Optional[CareerMetadata]: The metadata for the active career, or None if
                                      no career is currently selected.
        """
        if not self.current_career:
            logger.warning("Attempted to get career details, but no career is active.")
            return None
            
        return self.data_manager.get_career_details(self.current_career)

    def get_latest_match_in_game_date(self) -> Optional[datetime]:
        """Fetch the in-game date of the most recently recorded match.

        Provides a safe wrapper around the DataManager, returning None instead of
        propagating errors if the lookup fails or no matches are available.

        Returns:
            Optional[datetime]: The in-game date of the latest match, or None on failure.
        """
        try:
            return self.data_manager.get_latest_match_in_game_date()
        except Exception as e:
            logger.debug(f"Failed to get latest match date from DataManager: {e}")
            return None
    
    def get_all_player_names(self, only_outfield: bool = False, only_gk: bool = False, remove_on_loan: bool = False) -> list[str]:
        """Return an alphabetized list of active player names with optional filtering.

        Syncs player data from disk, removes sold (and optionally loaned-out) players,
        applies positional filters, and formats names for display in the UI.

        Args:
            only_outfield (bool, optional): If True, include only outfield players.
            only_gk (bool, optional): If True, include only goalkeepers.
            remove_on_loan (bool, optional): If True, exclude players currently on loan.

        Returns:
            list[str]: A list of player names sorted by surname, or a single-item list
                       with the message "No players found" when no players match the criteria.
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
        
        # Make sure only_outfield and only_gk can't both be true
        if only_outfield and only_gk:
            logger.warning("Both only_outfield and only_gk flags are True. Defaulting to no positional filter.")
            only_outfield = False
            only_gk = False

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
        return ["No players found"]

    # --- Career / Competitions API for Views (Controller wrappers) ---
    def get_all_career_names(self) -> list[str]:
        """Controller wrapper to retrieve all career display names."""
        return self.data_manager.get_all_career_names()

    def add_competition(self, competition: str) -> None:
        """Add a competition to the current career via the DataManager."""
        if not self.current_career:
            raise RuntimeError("No career loaded")
        self.data_manager.add_competition(competition)

    def remove_competition(self, competition: str) -> None:
        """Remove a competition from the current career via the DataManager."""
        if not self.current_career:
            raise RuntimeError("No career loaded")
        self.data_manager.remove_competition(competition)

    def update_career_metadata(self, updates: dict) -> None:
        """Update current career metadata via the DataManager."""
        if not self.current_career:
            raise RuntimeError("No career loaded")
        self.data_manager.update_career_metadata(updates)

    def get_player_bio(self, name: str) -> Optional[PlayerBioDict]:
        """Retrieve core biographical details for a specific player, if available.

        Provides a lightweight dictionary of basic player attributes for use in 
        UI displays or summary panels, returning None when the player cannot be found.

        Args:
            name (str): The full name of the player to look up.

        Returns:
            Optional[PlayerBioDict]: A dictionary of player bio fields, or None if 
                                     no matching player exists in the current career.
        """
        player = self.data_manager.find_player_by_name(name)
        if player is None:
            return None
        return {
            "age": player.age,
            "height": player.height,
            "weight": player.weight,
            "country": player.nationality,
            "positions": player.positions,
        }

    def buffer_player_attributes(self, data: dict[str, Any], is_goalkeeper: bool, is_first_page: bool = True) -> None:
        """Store captured player attribute data during multi-step entry flows.

        This method routes raw data from goalkeeper and outfield pages into 
        their respective buffer slots. This data remains raw (unvalidated) 
        until the final save step pushes it across the Pydantic boundary in 
        the DataManager.

        Args:
            data (dict[str, Any]): The raw attribute values collected from the UI or OCR.
            is_goalkeeper (bool): Indicates whether the data belongs to a goalkeeper.
            is_first_page (bool, optional): Distinguishes between the first and second 
                                    outfield attribute pages. Defaults to True.
        """
        logger.info(f"Buffering player data. GK: {is_goalkeeper}, First Page: {is_first_page}")

        if is_first_page and is_goalkeeper:
            message = (
                "Invalid player attribute state: data cannot be both goalkeeper "
                "and first-page outfield (is_goalkeeper=True, is_first_page=True)."
            )
            logger.error(message)
            raise ValueError(message)
        if is_goalkeeper:
            self.player_attributes_buffer['gk_attr'] = data
        elif is_first_page:
            self.player_attributes_buffer['outfield_attr_1'] = data
        else:
            self.player_attributes_buffer['outfield_attr_2'] = data

    def _extract_goalkeeper_player_buffer(
        self,
        buffered_data: dict[str, Any],
    ) -> tuple[str, str, str, dict[str, Any]]:
        """Extract normalized save data from a goalkeeper attribute buffer."""
        gk_data = buffered_data['gk_attr']
        return (
            gk_data.get('name', '').strip(),
            'GK',
            gk_data.get('in_game_date', '').strip(),
            gk_data,
        )

    def _extract_outfield_player_buffer(
        self,
        buffered_data: dict[str, Any],
    ) -> tuple[str, str | None, str, dict[str, Any]]:
        """Extract normalized save data from a two-page outfield attribute buffer."""
        outfield_page_1 = buffered_data['outfield_attr_1']
        outfield_page_2 = buffered_data['outfield_attr_2']
        return (
            outfield_page_1.get('name', '').strip(),
            outfield_page_1.get('position') or None,
            outfield_page_1.get('in_game_date', '').strip(),
            {**outfield_page_1, **outfield_page_2},
        )
    
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
        try:
            if 'gk_attr' in self.player_attributes_buffer:
                player_name, position, in_game_date, attributes = self._extract_goalkeeper_player_buffer(
                    self.player_attributes_buffer
                )
                is_gk = True
            elif 'outfield_attr_1' in self.player_attributes_buffer and 'outfield_attr_2' in self.player_attributes_buffer:
                player_name, position, in_game_date, attributes = self._extract_outfield_player_buffer(
                    self.player_attributes_buffer
                )
                is_gk = False
            else:
                raise IncompleteDataError("Cannot save: Missing page 1 or page 2 of outfield attributes.")

            if not player_name or not in_game_date:
                logger.error(f"Save aborted: Missing critical context. Name: '{player_name}', Date: '{in_game_date}'")
                raise IncompleteDataError("Cannot save: Missing required player context fields (Name or In-game Date).")

            logger.info(f"Saving player {player_name} at position {position}")

            self.data_manager.add_or_update_player(
                player_ui_data=attributes,
                position=position,
                in_game_date=in_game_date,
                is_gk=is_gk,
            )
        except IncompleteDataError:
            raise
        except Exception as e:
            # We catch the generic exception (like a Pydantic ValidationError)
            # and wrap it in our custom DataPersistenceError for the UI to handle.
            logger.error(f"DataManager failed to save player '{player_name}': {e}", exc_info=True)
            raise DataPersistenceError(f"Failed to save player data to the database: {e}") from e
        finally:
            # Reset buffer after saving
            self.player_attributes_buffer = {}
    
    def save_financial_data(self, player_name: str, financial_data: dict[str, Any], in_game_date: str) -> None:
        """Controller gatekeeper that validates financial context before persisting data.

        Ensures a player is selected, financial fields are non-empty, and an in-game 
        date is provided before delegating the save operation to the DataManager.

        Args:
            player_name (str): The name of the player whose financials are being updated.
            financial_data (dict[str, Any]): The raw financial fields captured from the UI.
            in_game_date (str): The in-game date associated with the financial snapshot.

        Raises:
            IncompleteDataError: If the player name, financial data, or in-game date is
                                 missing, blank, or otherwise empty.
            DataPersistenceError: If the backend fails to validate or persist the financial data.
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
        """Controller gatekeeper that validates context before selling a player.

        Ensures a player is selected and a non-empty in-game date is provided 
        before delegating the sell operation to the DataManager.

        Args:
            player_name (str): The name of the player to be sold.
            in_game_date (str): The in-game date on which the sale occurs.

        Raises:
            IncompleteDataError: If the player name or in-game date is missing, blank, or empty.
            DataPersistenceError: If the backend fails to update the player's sold status.
        """
        if not player_name or not player_name.strip():
            logger.error("Sell action aborted: No player name provided.")
            raise IncompleteDataError("Cannot sell: No player selected.")
        
        if not in_game_date or not in_game_date.strip():
            logger.error("Sell action aborted: No in-game date provided.")
            raise IncompleteDataError("Cannot sell: In-game date is required.")
            
        logger.info(f"Routing sell request for player: {player_name}")
        try:
            self.data_manager.sell_player(player_name, in_game_date)
        except Exception as e:
            logger.error(f"Failed to sell player '{player_name}': {e}", exc_info=True)
            raise DataPersistenceError(f"Failed to sell player: {e}") from e
    
    def loan_out_player(self, player_name: str) -> None:
        """Controller gatekeeper that validates context before loaning out a player.

        Ensures a player is selected and the name is non-empty before delegating 
        the loan-out operation to the DataManager.

        Args:
            player_name (str): The name of the player to be loaned out.

        Raises:
            IncompleteDataError: If the player name is missing, blank, or empty.
            DataPersistenceError: If the backend fails to save the loan-out record.
        """
        if not player_name or not player_name.strip():
            logger.error("Loan out action aborted: No player name provided.")
            raise IncompleteDataError("Cannot loan out: No player selected.")

        logger.info(f"Routing loan out request for player: {player_name}")
        try:
            self.data_manager.loan_out_player(player_name)
        except Exception as e:
            logger.error(f"Failed to loan out player '{player_name}': {e}", exc_info=True)
            raise DataPersistenceError(f"Failed to loan out player: {e}") from e

    def return_loan_player(self, player_name: str) -> None:
        """Controller gatekeeper that validates context before returning a player from loan.

        Ensures a player is selected and the name is non-empty before delegating 
        the return-from-loan operation to the DataManager.

        Args:
            player_name (str): The name of the player to be returned from loan.

        Raises:
            IncompleteDataError: If the player name is missing, blank, or empty.
            DataPersistenceError: If the backend fails to update the player's loan status.
        """
        if not player_name or not player_name.strip():
            logger.error("Return loan action aborted: No player name provided.")
            raise IncompleteDataError("Cannot return from loan: No player selected.")

        logger.info(f"Routing return from loan request for player: {player_name}")
        try:
            self.data_manager.return_loan_player(player_name)
        except Exception as e:
            logger.error(f"Failed to return player '{player_name}' from loan: {e}", exc_info=True)
            raise DataPersistenceError(f"Failed to return player from loan: {e}") from e

    def add_injury_record(self, player_name: str, injury_data: dict[str, Any]) -> None:
        """Controller gatekeeper that validates injury context before persisting data.

        Ensures a player is selected and non-empty injury fields are provided 
        before delegating the save operation to the DataManager.

        Args:
            player_name (str): The name of the player whose injury record is being saved.
            injury_data (dict[str, Any]): The raw injury details captured from the UI.

        Raises:
            IncompleteDataError: If the player name or injury data are missing, blank, or empty.
            DataPersistenceError: If the backend fails to validate or persist the injury data.
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

            stats: dict[str, Any] = self._detect_stats(is_player=False)

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
    
    def process_player_stats(self, is_goalkeeper: bool = False) -> None:
        """Process individual player match statistics via the OCR workflow.

        Captures a screenshot of the active screen, detects the player statistics 
        based on their role (Goalkeeper vs Outfield), and routes the extracted data 
        to the appropriate UI frame for user validation.

        Args:
            is_goalkeeper (bool): If True, processes stats for the GKStatsFrame. 
                                  If False, processes stats for the PlayerStatsFrame.

        Raises:
            UIPopulationError: If the screenshot, OCR process, or frame population fails.
        """
        try:
            self._capture_screenshot()
            
            stats: dict[str, Any] = self._detect_stats(is_player=True, is_goalkeeper=is_goalkeeper)
            
            if is_goalkeeper:
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
            logger.error(f"Error processing player stats (GK={is_goalkeeper}): {e}", exc_info=True)
            # Re-raise to trigger a GUI warning popup
            raise UIPopulationError(f"Failed to extract player stats from screen: {e}") from e
        
    def process_player_attributes(self, is_goalkeeper: bool, is_first_page: bool) -> None:
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
            self._capture_screenshot()
            
            stats: dict[str, Any] = self._detect_player_attributes(is_goalkeeper=is_goalkeeper, is_first_page=is_first_page)
            
            if is_goalkeeper:
                logger.info("Populating AddGKFrame with detected attributes.")
                target_frame = self.frames[self.get_frame_class("AddGKFrame")]
            else:
                logger.info(f"Populating {'AddOutfieldFrame1' if is_first_page else 'AddOutfieldFrame2'} with detected attributes.")
                target_frame = self.frames[self.get_frame_class("AddOutfieldFrame1" if is_first_page else "AddOutfieldFrame2")]
            
            if hasattr(target_frame, "populate_stats"):
                target_frame.populate_stats(stats)
            else:
                logger.error(f"{target_frame.__class__.__name__} is missing the 'populate_stats' method.")
                raise UIPopulationError("Target UI frame cannot accept OCR attributes.")
        
        except Exception as e:
            # Log the technical trace for the developer
            logger.error(f"Error processing player attributes (GK={is_goalkeeper}, First={is_first_page}): {e}", exc_info=True)
            # Re-raise to trigger a GUI warning popup
            raise UIPopulationError(f"Failed to extract player attributes from screen: {e}") from e
    
    def _capture_screenshot(self, delay: int | None = None) -> None:
        """Capture a timestamped screenshot of the user's screen for OCR processing.

        Presents a brief, user-visible delay to allow focus on the game window, then
        saves the screenshot into the app's screenshots directory and performs cleanup.

        Args:
            delay (int | None, optional): The number of seconds to wait before capturing
                the screenshot. If None, the application's default delay is used.
        """
        if delay is None:
            delay = App.DEFAULT_SCREENSHOT_DELAY
        if delay < 0:
            logger.warning(f"Negative delay provided for screenshot capture: {delay}s. Defaulting to {App.DEFAULT_SCREENSHOT_DELAY}s.")
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
        
        # Ensure the screenshot file is fully written and accessible before proceeding
        if not self.screenshot_path.exists():
            logger.error(f"Screenshot file not found after capture: {self.screenshot_path}")
            raise ScreenshotError("Screenshot file was not created successfully.")
    
    def _non_blocking_delay(self, seconds: int, message: str = "Please wait...") -> None:
        """Display a non-blocking countdown overlay instead of freezing the UI.

        Provides a user-facing message and timer while long-running operations 
        (such as screenshot capture delays) are pending, keeping the main window responsive.

        Args:
            seconds (int): The number of seconds to display the overlay countdown.
            message (str, optional): The message shown alongside the countdown. Defaults to "Please wait...".
        """
        show_delay_overlay(self, seconds, message)

    def _get_latest_screenshot_path(self) -> Path:
        """Locate and return the most recent stats screenshot captured by the application.

        Searches the dedicated screenshots directory for files matching the expected
        naming pattern and surfaces clear, user-facing errors when no directory or
        screenshots are available.

        Raises:
            ScreenshotError: If the screenshots directory is missing or contains no
                             matching screenshot files.

        Returns:
            Path: The filesystem path to the most recently modified screenshot file.
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
        and deletes the oldest files, keeping only the ``max_files`` most recent.
        Deletions are scheduled on a background thread pool so the UI is not
        blocked; failures to delete individual files are logged but not raised.

        Args:
            max_files (int): The maximum number of recent screenshots to retain.
                             Defaults to 5.
        """
        screenshots_dir = App.PROJECT_ROOT / "screenshots"
        if not screenshots_dir.exists():
            return

        if max_files <= 0:
            # Nothing to keep; treat as no-op to avoid mass-deletion surprises.
            logger.debug("max_files <= 0; skipping screenshot cleanup.")
            return

        # Get all screenshot files and ensure they are regular files
        screenshot_files = [p for p in screenshots_dir.glob("stats_capture_*.png") if p.is_file()]

        # Safe mtime getter to avoid races if a file disappears between listing and stat()
        def _safe_mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except OSError:
                return 0.0

        # Sort files by modification time (newest first)
        screenshot_files.sort(key=_safe_mtime, reverse=True)

        # Identify files to delete (everything after the first max_files)
        files_to_delete = screenshot_files[max_files:]
        if not files_to_delete:
            return

        logger.info(f"Cleanup: Deleting {len(files_to_delete)} old screenshots.")

        # Delete files on a short-lived background thread pool so we don't block Tk mainloop
        from concurrent.futures import ThreadPoolExecutor

        def _delete_file(path: Path) -> None:
            """Attempt to delete a file, logging any issues but not raising exceptions."""
            try:
                # Use missing_ok when available (Python 3.8+)
                try:
                    path.unlink(missing_ok=True)  # type: ignore[arg-type]
                    logger.debug(f"Deleted old screenshot: {path}")
                except TypeError:
                    # missing_ok not supported; fall back to guarded unlink
                    try:
                        path.unlink()
                        logger.debug(f"Deleted old screenshot: {path}")
                    except FileNotFoundError:
                        logger.debug(f"Screenshot already removed: {path}")
                    except PermissionError as e:
                        logger.warning(f"Permission denied deleting screenshot {path}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to delete screenshot {path}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error when deleting screenshot {path}: {e}")

        executor = ThreadPoolExecutor(max_workers=2)
        for p in files_to_delete:
            executor.submit(_delete_file, p)
        # Do not wait for completion; allow background threads to finish asynchronously
        executor.shutdown(wait=False)
    
    def _detect_stats(self, is_player: bool, is_goalkeeper: bool = False) -> dict[str, Any]:
        """Detect and extract statistics from the latest screenshot using OCR.

        Loads ROI (Region of Interest) coordinates from the JSON config, maps 
        them based on the requested context (match overview, outfield player, 
        or goalkeeper), and runs the OCR model against the latest screenshot.

        Args:
            is_player (bool): True if extracting individual player stats, 
                              False for team match overview stats.
            is_goalkeeper (bool, optional): True if extracting goalkeeper stats. Defaults to False.

        Raises:
            ConfigurationError: If the coordinates JSON is missing or corrupt.
            ScreenshotError: If the screenshot cannot be loaded by OpenCV.

        Returns:
            dict[str, Any]: A dictionary containing the strictly typed detected statistics.
        """
        logger.info(f"Starting OCR (player mode: {is_player})")
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
        results: dict[str, Any] = {}
        
        # --- 3. Determine Target Screen ---
        if not is_player:
            target_screen = "match_overview"
        elif is_goalkeeper:
            target_screen = "gk_performance"
        else:
            target_screen = "player_performance"
        
        screen_data = coordinates.get(target_screen)
        if not screen_data:
            logger.warning(f"No coordinates found in JSON for screen: '{target_screen}'")
            return results

        logger.debug(f"Processing target screen: {target_screen}")
        
        # --- 4. Reusable OCR Execution Engine ---
        def process_roi_dict(data_dict: dict[str, Any]) -> dict[str, Any]:
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
                
                # ocr.recognise_number returns number as a string with no decimal point, 
                # e.g. 0.5 is returned as 05, convert it to a float if in decimal stats 
                # otherwise convert to int
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
    
    def _detect_player_attributes(self, is_goalkeeper: bool = False, is_first_page: bool = True) -> dict[str, Any]:
        """Detect and extract player attribute statistics from the latest screenshot.

        Loads coordinates based on player position and page, processes the screenshot 
        using customized OCR preprocessing (e.g., erosion for colored text), and 
        safely casts all recognized values to integers for Pydantic compatibility.

        Args:
            is_goalkeeper (bool, optional): If True, processes goalkeeper attributes. Defaults to False.
            is_first_page (bool, optional): If True, processes the first page of the outfield 
                                    player's attributes. Defaults to True.

        Raises:
            ConfigurationError: If the coordinates JSON is missing or corrupt.
            ScreenshotError: If the screenshot cannot be loaded by OpenCV.

        Returns:
            dict[str, Any]: A dictionary mapping attribute names to their parsed integer values.
        """
        logger.info(f"Starting Attribute OCR (GK: {is_goalkeeper}, First Page: {is_first_page})")
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
        results: dict[str, Any] = {}
        
        # --- 3. O(1) Dictionary Targeting ---
        # Navigate directly to the required node instead of looping through items
        target_position = "gk" if is_goalkeeper else "outfield_1" if is_first_page else "outfield_2"
        
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
        """Stage validated match overview data in a temporary session buffer.

        Acts as a controller gatekeeper by enforcing basic shape and key checks 
        on the overview payload before it is accepted for later persistence.

        Args:
            overview_data (dict[str, Any]): The raw match overview fields collected 
                                            from the UI or OCR.
        """

        # Validate that the dictionary contains the expected keys
        expected_keys = {"home_team", "away_team"}
        missing_keys = expected_keys.difference(overview_data.keys())
        if missing_keys:
            logger.error(f"Match overview data is missing required keys: {missing_keys}")
            raise ValueError(f"Match overview data is missing required keys: {missing_keys}")
        expected_keys = {"home_team", "away_team"}
        if not expected_keys.issubset(overview_data.keys()):
            logger.error("Match overview data is missing required keys.")
            raise ValueError("Match overview data is missing required keys.")

        logger.info("Buffering match overview data.")
        self.match_overview_buffer = overview_data
    
    def buffer_player_performance(self, performance_data: dict[str, Any]) -> None:
        """Stage a single player's performance data in the session buffer after validation.

        Acts as a controller gatekeeper by enforcing type checks, required keys, 
        and duplicate-prevention rules before accepting performance payloads.

        Args:
            performance_data (dict[str, Any]): The raw performance statistics for a single 
                                               player, including at minimum a ``player_name`` key.

        Raises:
            ValueError: If the payload is not a dictionary or is missing the required ``player_name`` key.
            DuplicateRecordError: If performance data for the same player has already been buffered this match.
        """
        # validate that data is a dict and contains expected keys (e.g. player_name)
        if not isinstance(performance_data, dict):
            logger.error("Attempted to buffer player performance data that is not a dictionary.")
            raise ValueError("Player performance data must be a dictionary.")
        
        if "player_name" not in performance_data:
            logger.error("Player performance data is missing the required 'player_name' key.")
            raise ValueError("Player performance data must include 'player_name' key.")
        
        logger.info(f"Buffering player performance data for: {performance_data.get('player_name', 'Unknown')}")
        
        # Check if data for this player has already been buffered
        for dataset in self.player_performances_buffer:
            if dataset.get('player_name') == performance_data.get('player_name'):
                logger.error(f"Duplicate player performance detected for {performance_data.get('player_name')}. Each player's performance should only be buffered once per match.")
                raise DuplicateRecordError(performance_data.get('player_name'))
                
        self.player_performances_buffer.append(performance_data)
    
    def get_buffered_player_performances(self, display_keys: list[str], id_key: str = "player_name", default: str = "-") -> list[dict[str, str]]:
        """Format buffered player performance data for safe, human-readable display.

        Converts the raw internal performance payloads into a list of flat, string-only
        dictionaries keyed by an identifier and selected display fields, applying
        sensible defaults and special handling for goalkeepers and missing values.

        Args:
            display_keys (list[str]): The ordered list of keys to expose in each formatted record.
            id_key (str, optional): The key used as the unique identifier column (e.g. ``"player_name"``).
                                    Entries missing this key are skipped. Defaults to ``"player_name"``.
            default (str, optional): The placeholder string used when a field is missing, null, or empty.
                                     Defaults to ``"-"``.

        Returns:
            list[dict[str, str]]: A list of dictionaries suitable for UI tables, where all values
                                   are strings and each entry is guaranteed to contain the id_key.
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
                value = performance.get(key, default)
                if value in (None, ""): 
                    value = default
                if isinstance(value, list):
                    formatted_performance[key] = ", ".join(str(v) for v in value)
                else:
                    formatted_performance[key] = str(value)
            formatted_performances.append(formatted_performance)
        
        return formatted_performances
    
    def remove_player_from_buffer(self, player_name: str) -> None:
        """Remove a single player's performance entry from the in-memory session buffer.

        Acts as a controller gatekeeper by enforcing a non-empty player name and 
        safely filtering the buffer, logging whether any matching entry was found.

        Args:
            player_name (str): The full name of the player whose buffered performance
        """
        # Normalize the target player name once for robust comparison
        normalized_target = player_name.strip().casefold()

        def _safe_normalize_name(name: Any) -> Optional[str]:
            """
            Safely normalize a player name by stripping whitespace and case-folding.

            Returns None if the provided name is not a non-empty string.
            """
            if not isinstance(name, str):
                return None
            stripped = name.strip()
            return stripped.casefold() if stripped else None

        original_count = len(self.player_performances_buffer)
        self.player_performances_buffer = [
            performance
            for performance in self.player_performances_buffer
            if _safe_normalize_name(performance.get("player_name")) != normalized_target
        ]
        
        original_count = len(self.player_performances_buffer)
        self.player_performances_buffer = [
            performance for performance in self.player_performances_buffer 
            if performance.get("player_name").strip().casefold() != player_name.strip().casefold()
        ]
        if len(self.player_performances_buffer) < original_count:
            logger.info(f"Removed buffered performance for player: {player_name}")
        else:
            logger.warning(f"No buffered performance found for player: {player_name}. No entries removed.")
    
    def save_buffered_match(self) -> None:
        """Controller gatekeeper that validates buffered match data before saving.

        Ensures a match overview has been staged, delegates persistence of the 
        overview and all buffered player performances to the DataManager, and
        then clears the in-memory buffers to avoid cross-match contamination.

        Raises:
            IncompleteDataError: If no match overview data has been buffered for the session.
            DataPersistenceError: If the DataManager fails to validate or persist the match.
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
        else:
            # Clear buffers only after a successful save so the user can retry on failure
            logger.debug("Clearing match buffers after successful save.")
            self.match_overview_buffer.clear()
            self.player_performances_buffer.clear()
    