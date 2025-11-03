import customtkinter as ctk

class AddOutfieldFrame1(ctk.CTkFrame):
    def __init__(self, parent, controller, theme):
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
        self.grid_rowconfigure(5, weight=1)
        
        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter name here",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.name_entry.grid(row=1, column=1, pady=(10, 5), sticky="ew")
        
        self.base_attr_row = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.base_attr_row.grid(row=2, column=1, pady=(5, 10), sticky="nsew")
        self.base_attr_row.grid_columnconfigure(0, weight=1)
        self.base_attr_row.grid_columnconfigure(1, weight=0)
        self.base_attr_row.grid_columnconfigure(2, weight=0)
        self.base_attr_row.grid_columnconfigure(3, weight=0)
        self.base_attr_row.grid_columnconfigure(4, weight=0)
        self.base_attr_row.grid_columnconfigure(5, weight=0)
        self.base_attr_row.grid_columnconfigure(6, weight=1)
        self.base_attr_row.grid_rowconfigure(0, weight=1)
        
        self.position_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Position",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.position_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.age_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Age",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.age_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        self.height_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Height (cm)",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.height_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        self.weight_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Weight (kg)",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.weight_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.country_entry = ctk.CTkEntry(
            self.base_attr_row,
            placeholder_text="Country",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.country_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        
        self.attributes_grid = ctk.CTkScrollableFrame(self, fg_color=theme["colors"]["background"])
        self.attributes_grid.grid(row=3, column=1, pady=(0, 10), sticky="nsew")
        
        attr_names_physical = ["Acceleration", "Agility", "Balance", "Jumping", "Sprint Speed", "Stamina", "Strength"]
        attr_names_mental = ["Aggression", "Att. Position", "Composure", "Interceptions", "Reactions", "Vision"]
        
        self.attributes_grid.grid_columnconfigure(0, weight=1)
        self.attributes_grid.grid_columnconfigure(1, weight=0)
        self.attributes_grid.grid_columnconfigure(2, weight=0)
        self.attributes_grid.grid_columnconfigure(3, weight=0)
        self.attributes_grid.grid_columnconfigure(4, weight=0)
        self.attributes_grid.grid_columnconfigure(5, weight=1)
        for i in range(max(len(attr_names_physical), len(attr_names_mental))):
            self.attributes_grid.grid_rowconfigure(i, weight=1)
        
        for i, attr in enumerate(attr_names_physical):
            self.create_stat_row(i, attr, theme, physical=True)

        for i, attr in enumerate(attr_names_mental):
            self.create_stat_row(i, attr, theme, physical=False)
        
        self.next_page_button = ctk.CTkButton(
            self,
            text="Next Page",
            font=theme["fonts"]["button"],
            fg_color=theme["colors"]["button_bg"],
            hover_color=theme["colors"]["accent"],
            text_color=theme["colors"]["secondary_text"],
            command=lambda: self.on_next_page()
        )
        self.next_page_button.grid(row=4, column=1, pady=(5, 10), sticky="ew")
    
    def create_stat_row(self, index, attr_name, theme, physical=True):
        attr_label = ctk.CTkLabel(
            self.attributes_grid,
            text=attr_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        attr_label.grid(row=index, column=1 if physical else 3, padx=5, pady=5, sticky="w")
        
        attr_var = ctk.StringVar(value="")
        self.attr_vars[attr_name] = attr_var
        self.attr_entry = ctk.CTkEntry(
            self.attributes_grid,
            textvariable=attr_var,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.attr_entry.grid(row=index, column=2 if physical else 4, padx=5, pady=5, sticky="ew")
    
    def populate_stats(self, stats):
        key_to_display_name = {
            "acceleration": "Acceleration",
            "agility": "Agility",
            "balance": "Balance",
            "jumping": "Jumping",
            "sprint_speed": "Sprint Speed",
            "stamina": "Stamina",
            "strength": "Strength",
            "aggression": "Aggression",
            "att_position": "Att. Position",
            "composure": "Composure",
            "interceptions": "Interceptions",
            "reactions": "Reactions",
            "vision": "Vision"
        }
        for key, display_name in key_to_display_name.items():
            self.attr_vars[display_name].set(str(stats.get(key, "")))
    
    def on_next_page(self):
        self.controller.process_player_attributes(gk=False, first=False)
        self.controller.show_frame(self.controller.get_frame_class("AddOutfieldFrame2"))