import customtkinter as ctk

class PlayerStatsFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme):
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=1)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Player Statistics collected",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Info Label
        self.info_label = ctk.CTkLabel(
            self, text="Empty stats couldn't be recognised and require manual entry.\n Please review and update player attributes as necessary.",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=2, column=1, pady=(0, 20))
        
        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self, fg_color=theme["colors"]["background"])
        self.stats_grid.grid(row=3, column=1, pady=(0, 20), sticky="nsew")

        stat_names = ['Goals', 'Assists', 'Shots', 'Shots on target', 'xG', 'Passes', 'Passes completed', 'Key passes', 'Dribbles', 'Dribbles completed', 'Tackles completed', 'Fouls committed', 'Possession won', 'Possession lost', 'Minutes played', 'Distance covered']
        # Configure subgrid
        for col in range(5):
            self.stats_grid.grid_columnconfigure(col, weight=1)
        for row in range(len(stat_names)):
            self.stats_grid.grid_rowconfigure(row, weight=1)

        # Populate subgrid with placeholder labels
        self.user_team_name = ctk.CTkLabel(
            self.stats_grid,
            text="User Team",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.user_team_name.grid(row=0, column=0, padx=5, pady=5)
        
        self.user_team_score = ctk.CTkLabel(
            self.stats_grid,
            text="0",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.user_team_score.grid(row=0, column=1, padx=5, pady=5)

        self.score_dash = ctk.CTkLabel(
            self.stats_grid,
            text="-",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.score_dash.grid(row=0, column=2, padx=5, pady=5)
        self.opponent_team_score = ctk.CTkLabel(
            self.stats_grid,
            text="0",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.opponent_team_score.grid(row=0, column=3, padx=5, pady=5)
        
        self.opponent_team_name = ctk.CTkLabel(
            self.stats_grid,
            text="Opponent Team",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.opponent_team_name.grid(row=0, column=4, padx=5, pady=5)
        
        for i, stat in enumerate(stat_names):
            self.create_stat_row(i+1, stat, theme)
        
        # Direction label
        self.direction_label = ctk.CTkLabel(
            self, text="Please navigate to the next player's stats",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.direction_label.grid(row=4, column=1, pady=(0, 20))
    
    def create_stat_row(self, row, stat_name, theme):
        self.user_stat_value = ctk.StringVar(value="0")
        self.user_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.user_stat_value,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.user_stat_entry.grid(row=row, column=0, padx=5, pady=5)
        self.stat_label = ctk.CTkLabel(
            self.stats_grid,
            text=stat_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.stat_label.grid(row=row, column=2, padx=5, pady=5)
        self.opponent_stat_value = ctk.StringVar(value="0")
        self.opponent_stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=self.opponent_stat_value,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.opponent_stat_entry.grid(row=row, column=4, padx=5, pady=5)
