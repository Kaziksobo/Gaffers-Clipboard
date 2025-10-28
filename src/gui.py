import customtkinter as ctk
import time
import pyautogui
import json
import cv2 as cv
from src import ocr
from pathlib import Path
from src.theme import THEME
from src.views.main_menu_frame import MainMenuFrame
from src.views.add_match_frame import AddMatchFrame
from src.views.match_stats_frame import MatchStatsFrame
from src.views.player_stats_frame import PlayerStatsFrame
from src.views.match_added_frame import MatchAddedFrame
from src.views.player_library_frame import PlayerLibraryFrame
from src.views.add_gk_frame import AddGKFrame
from src.views.add_outfield_frame import AddOutfieldFrame

class App(ctk.CTk):
    # Default screenshot delay (seconds) used when no explicit delay is provided
    DEFAULT_SCREENSHOT_DELAY = 3
    PROJECT_ROOT = Path(__file__).parent.parent

    def __init__(self) -> None:
        '''    
        Initialize the main application window, set up the frame container,
        register all navigation frames, and display the main menu.

        - Sets window title, size, and minimum size.
        - Creates a container frame for all pages.
        - Instantiates and registers each frame (MainMenu, AddMatch, MatchStats, PlayerStats, MatchAdded).
        - Displays the main menu frame on startup.
        '''
        super().__init__()
        self.title("Gaffer's Clipboard")
        self.geometry("800x600")
        self.minsize(600, 400)
        
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        
        for F in (MainMenuFrame, AddMatchFrame, MatchStatsFrame, PlayerStatsFrame, MatchAddedFrame, PlayerLibraryFrame, AddGKFrame, AddOutfieldFrame):
            frame = F(container, self, THEME)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame(MainMenuFrame)

    def show_frame(self, page_class: type) -> None:
        '''Show a frame for the given page class.

        Args:
            page_class (type): The class of the page to show.
        '''
        frame = (self.frames[page_class])
        frame.tkraise()

    def get_frame_class(self, name: str) -> type:
        '''Get the frame class by its name.

        Args:
            name (str): The name of the frame class.

        Raises:
            ValueError: If no frame class with the given name is found.

        Returns:
            type: The frame class corresponding to the given name.
        '''
        for cls in self.frames:
            if cls.__name__ == name:
                return cls
        raise ValueError(f"No frame class named '{name}' found.")
    
    def process_match_stats(self):
        self.capture_screenshot()
        stats = self.detect_stats(is_it_player=False)
        
        match_stats_frame = self.frames[self.get_frame_class("MatchStatsFrame")]
        match_stats_frame.populate_stats(stats)
        
    def process_player_attributes(self, gk: bool, first: bool):
        self.capture_screenshot()
        stats = self.detect_player_attributes(gk=gk, first=first)
        
        if gk:
            gk_attr_frame = self.frames[self.get_frame_class("AddGKFrame")]
            gk_attr_frame.populate_stats(stats)
        else:
            outfield_attr_frame = self.frames[self.get_frame_class("AddOutfieldFrame")]
            outfield_attr_frame.populate_stats(stats)
    
    def capture_screenshot(self, delay: int | None = None) -> None:
        '''Capture a screenshot after a delay.

        Args:
            is_it_player (bool): Whether the screenshot is a specific player's match stats or match overview
            delay (int | None, optional): Delay before taking the screenshot. If None,
                uses the application's `screenshot_delay` (defaults to
                `App.DEFAULT_SCREENSHOT_DELAY`).
        '''
        if delay is None:
            delay = App.DEFAULT_SCREENSHOT_DELAY
        print(f"Capturing screenshot in {delay} seconds...")
        time.sleep(delay)
        capture_folder = App.PROJECT_ROOT / "screenshots"
        capture_folder.mkdir(parents=True, exist_ok=True)
        filename = f"stats_capture_{int(time.time())}.png"
        self.screenshot_path = capture_folder / filename
        
        pyautogui.screenshot(self.screenshot_path)

        print(f"Screenshot saved to {self.screenshot_path}")
        
    
    def get_latest_screenshot_path(self) -> Path:
        screenshots_dir = App.PROJECT_ROOT / "screenshots"
        if not screenshots_dir.exists():
            raise FileNotFoundError("Screenshots directory does not exist.")
        
        screenshot_files = list(screenshots_dir.glob("stats_capture_*.png"))
        if not screenshot_files:
            raise FileNotFoundError("No screenshots found in the screenshots directory.")
        
        latest_screenshot = max(screenshot_files, key=lambda p: p.stat().st_mtime)
        return latest_screenshot
    
    def detect_stats(self, is_it_player: bool) -> dict:
        latest_screenshot_path = App.PROJECT_ROOT / "testing" / "fullscreen_screenshots" / "cropped" / "match_overview.png"
        
        # load coordinates from JSON file
        coordinates_path = App.PROJECT_ROOT / "config" / "coordinates.json"
        with open(coordinates_path, 'r') as f:
            coordinates = json.load(f)
        
        # import OCR model
        ocr_model = ocr.load_ocr_model()
        
        # load the latest screenshot for processing
        screenshot_image = cv.imread(str(latest_screenshot_path))
        
        decimal_stats = ['xG']
        debug = True
        
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
                                recognised_number = recognised_number[:-1] + '.' + recognised_number[-1]
                            recognised_number = float(recognised_number)
                        
                        print(f"Recognised value: {recognised_number}")
                        results[team_name][stat_name] = recognised_number
        
        return results    
    
    def detect_player_attributes(self, gk=False, first=True):
        # latest_screenshot_path = self.get_latest_screenshot_path()
        latest_screenshot_path = App.PROJECT_ROOT / "testing" / "fullscreen_screenshots" / "cropped" / "player_attributes_gk.png"

        coordinates_path = App.PROJECT_ROOT / "config" / "coordinates.json"
        with open(coordinates_path, 'r') as f:
            coordinates = json.load(f)
        
        ocr_model = ocr.load_ocr_model()
        
        screenshot_image = cv.imread(str(latest_screenshot_path))
        
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
                                debug=True
                            )
                            
                            results[stat_name] = recognised_number
        return results