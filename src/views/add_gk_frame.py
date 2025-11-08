import customtkinter as ctk

class AddGKFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict):
        '''Initializes the goalkeeper attribute entry frame for the application.
        Sets up input fields for player details and goalkeeper attributes, and configures the layout.

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
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=0)
        self.grid_rowconfigure(6, weight=1)
        
        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter name here",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.name_entry.grid(row=1, column=1, pady=(10, 5), sticky="ew")
        
        self.season_entry = ctk.CTkEntry(
            self,
            placeholder_text="Season (e.g., 25/26)",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.season_entry.grid(row=2, column=2, pady=(10, 5), sticky="ew")

        self.base_attr_row = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.base_attr_row.grid(row=3, column=1, pady=(5, 10), sticky="nsew")
        self.base_attr_row.grid_columnconfigure(0, weight=1)
        self.base_attr_row.grid_columnconfigure(1, weight=0)
        self.base_attr_row.grid_columnconfigure(2, weight=0)
        self.base_attr_row.grid_columnconfigure(3, weight=0)
        self.base_attr_row.grid_columnconfigure(4, weight=0)
        self.base_attr_row.grid_columnconfigure(5, weight=1)
        self.base_attr_row.grid_rowconfigure(0, weight=1)
        
        self.age_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Age",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.age_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (cm)",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.height_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (kg)",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.weight_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.country_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.attributes_grid = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.attributes_grid.grid(row=4, column=1, pady=(0, 10), sticky="nsew")

        attr_names = ["Diving", "Handling", "Kicking", "Reflexes", "Positioning"]
        
        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=1)
        for i in range(len(attr_names)):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, attr in enumerate(attr_names):
            self.create_attribute_row(i, attr, theme)
        
        self.done_button = ctk.CTkButton(
            self,
            text="Done",
            font=theme["fonts"]["button"],
            fg_color=theme["colors"]["button_bg"],
            hover_color=theme["colors"]["accent"],
            text_color=theme["colors"]["secondary_text"],
            command=lambda: self.on_done_button_press()
        )
        self.done_button.grid(row=5, column=1, pady=(0, 20), sticky="ew")
    
    def create_attribute_row(self, row: int, attr_name: str, theme: dict) -> None:
        '''Creates a row in the attributes grid for a specific goalkeeper attribute.
        Adds a label and entry field for the attribute to the grid layout.

        Args:
            row (int): The row index in the grid.
            attr_name (str): The name of the attribute.
            theme (dict): The theme dictionary containing color and font settings.
        '''
        attr_label = ctk.CTkLabel(
            self.attributes_grid,
            text=attr_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        attr_label.grid(row=row, column=1, padx=5, pady=5)
        
        attr_var = ctk.StringVar(value="")  
        self.attr_vars[attr_name] = attr_var      
        self.attr_entry = ctk.CTkEntry(
            self.attributes_grid,
            textvariable=attr_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.attr_entry.grid(row=row, column=2, padx=5, pady=5)
    
    def populate_stats(self, stats: dict) -> None:
        ''' Populates the goalkeeper attribute entry fields with detected statistics.
        Updates the input fields for each attribute using the provided stats dictionary.

        Args:
            stats (dict): A dictionary containing attribute names and their corresponding values.
        '''
        if not stats:
            raise self.controller.UIPopulationError("Received no data to populate GK attributes.")
        key_to_display_name = {
            "diving": "Diving",
            "handling": "Handling",
            "kicking": "Kicking",
            "reflexes": "Reflexes",
            "positioning": "Positioning"
        }
        
        for key, display_name in key_to_display_name.items():
            self.attr_vars[display_name].set(str(stats.get(key, "")))
    
    def on_done_button_press(self) -> None:
        """
        Handles the event when the 'Done' button is pressed on the goalkeeper attributes page.
        Collects the entered attribute and player data, saves it through the controller, and navigates back to the player library frame.
        """
        ui_data = {name: var.get() for name, var in self.attr_vars.items()}
        ui_data["name"] = self.name_entry.get()
        ui_data["age"] = self.age_entry.get()
        ui_data["height"] = self.height_entry.get()
        ui_data["weight"] = self.weight_entry.get()
        ui_data["country"] = self.country_entry.get()
        
        self.controller.data_manager.add_or_update_player(ui_data, position="GK")

        self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))