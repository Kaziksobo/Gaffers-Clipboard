from pathlib import Path
import json
import time

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
        
        self.players_path = self.data_folder / "players.json"
        self.matches_path = self.data_folder / "matches.json"
        
        self.players = self._load_json(self.players_path, default=[])
        self.matches = self._load_json(self.matches_path, default=[])
    
    def _load_json(self, path: Path, default):
        """
        Loads JSON data from the specified file path. 
        Returns the default value if the file does not exist or is invalid.

        Args:
            path (Path): The path to the JSON file.
            default: The value to return if loading fails.

        Returns:
            The loaded JSON data, or the default value if loading fails.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default
    
    def _save_json(self, path: Path, data):
        """
        Saves the provided data as JSON to the specified file path.
        Overwrites the file if it already exists.

        Args:
            path (Path): The path to the JSON file.
            data: The data to be saved as JSON.
        """
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    
    def add_or_update_player(self, player_ui_data: dict, position: str, season: str):
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
            existing_player["attribute_history"].append(attributes_snapshot)
        else:
            new_player = {
                "id": self._generate_id(self.players),
                "name": full_name,
                "nationality": player_ui_data.get("country").strip(),
                "age": player_ui_data.get("age").strip(),
                "height": player_ui_data.get("height").strip(),
                "weight": player_ui_data.get("weight").strip(),
                "position": position,
                "attribute_history": [attributes_snapshot]
            }
            self.players.append(new_player)
        self._save_json(self.players_path, self.players)
    
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
        
        normalised_performances = []
        for perf in player_performances:
            perf_copy = perf.copy()
            perf_copy["player_id"] = self._find_player_id_by_name(perf_copy.get("name", ""))
            normalised_performances.append(perf_copy)
        
        new_match = {
            "id": match_id,
            "datetime": timestamp,
            "data": match_data,
            "player_performances": normalised_performances
        }
        self.matches.append(new_match)
        self._save_json(self.matches_path, self.matches)