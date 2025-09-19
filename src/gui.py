import tkinter as tk
from src.ocr import load_templates, recognise_digit
from src.preprocessing import get_stat_roi

class App:
    '''Main application class for the gaffer's clipboard.
    '''
    def __init__(self):
        '''Initialize the application.
        '''
        self.root = tk.Tk()
        self.root.title("The gaffer's clipboard")
        
        self.info_label = tk.Label(self.root, text="Navigate to the Team Stats screen.")
        self.capture_button = tk.Button(self.root, text="Capture stats", command=self.capture_and_recognise)

        self.info_label.pack()
        self.capture_button.pack()
    
    def capture_and_recognise(self):
        '''Capture the screen and recognise the stats.
        '''
        image_path = "C:\\Users\\kazik\\projects\\OCRtest\\source_images\\match_overview.png"
        coords = (640, 430, 658, 454)
        templates = load_templates()
        roi_image = get_stat_roi(image_path, coords)
        recognised_digit = recognise_digit(roi_image, templates)
        self.info_label.config(text=f"Recognised Digit: {recognised_digit}")
        
    def run(self):
        self.root.mainloop()