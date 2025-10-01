from src.ocr import load_templates, recognise_digit, get_stat_roi
from src.theme import THEME
import customtkinter as ctk
from src.views.main_menu_frame import MainMenuFrame

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gaffer's Clipboard")
        self.geometry("800x600")
        self.minsize(600, 400)
        # Show main menu frame
        self.main_menu = MainMenuFrame(self, THEME)

    # def capture_and_recognise(self):
    #     '''Capture the screen and recognise the stats.
    #     '''
    #     image_path = "C:\\Users\\kazik\\projects\\OCRtest\\source_images\\defending.png"
    #     coords = (704, 105, 722, 128)
    #     templates = load_templates()
    #     roi_image = get_stat_roi(image_path, coords)
    #     recognised_digit = recognise_digit(roi_image, templates)
    #     self.info_label.config(text=f"Recognised Digit: {recognised_digit}")
