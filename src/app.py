import customtkinter as ctk
import time
import pyautogui
import json
import cv2 as cv
import logging
from src import ocr
from pathlib import Path
from src.theme import THEME
from src.exceptions import GUIError, ScreenshotError, FrameNotFoundError, ConfigurationError, UIPopulationError
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
from src.data_manager import DataManager

logger = logging.getLogger(__name__)

class App(ctk.CTk):
    # Default screenshot delay (seconds) used when no explicit delay is provided
    DEFAULT_SCREENSHOT_DELAY = 3
    PROJECT_ROOT = Path(__file__).parent.parent

    def __init__(self) -> None:
        '''    
        Initialize the main application window, set up the frame container,
        register all navigation frames, and display the career select frame.

        - Sets window title, size, and minimum size.
        - Initializes the DataManager with the data directory.
        - Creates a container frame for all pages.
        - Instantiates and registers each frame (CareerSelect, CreateCareer, MainMenu, AddMatch, MatchStats, PlayerStats, MatchAdded, PlayerLibrary, AddGK, AddOutfield1, AddOutfield2).
        - Displays the career select frame on startup.
        '''
        super().__init__()
        self.title("Gaffer's Clipboard")
        self.geometry("800x600")
        self.minsize(600, 400)
        
        data_path = App.PROJECT_ROOT / "data"
        self.data_manager = DataManager(data_path)
        
        self.current_career = None
        
        # Buffers to allow data to be collected by multiple frames before entering into data manager
        self.outfield_player_buffer = {}
        self.match_overview_buffer = {}
        self.player_performances_buffer = []

        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        
        for F in (CareerSelectFrame, CreateCareerFrame, MainMenuFrame, AddMatchFrame, MatchStatsFrame, PlayerStatsFrame, MatchAddedFrame, PlayerLibraryFrame, AddGKFrame, AddOutfieldFrame1, AddOutfieldFrame2):
            frame = F(container, self, THEME)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame(CareerSelectFrame)
        
    def get_frame_class(self, name: str) -> type:
        '''Get the frame class by its name.

        Args:
            name (str): The name of the frame class.

        Raises:
            FrameNotFoundError: If no frame class with the given name is found.

        Returns:
            type: The frame class corresponding to the given name.
        '''
        for cls in self.frames:
            if cls.__name__ == name:
                return cls
        raise FrameNotFoundError(f"No frame class named '{name}' found.")
    
    def show_frame(self, page_class: type) -> None:
        '''Show a frame for the given page class.

        Args:
            page_class (type): The class of the page to show.
        Raises:
            FrameNotFoundError: If the frame for the given page class is not found.
        '''
        if page_class not in self.frames:
            raise FrameNotFoundError(f"No frame class named '{page_class.__name__}' found.")
        frame = self.frames[page_class]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def set_current_career_by_name(self, career_name: str) -> None:
        self.data_manager.load_career(career_name)
        self.data_manager.refresh_players()
        self.current_career = career_name
    
    def save_new_career(self, club_name: str, manager_name: str, starting_season: str, half_length: int, match_difficulty: str) -> None:
        self.data_manager.create_new_career(club_name, manager_name, starting_season, half_length, match_difficulty)
        self.set_current_career_by_name(club_name)
    
    def get_current_career_details(self) -> dict | None:
        return self.data_manager.get_career_details(self.current_career)
    
    def get_all_player_names(self) -> list[str]:
        """
        Returns a sorted list of all player names from the data manager. 
        If no players are found, returns a list containing a single message.

        Returns:
            list[str]: A sorted list of player names, or ["No players found"] if none exist.
        """
        self.data_manager.refresh_players()
        if not self.data_manager.players:
            return ["No players found"]
        return sorted([player.get("name") for player in self.data_manager.players])
    
    def buffer_outfield_data(self, data_page_1: dict) -> None:
        '''Buffers outfield player data from the first attribute page.

        Args:
            data_page_1 (dict): The attribute data from the first page.
        '''
        self.outfield_player_buffer = data_page_1
    
    def save_outfield_player(self, data_page_2: dict) -> None:
        """
        Combines buffered and new outfield player data, then saves or updates the player in the data manager.
        This method ensures all relevant player attributes are merged and stored for future reference.

        Args:
            data_page_2 (dict): The attribute data from the second page.
        """
        full_player_data = {**self.outfield_player_buffer, **data_page_2}

        position = full_player_data.pop("position", "Unknown")
        season = full_player_data.pop("season", "Unknown")
        
        self.data_manager.add_or_update_player(
            player_ui_data=full_player_data,
            position=position,
            season=season
        )

    def process_match_stats(self) -> None:
        '''Process match statistics by capturing a screenshot,
        detecting statistics, and populating the MatchStatsFrame with the results.
        '''
        self.capture_screenshot()
        stats = self.detect_stats(is_it_player=False)
        
        match_stats_frame = self.frames[self.get_frame_class("MatchStatsFrame")]
        match_stats_frame.populate_stats(stats)
    
    def process_player_stats(self) -> None:
        '''Process player statistics by capturing a screenshot,
        detecting statistics, and populating the PlayerStatsFrame with the results.
        '''
        self.capture_screenshot()
        stats = self.detect_stats(is_it_player=True)
        
        player_stats_frame = self.frames[self.get_frame_class("PlayerStatsFrame")]
        player_stats_frame.populate_stats(stats)
        
    def process_player_attributes(self, gk: bool, first: bool) -> None:
        '''Process player attributes by capturing a screenshot,
        detecting statistics, and populating the corresponding frame with the results

        Args:
            gk (bool): Identify if the player is a goalkeeper or not
            first (bool): If the player is an outfield player, identify if it's the first or second page of attributes
        '''
        self.capture_screenshot()
        stats = self.detect_player_attributes(gk=gk, first=first)
        
        if gk:
            gk_attr_frame = self.frames[self.get_frame_class("AddGKFrame")]
            gk_attr_frame.populate_stats(stats)
        else:
            outfield_attr_frame = self.frames[self.get_frame_class("AddOutfieldFrame1" if first else "AddOutfieldFrame2")]
            outfield_attr_frame.populate_stats(stats)
    
    def capture_screenshot(self, delay: int | None = None) -> None:
        '''Capture a screenshot after a set delay

        Args:
            delay (int | None, optional): The delay before taking a screenshot. Defaults to None, which uses DEFAULT_SCREENSHOT_DELAY.

        Raises:
            ScreenshotError: If the screenshot capture fails.
        '''
        if delay is None:
            delay = App.DEFAULT_SCREENSHOT_DELAY
        print(f"Capturing screenshot in {delay} seconds...")
        time.sleep(delay)
        capture_folder = App.PROJECT_ROOT / "screenshots"
        capture_folder.mkdir(parents=True, exist_ok=True)
        filename = f"stats_capture_{int(time.time())}.png"
        self.screenshot_path = capture_folder / filename
        try:
            pyautogui.screenshot(self.screenshot_path)
            print(f"Screenshot saved to {self.screenshot_path}")
            self._cleanup_screenshots()
        except Exception as e:
            raise ScreenshotError(f"Failed to capture screenshot: {e}") from e

    def get_latest_screenshot_path(self) -> Path:
        '''Gets the path of the latest screenshot taken by the application, based on the modification time.

        Raises:
            ScreenshotError: If the screenshots directory does not exist.
            ScreenshotError: If no screenshots are found in the screenshots directory.

        Returns:
            Path: The path of the latest screenshot.
        '''
        screenshots_dir = App.PROJECT_ROOT / "screenshots"
        if not screenshots_dir.exists():
            raise ScreenshotError("Screenshots directory does not exist.")

        if screenshot_files := list(screenshots_dir.glob("stats_capture_*.png")):
            return max(screenshot_files, key=lambda p: p.stat().st_mtime)
        else:
            raise ScreenshotError("No screenshots found in the screenshots directory.")
    
    def _cleanup_screenshots(self, max_files: int = 5) -> None:
        screenshots_dir = App.PROJECT_ROOT / "screenshots"
        if not screenshots_dir.exists():
            return
        
        # Get all screenshot files
        screenshot_files = list(screenshots_dir.glob("*.png"))
        
        # Sort files by modification time (newest first)
        screenshot_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Identify files to delete (everything after the first max_files)
        files_to_delete = screenshot_files[max_files:]
        
        if not files_to_delete:
            return
        
        for file_path in files_to_delete:
            try:
                file_path.unlink()
                print(f"Deleted old screenshot: {file_path}")
            except Exception as e:
                print(f"Failed to delete screenshot {file_path}: {e}")
    
    def detect_stats(self, is_it_player: bool) -> dict:
        '''Detects and extracts match statistics from the latest screenshot using OCR.

        Args:
            is_it_player (bool): Under construction, method currently not setup to deal with individual player stats

        Raises:
            ConfigurationError: If coordinates file is missing
            ConfigurationError: If coordinates file is corrupt

        Returns:
            dict: A dictionary containing the detected statistics.
        '''
        latest_screenshot_path = self.get_latest_screenshot_path()

        # load coordinates from JSON file
        coordinates_path = App.PROJECT_ROOT / "config" / "coordinates.json"
        if not coordinates_path.exists():
            raise ConfigurationError("Coordinates configuration file is missing.")
        try:
            with open(coordinates_path, 'r') as f:
                coordinates = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError("Coordinates configuration file is corrupt.") from e

        # import OCR model
        ocr_model = ocr.load_ocr_model()

        # load the latest screenshot for processing
        screenshot_image = cv.imread(str(latest_screenshot_path))

        decimal_stats = ['xG', 'distance_covered', 'distance_sprinted']
        debug = False

        results = {}

        for screen_name, screen_data in coordinates.items():
            if screen_name == "match_overview" and not is_it_player:
                for team_name, team_data in screen_data.items():
                    results[team_name] = {}
                    print(f"Processing {team_name} stats...")
                    for stat_name, roi in team_data.items():
                        x1 = roi['x1']
                        y1 = roi['y1']
                        x2 = roi['x2']
                        y2 = roi['y2']
                        stat_roi = (x1, y1, x2, y2)

                        print(f"  Recognising {stat_name}...")
                        recognised_number = ocr.recognise_number(
                            full_screenshot=screenshot_image,
                            roi=stat_roi,
                            ocr_model=ocr_model,
                            debug=debug
                        )
                        if debug:
                            # if debug is true, recognised_number will output two variables not one, so separate them
                            recognised_number, debug_image = recognised_number

                        if stat_name in decimal_stats:
                            recognised_number = str(recognised_number)
                            if len(recognised_number) > 1:
                                recognised_number = f'{recognised_number[:-1]}.{recognised_number[-1]}'
                            recognised_number = float(recognised_number)

                        print(f"Recognised value: {recognised_number}")
                        results[team_name][stat_name] = recognised_number
            if screen_name == "player_performance" and is_it_player:
                print("Processing player stats...")
                for stat_name, roi in screen_data.items():
                    x1 = roi['x1']
                    y1 = roi['y1']
                    x2 = roi['x2']
                    y2 = roi['y2']
                    stat_roi = (x1, y1, x2, y2)

                    print(f"  Recognising {stat_name}...")
                    recognised_number = ocr.recognise_number(
                        full_screenshot=screenshot_image,
                        roi=stat_roi,
                        ocr_model=ocr_model,
                        debug=debug
                    )
                    if debug:
                        # if debug is true, recognised_number will output two variables not one, so separate them
                        recognised_number, debug_image = recognised_number

                    if stat_name in decimal_stats:
                        recognised_number = str(recognised_number)
                        if len(recognised_number) > 1:
                            recognised_number = f'{recognised_number[:-1]}.{recognised_number[-1]}'
                        recognised_number = float(recognised_number)

                    print(f"Recognised value: {recognised_number}")
                    results[stat_name] = recognised_number

        return results    
    
    def detect_player_attributes(self, gk=False, first=True) -> dict:
        '''Detects and extracts player attribute statistics from the latest screenshot using OCR.

        Args:
            gk (bool, optional): If True, processes goalkeeper attributes. Defaults to False.
            first (bool, optional): If True, processes the first page of the outfield player's attributes, 
            otherwise processes the second page of outfield player's attributes. Defaults to True.

        Raises:
            ConfigurationError: If coordinates file is missing.
            ConfigurationError: If coordinates file is corrupt.

        Returns:
            dict: A dictionary containing the detected player attributes.
        '''
        latest_screenshot_path = self.get_latest_screenshot_path()

        coordinates_path = App.PROJECT_ROOT / "config" / "coordinates.json"
        if not coordinates_path.exists():
            raise ConfigurationError("Coordinates configuration file is missing.")
        try:
            with open(coordinates_path, 'r') as f:
                coordinates = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError("Coordinates configuration file is corrupt.") from e

        ocr_model = ocr.load_ocr_model()
        
        screenshot_image = cv.imread(str(latest_screenshot_path))
        
        debug = False
        
        results = {}
        
        for screen_name, screen_data in coordinates.items():
            if screen_name == 'player_attributes':
                for position, stats in coordinates['player_attributes'].items():
                    if position == ("gk" if gk else 'outfield_1' if first else 'outfield_2'):
                        for stat_name, roi in stats.items():
                            x1 = roi['x1']
                            y1 = roi['y1']
                            x2 = roi['x2']
                            y2 = roi['y2']
                            stat_roi = (x1, y1, x2, y2)

                            recognised_number = ocr.recognise_number(
                                full_screenshot=screenshot_image,
                                roi=stat_roi,
                                ocr_model=ocr_model,
                                preprocess_args={'erode_iterations': 1},
                                debug=debug
                            )

                            if debug:
                                # if debug is true, recognised_number will output two variables not one, so separate them
                                recognised_number, debug_image = recognised_number

                            results[stat_name] = recognised_number
        return results
    
    def buffer_match_overview(self, overview_data: dict) -> None:
        '''Buffers match overview data.

        Args:
            overview_data (dict): The match overview data to buffer.
        '''
        self.match_overview_buffer = overview_data
    
    def buffer_player_performance(self, performance_data: dict) -> None:
        '''Buffers a single player's performance data.

        Args:
            performance_data (dict): The player's performance data to buffer.
        '''
        self.player_performances_buffer.append(performance_data)
    
    def save_buffered_match(self) -> None:
        '''
        Saves the buffered match overview and player performances to the data manager as a new match entry.
        Clears the buffers after saving.
        '''
        self.data_manager.add_match(
            match_data=self.match_overview_buffer,
            player_performances=self.player_performances_buffer
        )
        # Clear buffers after saving
        self.match_overview_buffer = {}
        self.player_performances_buffer = []
    