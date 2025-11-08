import customtkinter as ctk

class AddOutfieldFrame2(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict):
        '''Initializes the outfield player attribute entry frame for the second page.
        Sets up input fields for technical attributes and configures the layout.

        Args:
            parent: The parent widget for this frame.
            controller: The main application controller.
            theme (dict): The theme dictionary containing color and font settings.
        '''
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        self.attr_vars = {}
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=5)
        
        self.title = ctk.CTkLabel(
            self,
            text="Page 2 - Technical Attributes",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.title.grid(row=1, column=1, pady=(20, 10))
        
        self.attributes_grid = ctk.CTkScrollableFrame(self, fg_color=theme["colors"]["background"])
        self.attributes_grid.grid(row=2, column=1, pady=(10, 20), sticky="nsew")
        
        attr_names = ["Ball Control", "Crossing", "Curve", "Def. Awareness", "Dribbling", "FK Accuracy", "Finishing", "Heading Acc.",
                      "Long Pass", "Long Shots", "Penalties", "Short Pass", "Shot Power", "Slide Tackle", "Stand Tackle", "Volleys"]
        
        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=0)
        self.attributes_grid.grid_columnconfigure(4, weight=0)
        self.attributes_grid.grid_columnconfigure(5, weight=1)
        # Use half the list height so the left and right columns share the same rows
        half = len(attr_names) // 2
        for i in range(half):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, attr in enumerate(attr_names):
            self.create_stat_row(i, attr, theme)
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            fg_color=theme["colors"]["button_bg"],
            text_color=theme["colors"]["secondary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=3, column=1, pady=(0, 20), sticky="ew")

    def create_stat_row(self, index: int, attr_name: str, theme: dict) -> None:
        '''Creates a row in the attributes grid for a specific technical attribute.
        Adds a label and entry field for the attribute to the grid layout, placing it in the correct column.

        Args:
            index (int): The index of the attribute in the list.
            attr_name (str): The name of the attribute to display.
            theme (dict): The theme dictionary containing color and font settings.
        '''
        # place items in two columns but on the same row index (row = index % half)
        half = 8  # number of rows per column (for a 16-item list)
        row = index % half
        # decide which side this attribute belongs to
        if index < half:
            left_column_label = 1
            label_col = left_column_label
            left_column_entry = 2
            entry_col = left_column_entry
        else:
            right_column_label = 3
            label_col = right_column_label
            right_column_entry = 4

            entry_col = right_column_entry

        attr_label = ctk.CTkLabel(
            self.attributes_grid,
            text=attr_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        attr_label.grid(row=row, column=label_col, padx=5, pady=5, sticky="w")

        attr_var = ctk.StringVar(value="")
        self.attr_vars[attr_name] = attr_var
        attr_entry = ctk.CTkEntry(
            self.attributes_grid,
            textvariable=attr_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        attr_entry.grid(row=row, column=entry_col, padx=5, pady=5, sticky="ew")
    
    def populate_stats(self, stats: dict) -> None:
        '''Populates the technical attribute entry fields with detected statistics.
        Updates the input fields for each technical attribute using the provided stats dictionary.

        Args:
            stats (dict): A dictionary containing attribute names and their corresponding values.
        '''
        if not stats:
            raise self.controller.UIPopulationError("Received no data to populate outfield player attributes.")
        key_to_display_name = {
            "ball_control": "Ball Control",
            "crossing": "Crossing",
            "curve": "Curve",
            "defensive_awareness": "Def. Awareness",
            "dribbling": "Dribbling",
            "fk_accuracy": "FK Accuracy",
            "finishing": "Finishing",
            "heading_accuracy": "Heading Acc.",
            "long_pass": "Long Pass",
            "long_shots": "Long Shots",
            "penalties": "Penalties",
            "short_pass": "Short Pass",
            "shot_power": "Shot Power",
            "slide_tackle": "Slide Tackle",
            "stand_tackle": "Stand Tackle",
            "volleys": "Volleys"
        }
        for key, display_name in key_to_display_name.items():
            self.attr_vars[display_name].set(str(stats.get(key, "")))
    
    def on_done_button_press(self) -> None:
        """
        Handles the event when the 'Done' button is pressed on the technical attributes page.
        Collects the entered attribute data, saves it through the controller, and navigates back to the player library frame.
        """
        data_page_2 = {name: var.get() for name, var in self.attr_vars.items()}
        self.controller.save_outfield_player(data_page_2)
        
        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))