from src.ocr import load_templates, recognise_digit, get_stat_roi
from src.theme import THEME
import customtkinter as ctk

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("800x600")
        self.minsize(600, 400)
        # Main Frame
        self.home_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["colors"]["background"]
        )
        self.home_frame.pack(expand=True, fill="both")
        self.home_frame.pack_propagate(False)
        self.home_frame.pack(expand=True, fill="both")
        self.home_frame.pack_propagate(False)
        
        # Setting up grid
        self.home_frame.grid_columnconfigure(0, weight=1)
        self.home_frame.grid_columnconfigure(1, weight=0)
        self.home_frame.grid_columnconfigure(2, weight=1)
        self.home_frame.grid_rowconfigure(0, weight=1)
        self.home_frame.grid_rowconfigure(4, weight=1)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self.home_frame, 
            text="Welcome to Gaffer's Clipboard!",
            font=THEME["fonts"]["title"],
            text_color=THEME["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        # Question Label
        self.question_label = ctk.CTkLabel(
            self.home_frame, text="What would you like to do?",
            font=THEME["fonts"]["body"],
            text_color=THEME["colors"]["secondary_text"]
        )
        self.question_label.grid(row=2, column=1, pady=10)
        
        # Buttons Frame
        self.button_frame = ctk.CTkFrame(
            self.home_frame,
            fg_color=THEME["colors"]["background"]
            )
        self.button_frame.grid(row=3, column=1, pady=20)

        # Player Update Button
        self.player_update_button = ctk.CTkButton(
            self.button_frame, 
            text="Update player attributes",
            fg_color=THEME["colors"]["button_bg"],
            bg_color=THEME["colors"]["background"],
            font=THEME["fonts"]["button"],
            text_color=THEME["colors"]["primary_text"],
            hover_color=THEME["colors"]["accent"]
        )
        self.player_update_button.pack(side="left", padx=(0, 10), pady=10)

        # Add Match Button
        self.add_match_button = ctk.CTkButton(
            self.button_frame, text="Add new match",
            fg_color=THEME["colors"]["button_bg"],
            bg_color=THEME["colors"]["background"],
            font=THEME["fonts"]["button"],
            text_color=THEME["colors"]["primary_text"],
            hover_color=THEME["colors"]["accent"]
        )
        self.add_match_button.pack(side="right", padx=(10, 0), pady=10)

    # def capture_and_recognise(self):
    #     '''Capture the screen and recognise the stats.
    #     '''
    #     image_path = "C:\\Users\\kazik\\projects\\OCRtest\\source_images\\defending.png"
    #     coords = (704, 105, 722, 128)
    #     templates = load_templates()
    #     roi_image = get_stat_roi(image_path, coords)
    #     recognised_digit = recognise_digit(roi_image, templates)
    #     self.info_label.config(text=f"Recognised Digit: {recognised_digit}")
