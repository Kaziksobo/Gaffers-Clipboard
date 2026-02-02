import customtkinter as ctk
from src.exceptions import UIPopulationError
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

class PlayerStatsFrame(ctk.CTkFrame):
    def __init__(self, parent, controller, theme: dict) -> None:
        '''Frame for displaying player statistics in editable text boxes.

        Args:
            parent: The parent CTk window.
            controller: The main application controller.
            theme (dict): The theme dictionary containing colors and fonts.
        '''
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        
        # Attributes to store stat variables
        self.stats_vars = {}
        
        # Setting up grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)
        
        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self,
            text="Player Statistics collected",
            font=theme["fonts"]["title"],
            text_color=theme["colors"]["primary_text"]
        )
        self.main_heading.grid(row=1, column=1, pady=(0, 60))
        
        # Player dropdown (reusable scrollable dropdown)
        self.player_list_var = ctk.StringVar(value="Click here to select player")
        self.player_dropdown = ScrollableDropdown(
            self,
            theme=theme,
            variable=self.player_list_var,
            width=350,
            dropdown_height=200,
            placeholder="Click here to select player"
        )
        self.player_dropdown.grid(row=2, column=1, pady=(0, 20))
        
        # Info Label
        self.info_label = ctk.CTkLabel(
            self, text="Empty stats couldn't be recognised and require manual entry.\n Please review and update player attributes as necessary.",
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=3, column=1, pady=(0, 20))
        
        # Stats Grid
        self.stats_grid = ctk.CTkScrollableFrame(self, fg_color=theme["colors"]["background"])
        self.stats_grid.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        stat_names = ['Goals', 'Assists', 'Shots', 'Shot Accuracy (%)', 'Passes', 'Pass Accuracy (%)', 'Dribbles', 'Dribbles Success Rate (%)', 'Tackles', 'Tackles Success Rate (%)', 'Offsides', 'Fouls Committed', 'Possession Won', 'Possession Lost', 'Minutes Played', 'Distance Covered (km)', 'Distance Sprinted (km)']
        # Configure subgrid
        self.stats_grid.grid_columnconfigure(0, weight=1)
        self.stats_grid.grid_columnconfigure(1, weight=1)
        for row in range(len(stat_names)):
            self.stats_grid.grid_rowconfigure(row, weight=1)

        # Populate stats grid
        for i, stat in enumerate(stat_names):
            self.create_stat_row(i, stat, theme)
        
        # Direction subgrid
        self.direction_frame = ctk.CTkFrame(self, fg_color=theme["colors"]["background"])
        self.direction_frame.grid(row=5, column=1, pady=(0, 20), sticky="nsew")
        self.direction_frame.grid_columnconfigure(0, weight=1)
        self.direction_frame.grid_columnconfigure(1, weight=1)
        self.direction_frame.grid_columnconfigure(2, weight=1)

        self.direction_label = ctk.CTkLabel(
            self.direction_frame,
            text="Please navigate to the next player's stats",
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["body"],
        )
        self.direction_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.next_player_button = ctk.CTkButton(
            self.direction_frame,
            text="Next Player",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_next_player_button_press()
        )
        self.next_player_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.all_players_added_button = ctk.CTkButton(
            self.direction_frame,
            text="All Players Added",
            fg_color=theme["colors"]["button_fg"],
            text_color=theme["colors"]["primary_text"],
            font=theme["fonts"]["button"],
            command=lambda: self.on_done_button_press()
        )
        self.all_players_added_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")

    def create_stat_row(self, row: int, stat_name: str, theme: dict) -> None:
        '''Create a row in the stats grid for a specific statistic.

        Args:
            row (int): The row number in the grid.
            stat_name (str): The name of the statistic.
            theme (dict): The theme dictionary containing colors and fonts.
        '''
        self.stat_label = ctk.CTkLabel(
            self.stats_grid,
            text=stat_name,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"]
        )
        self.stat_label.grid(row=row, column=0, padx=5, pady=5, sticky="w")
        
        stat_value = ctk.StringVar(value="0")
        self.stats_vars[stat_name] = stat_value
        stat_entry = ctk.CTkEntry(
            self.stats_grid,
            textvariable=stat_value,
            font=theme["fonts"]["body"],
            text_color=theme["colors"]["primary_text"],
            fg_color=theme["colors"]["entry_fg"]
        )
        stat_entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    
    def populate_stats(self, stats_data: dict) -> None:
        '''Populates player statistics entry fields with detected statistics
        Updates input fields for each statistic using the provided stats_data dictionary

        Args:
            stats_data (dict): A dictionary containing player statistics for the current match
        '''
        if not stats_data:
            raise UIPopulationError("Received no data to populate player statistics.")
        key_to_display_name = {
            'goals': 'Goals',
            'assists': 'Assists',
            'shots': 'Shots',
            'shot_accuracy': 'Shot Accuracy (%)',
            'passes': 'Passes',
            'pass_accuracy': 'Pass Accuracy (%)',
            'dribbles': 'Dribbles',
            'dribbles_success_rate': 'Dribbles Success Rate (%)',
            'tackles': 'Tackles',
            'tackles_success_rate': 'Tackles Success Rate (%)',
            'offsides': 'Offsides',
            'fouls_committed': 'Fouls Committed',
            'possession_won': 'Possession Won',
            'possession_lost': 'Possession Lost',
            'minutes_played': 'Minutes Played',
            'distance_covered': 'Distance Covered (km)',
            'distance_sprinted': 'Distance Sprinted (km)'
        }
        
        for key, display_name in key_to_display_name.items():
            self.stats_vars[display_name].set(str(stats_data.get(key, "0")))

    def refresh_player_dropdown(self) -> None:
        names = self.controller.get_all_player_names()
        self.player_dropdown.set_values(names or ["No players found"])

    def on_show(self) -> None:
        self.refresh_player_dropdown()
        self.player_dropdown.set_value("Click here to select player")
    
    def collect_data(self) -> dict:
        '''Collects the player statistics data from the entry fields.

        Returns:
            dict: A dictionary containing the collected player statistics.
        '''
        data = {stat_name: var.get() for stat_name, var in self.stats_vars.items()}
        data['player_name'] = self.player_list_var.get()
        self.controller.buffer_player_performance(data)

    def on_next_player_button_press(self) -> None:
        '''Handle the button pressing event, initiating screenshot capture and navigating to PlayerStatsFrame.
        '''
        self.collect_data()
        self.controller.process_player_stats()
        self.controller.show_frame(self.controller.get_frame_class("PlayerStatsFrame"))
    
    def on_done_button_press(self):
        self.collect_data()
        self.controller.save_buffered_match()
        self.controller.show_frame(self.controller.get_frame_class("MatchAddedFrame"))
