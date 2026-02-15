from pathlib import Path
import json
import time
import logging

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, data_folder: Path):
        """
        Initializes the DataManager with the specified data folder. 
        Loads player and match data from JSON files, creating them if they do not exist.

        Args:
            data_folder (Path): The directory where player and match data will be stored.
        """
        self.data_folder = data_folder
        self.data_folder.mkdir(exist_ok=True)
        
        self.current_career = None
        self.careers_details_path = self.data_folder / "careers_details.json"
        
        self.players_path = None
        self.matches_path = None
        
        self.players = []
        self.matches = []
    
    def _load_json(self, path: Path, default=None):
        """
        Loads JSON data from the specified file path. 
        Returns the default value if the file does not exist or is invalid.

        Args:
            path (Path): The path to the JSON file.
            default: The value to return if loading fails, defaults to an empty list.

        Returns:
            The loaded JSON data, or the default value if loading fails.
        """
        if default is None:
            default = []
        if not path.exists():
            logger.warning(f"File not found at {path}. Returning default value.")
            return default
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading JSON from {path}: {e}", exc_info=True)
            return default
    
    def _save_json(self, path: Path, data=None):
        """
        Saves the provided data as JSON to the specified file path.
        Overwrites the file if it already exists.

        Args:
            path (Path): The path to the JSON file.
            data: The data to be saved as JSON, defaults to an empty list.
        """
        if data is None:
            data = []
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save JSON to {path}: {e}", exc_info=True)
    
    def create_new_career(self, club_name: str, manager_name: str, starting_season: str, half_length: str, difficulty: str) -> None:
        """
        Creates a new career for the given club and starting season. 
        Sets up the career's storage structure and records its configuration and metadata.

        Args:
            club_name (str): The display name of the club associated with the new career.
            manager_name (str): The name of the manager for the new career.
            starting_season (str): The season identifier marking when the career begins.
            half_length (str): The configured length of each half for matches in this career.
            difficulty (str): The difficulty level associated with this career.
        """
        logger.info(f"Creating new career: {club_name} (Manager: {manager_name})")
        
        career_folder_name = club_name.replace(" ", "_")
        self.current_career = career_folder_name
        career_path = self.data_folder / career_folder_name
        career_path.mkdir(exist_ok=True)
        self.players_path = self.data_folder / career_folder_name / "players.json"
        self.matches_path = self.data_folder / career_folder_name / "matches.json"
        
        # Update careers_details.json
        careers_details = self._load_json(self.careers_details_path)
        career_id = self._generate_id(careers_details)
        
        career_detail = {
            "id": career_id,
            "club_name": club_name,
            "folder_name": career_folder_name,
        }
        
        careers_details.append(career_detail)
        self._save_json(self.careers_details_path, careers_details)
        
        # Create a metadata file for the career
        career_metadata = {
            "career_id": career_id,
            "club_name": club_name,
            "folder_name": career_folder_name,
            "manager_name": manager_name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "starting_season": starting_season,
            "half_length": half_length,
            "difficulty": difficulty
        }
        self._save_json(career_path / "metadata.json", career_metadata)
        

        # Initialize empty players and matches files
        self._save_json(self.players_path)
        self._save_json(self.matches_path)
    
    def get_all_career_names(self) -> list[str]:
        """
        Retrieves the names of all stored careers. 
        Returns a list containing only the display names for each known career.

        Returns:
            list[str]: A list of career names loaded from the careers details store.
        """
        careers_details = self._load_json(self.careers_details_path)
        return [career.get("club_name") for career in careers_details]
    
    def get_career_details(self, career_name: str) -> dict | None:
        """
        Retrieves the stored details for a specific career by name. 
        Searches the careers data and returns the matching career record if it exists.

        Args:
            career_name (str): The display name of the career to look up.

        Returns:
            dict | None: The career details dictionary if found, otherwise None.
        """
        careers_details = self._load_json(self.careers_details_path)
        career_folder_path = next(
            (
                career.get("folder_name")
                for career in careers_details
                if career.get("club_name") == career_name
            ),
            None,
        )
        if not career_folder_path:
            return None
        metadata_path = self.data_folder / career_folder_path / "metadata.json"
        return self._load_json(metadata_path)
    
    def load_career(self, career_name: str) -> None:
        """
        Loads an existing career and prepares it for further data operations.
        Updates the current career context and loads associated players and matches into memory.

        Args:
            career_name (str): The display name of the career to load.
        """
        logger.info(f"Loading career context: {career_name}")
        career_details = self.get_career_details(career_name)
        if not career_details:
            logger.warning(f"Career '{career_name}' not found.")
            return
        career_folder_name = career_details.get("folder_name")
        self.current_career = career_folder_name
        self.players_path = self.data_folder / career_folder_name / "players.json"
        self.matches_path = self.data_folder / career_folder_name / "matches.json"
        
        self.players = self._load_json(self.players_path)
        self.matches = self._load_json(self.matches_path)
        logger.info(f"Career {career_name} loaded with {len(self.players)} players and {len(self.matches)} matches.")

    def refresh_players(self) -> None:
        self.players = self._load_json(self.players_path)

    def refresh_matches(self) -> None:
        self.matches = self._load_json(self.matches_path)
    
    def add_or_update_player(self, player_ui_data: dict, position: str, season: str) -> None:
        """
        Adds a new player or updates an existing player's attribute history.
        Uses the player's name to determine if the player already exists and appends new attribute data if so.

        Args:
            player_ui_data (dict): Dictionary containing player information and attributes.
            position (str): The position of the player.
            season (str): The season associated with the attribute snapshot.
        """
        # Check if player already exists based on name to update them
        # May end up changing this to use ids in the future
        full_name = player_ui_data.get("name").strip().lower()
        existing_player = next((p for p in self.players if p.get("name").strip().lower() == full_name), None)
        
        non_attributes = ["name", "age", "height", "weight", "country"]
        
        attributes = {k: v for k, v in player_ui_data.items() if k not in non_attributes}
        attributes_snapshot = {
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "season": season,
            **attributes
        }
        
        if existing_player:
            logger.info(f"Updating player: {full_name}")
            existing_player["attribute_history"].append(attributes_snapshot)
            # If age, height or weight are different, update it
            if existing_player.get("age") != player_ui_data.get("age").strip():
                existing_player["age"] = player_ui_data.get("age").strip()
            if existing_player.get("height") != player_ui_data.get("height").strip():
                existing_player["height"] = player_ui_data.get("height").strip()
            if existing_player.get("weight") != player_ui_data.get("weight").strip():
                existing_player["weight"] = player_ui_data.get("weight").strip()
            # If position is new, add it
            if position not in existing_player.get("positions", []):
                existing_player["positions"].append(position)
        else:
            logger.info(f"Adding new player: {full_name}")
            new_player = {
                "id": self._generate_id(self.players),
                "name": full_name,
                "nationality": player_ui_data.get("country").strip(),
                "age": player_ui_data.get("age").strip(),
                "height": player_ui_data.get("height").strip(),
                "weight": player_ui_data.get("weight").strip(),
                "positions": [position],
                "attribute_history": [attributes_snapshot],
                "financial_history": [],
                "sold": False,
                "loaned": False
            }
            self.players.append(new_player)
        self._save_json(self.players_path, self.players)
        # Reload players to ensure consistency
        self.players = self._load_json(self.players_path)
    
    def add_financial_data(self, player_name: str, financial_data: dict, season: str) -> None:
        """
        Adds a financial data snapshot to the specified player's financial history.

        Args:
            player_name (str): The name of the player to update.
            financial_data (dict): A dictionary containing financial details to be added.
            season (str): The season associated with the financial snapshot.
        """
        full_name = player_name.strip().lower()
        existing_player = next((p for p in self.players if p.get("name").strip().lower() == full_name), None)
        
        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot add financial data.")
            return
        
        logger.info(f"Saving financial snapshot for {player_name} (Season: {season})")
        
        # Remove any commas from numeric fields
        for key, value in financial_data.items():
            if isinstance(value, str):
                financial_data[key] = value.replace(",", "")
        
        financial_snapshot = {
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "season": season,
            **financial_data
        }
        
        existing_player["financial_history"].append(financial_snapshot)
        self._save_json(self.players_path, self.players)
        # Reload players to ensure consistency
        self.players = self._load_json(self.players_path)
    
    def sell_player(self, player_name: str) -> None:
        logger.info(f"Action: Selling player {player_name}")
        self._update_player_status(player_name, "sold", True)
    
    def loan_out_player(self, player_name: str) -> None:
        logger.info(f"Action: Loaning out player {player_name}")
        self._update_player_status(player_name, "loaned", True)
    
    def return_loan_player(self, player_name: str) -> None:
        logger.info(f"Action: Returning player {player_name} from loan")
        self._update_player_status(player_name, "loaned", False)
        
    def _update_player_status(self, player_name: str, status_key: str, status_value: bool):
        full_name = player_name.strip().lower()
        existing_player = next((p for p in self.players if p.get("name").strip().lower() == full_name), None)
        
        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot update status '{status_key}'.")
            return
            
        existing_player[status_key] = status_value
        self._save_json(self.players_path, self.players)
        
        # Reload players to ensure consistency
        self.players = self._load_json(self.players_path)
    
    def _generate_id(self, collection: list) -> int:
        """
        Generates a unique integer ID for a new item in the given collection.
        The ID is one greater than the current maximum ID in the collection, or 1 if the collection is empty.

        Args:
            collection (list): A list of dictionaries, each potentially containing an 'id' key.

        Returns:
            int: The next available unique ID.
        """
        return max(item.get("id", 0) for item in collection) + 1 if collection else 1
    
    def _find_player_id_by_name(self, name: str) -> int | None:
        """
        Finds the unique ID of a player by their name.
        Returns the player's ID if a matching name is found, otherwise returns None.

        Args:
            name (str): The name of the player to search for.

        Returns:
            int | None: The player's unique ID if found, or None if not found.
        """
        if not name:
            return None
        name_norm = name.strip().lower()
        return next(
            (
                player.get("id")
                for player in self.players
                if player.get("name", "").strip().lower() == name_norm
            ),
            None,
        )
    
    def add_match(self, match_data: dict, player_performances: list[dict]):
        match_id = self._generate_id(self.matches)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"Adding match {match_id} with {len(player_performances)} player performances.")
        
        normalised_performances = []
        for perf in player_performances:
            perf_copy = perf.copy()
            perf_copy["player_id"] = self._find_player_id_by_name(perf_copy.get("player_name", ""))
            perf_copy.pop("player_name", None)  # Remove name after finding ID
            normalised_performances.append(perf_copy)
        
        new_match = {
            "id": match_id,
            "datetime": timestamp,
            "data": match_data,
            "player_performances": normalised_performances
        }
        self.matches.append(new_match)
        self._save_json(self.matches_path, self.matches)
        # Reload matches to ensure consistency
        self.matches = self._load_json(self.matches_path)