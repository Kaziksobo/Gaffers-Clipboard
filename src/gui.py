import tkinter as tk
from src.ocr import load_templates, recognise_digit, get_stat_roi
from src.theme import THEME

class App:
    '''Main application class for the gaffer's clipboard.
    '''
    def __init__(self):
        '''Initialize the application.
        '''
        self.root = tk.Tk()
        self.root.title("The gaffer's clipboard")
        self.root.geometry("800x600")
        
        main_menu_frame = tk.Frame(self.root, bg=THEME["colors"]["background"])
        main_menu_frame.pack(fill="both", expand=True)
        
        welcome_label = tk.Label(
            main_menu_frame,
            text="Welcome back, gaffer!",
            font=THEME["fonts"]["title"],
            fg=THEME["colors"]["primary_text"],
            bg=THEME["colors"]["background"]
        )
        welcome_label.pack(pady=(50, 10))

        sub_label = tk.Label(
            main_menu_frame,
            text="What would you like to do",
            font=THEME["fonts"]["body"],
            fg=THEME["colors"]["secondary_text"],
            bg=THEME["colors"]["background"]
        )
        sub_label.pack(pady=(0, 50))
        
        add_match_button = tk.Button(
            main_menu_frame,
            text="Add Match",
            font=THEME["fonts"]["button"],
            fg=THEME["colors"]["primary_text"],
            bg=THEME["colors"]["button_bg"],
        )
        add_match_button.pack(pady=10)
        
        update_attributes_button = tk.Button(
            main_menu_frame,
            text="Update Player Attributes",
            font=THEME["fonts"]["button"],
            fg=THEME["colors"]["primary_text"],
            bg=THEME["colors"]["button_bg"],
        )
        update_attributes_button.pack(pady=10)

    def capture_and_recognise(self):
        '''Capture the screen and recognise the stats.
        '''
        image_path = "C:\\Users\\kazik\\projects\\OCRtest\\source_images\\defending.png"
        coords = (704, 105, 722, 128)
        templates = load_templates()
        roi_image = get_stat_roi(image_path, coords)
        recognised_digit = recognise_digit(roi_image, templates)
        self.info_label.config(text=f"Recognised Digit: {recognised_digit}")
        
    def run(self):
        self.root.mainloop()