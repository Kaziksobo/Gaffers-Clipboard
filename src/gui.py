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
        
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        
        for F in (MainMenuFrame,):
            frame = F(container, THEME)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame(MainMenuFrame)
        
    def show_frame(self, page_class):
        frame = self.frames[page_class]
        frame.tkraise()
        

    # def capture_and_recognise(self):
    #     '''Capture the screen and recognise the stats.
    #     '''
    #     image_path = "C:\\Users\\kazik\\projects\\OCRtest\\source_images\\defending.png"
    #     coords = (704, 105, 722, 128)
    #     templates = load_templates()
    #     roi_image = get_stat_roi(image_path, coords)
    #     recognised_digit = recognise_digit(roi_image, templates)
    #     self.info_label.config(text=f"Recognised Digit: {recognised_digit}")
