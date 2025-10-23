import customtkinter as ctk
import time
import pyautogui
import json
import cv2 as cv
import ocr
from pathlib import Path
from src.theme import THEME
from src.views.main_menu_frame import MainMenuFrame
from src.views.add_match_frame import AddMatchFrame
from src.views.match_stats_frame import MatchStatsFrame
from src.views.player_stats_frame import PlayerStatsFrame
from src.views.match_added_frame import MatchAddedFrame

PROJECT_ROOT = Path(__file__).parent.parent

class App(ctk.CTk):
    # Default screenshot delay (seconds) used when no explicit delay is provided
    DEFAULT_SCREENSHOT_DELAY = 3

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
        
        for F in (MainMenuFrame, AddMatchFrame, MatchStatsFrame, PlayerStatsFrame, MatchAddedFrame):
            frame = F(container, self, THEME)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.screenshot_delay = self.DEFAULT_SCREENSHOT_DELAY
        
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
        self.capture_screenshot(is_it_player=False)
        stats = self.detect_stats(is_it_player=False)
        
        match_stats_frame = self.frames[self.get_frame_class("MatchStatsFrame")]
        match_stats_frame.populate_stats(stats)

    def capture_screenshot(self, is_it_player: bool, delay: int | None = None) -> None:
        '''Capture a screenshot after a delay.

        Args:
            is_it_player (bool): Whether the screenshot is a specific player's match stats or match overview
            delay (int | None, optional): Delay before taking the screenshot. If None,
                uses the application's `screenshot_delay` (defaults to
                `App.DEFAULT_SCREENSHOT_DELAY`).
        '''
        if delay is None:
            delay = self.screenshot_delay
        global PROJECT_ROOT
        print(f"Capturing screenshot in {delay} seconds...")
        time.sleep(delay)
        capture_folder = PROJECT_ROOT / "screenshots"
        capture_folder.mkdir(parents=True, exist_ok=True)
        filename = f"stats_capture_{int(time.time())}.png"
        self.screenshot_path = capture_folder / filename
        
        pyautogui.screenshot(self.screenshot_path)

        print(f"Screenshot saved to {self.screenshot_path}")
        
    
    def get_latest_screenshot_path(self) -> Path:
        global PROJECT_ROOT
        screenshots_dir = PROJECT_ROOT / "screenshots"
        if not screenshots_dir.exists():
            raise FileNotFoundError("Screenshots directory does not exist.")
        
        screenshot_files = list(screenshots_dir.glob("stats_capture_*.png"))
        if not screenshot_files:
            raise FileNotFoundError("No screenshots found in the screenshots directory.")
        
        latest_screenshot = max(screenshot_files, key=lambda p: p.stat().st_mtime)
        return latest_screenshot
    
    def detect_stats(self, is_it_player: bool) -> dict:
        latest_screenshot_path = self.get_latest_screenshot_path()
        
        # load coordinates from JSON file
        coordinates_path = PROJECT_ROOT / "config" / "coordinates.json"
        with open(coordinates_path, 'r') as f:
            coordinates = json.load(f)
        
        # import OCR model
        ocr_model = ocr.load_ocr_model()
        
        # load the latest screenshot for processing
        screenshot_image = cv.imread(str(latest_screenshot_path))
        
        decimal_stats = ['xG']
        
        results = {}
        
        for screen_name, screen_data in coordinates.items():
            for team_name, team_data in screen_data.items():
                results[team_name] = {}
                for stat_name, roi in team_data.items():
                    x1 = roi['x1']
                    y1 = roi['y1']
                    x2 = roi['x2']
                    y2 = roi['y2']
                    stat_roi = (x1, y1, x2, y2)

                    recognised_number = ocr.recognise_number(
                        full_screenshot=screenshot_image,
                        roi=stat_roi,
                        ocr_model=ocr_model
                    )
                    
                    if stat_name in decimal_stats:
                        recognised_number = str(recognised_number)
                        if len(recognised_number) > 1:
                            recognised_number = recognised_number[:-1] + '.' + recognised_number[-1]
                        recognised_number = float(recognised_number)
                    
                    results[team_name][stat_name] = recognised_number
        
        return results        