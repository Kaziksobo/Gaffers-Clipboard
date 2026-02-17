from pathlib import Path
import json
import time
import logging
from typing import List, Optional, Union
from pydantic import ValidationError, TypeAdapter
from datetime import datetime

from src.types import (
    GKAttributeSnapshot,
    OutfieldAttributeSnapshot,
    FinancialSnapshot,
    Player,
    MatchStats,
    MatchData,
    OutfieldPlayerPerformance,
    GoalkeeperPerformance,
    Match,
    CareerMetadata,
    CareerDetail
)

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
        
        self.current_career: Optional[str] = None
        self.careers_details_path = self.data_folder / "careers_details.json"
        
        self.players_path: Optional[Path] = None
        self.matches_path: Optional[Path] = None
        
        self.players: List[Player] = []
        self.matches: List[Match] = []
    
    def _load_json(self, path: Path, model_class, is_list: bool = True, default=None):
        """
        Loads JSON data from the specified file path. 
        Returns the default value if the file does not exist or is invalid.

        Args:
            path (Path): The path to the JSON file.
            model_class: The Pydantic model class to validate against.
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
                raw_data = json.load(f)
            
            adapter = TypeAdapter(List[model_class] if is_list else model_class)
            return adapter.validate_python(raw_data)
        except (json.JSONDecodeError, IOError, ValidationError) as e:
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
            return
        try:
            data = [item.model_dump(mode="json") for item in data]
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
        
        self.players_path = career_path / "players.json"
        self.matches_path = career_path / "matches.json"
        
        # Update careers_details.json
        careers_details = self._load_json(self.careers_details_path, CareerDetail)
        career_id = self._generate_id(careers_details)
        
        new_detail = CareerDetail(
            id=career_id,
            club_name=club_name,
            folder_name=career_folder_name
        )
        
        careers_details.append(new_detail)
        self._save_json(self.careers_details_path, careers_details)
        
        # Create a metadata file for the career
        metadata = CareerMetadata(
            career_id=career_id,
            club_name=club_name,
            folder_name=career_folder_name,
            manager_name=manager_name,
            created_at=datetime.now(),
            starting_season=starting_season,
            half_length=int(half_length),
            difficulty=difficulty
        )
        with open(career_path / "metadata.json", 'w', encoding='utf-8') as f:
            f.write(metadata.model_dump_json(indent=4))

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
        careers_details = self._load_json(self.careers_details_path, CareerDetail)
        return [career.club_name for career in careers_details]
    
    def get_career_details(self, career_name: str) -> dict | None:
        """
        Retrieves the stored details for a specific career by name. 
        Searches the careers data and returns the matching career record if it exists.

        Args:
            career_name (str): The display name of the career to look up.

        Returns:
            dict | None: The career details dictionary if found, otherwise None.
        """
        careers_details = self._load_json(self.careers_details_path, CareerDetail)
        career_folder_path = next(
            (
                career.folder_name
                for career in careers_details
                if career.club_name == career_name
            ),
            None,
        )
        if not career_folder_path:
            return None
        metadata_path = self.data_folder / career_folder_path / "metadata.json"
        return self._load_json(metadata_path, CareerMetadata, is_list=False, default={})
    
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
        
        self.players = self._load_json(self.players_path, Player)
        self.matches = self._load_json(self.matches_path, Match)
        logger.info(f"Career {career_name} loaded with {len(self.players)} players and {len(self.matches)} matches.")

    def refresh_players(self) -> None:
        self.players = self._load_json(self.players_path, Player)

    def refresh_matches(self) -> None:
        self.matches = self._load_json(self.matches_path, Match)
    
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
        existing_player = next((p for p in self.players if p.name.strip().lower() == full_name), None)
        
        top_level_keys = ["name", "age", "height", "weight", "country"]
        
        attributes = {k: v for k, v in player_ui_data.items() if k not in top_level_keys}
        if position == "GK":
            attributes_snapshot = GKAttributeSnapshot(
                datetime=datetime.now(),
                season=season,
                position_type="GK",
                **attributes
            )
        else:
            attributes_snapshot = OutfieldAttributeSnapshot(
                datetime=datetime.now(),
                season=season,
                position_type="Outfield",
                **attributes
            )
        
        
        if existing_player:
            logger.info(f"Updating player: {full_name}")
            existing_player.attribute_history.append(attributes_snapshot)
            # If age, height or weight are different, update it
            existing_player.age = int(player_ui_data.get("age"))
            existing_player.height = player_ui_data.get("height")
            existing_player.weight = int(player_ui_data.get("weight"))
            # If position is new, add it
            if position not in existing_player.positions:
                existing_player.positions.append(position)
        else:
            logger.info(f"Adding new player: {full_name}")
            new_id = self._generate_id(self.players)
            new_player = Player(
                id=new_id,
                name=full_name,
                nationality=player_ui_data.get("country").strip(),
                age=int(player_ui_data.get("age")),
                height=player_ui_data.get("height").strip(),
                weight=int(player_ui_data.get("weight")),
                positions=[position],
                attribute_history=[attributes_snapshot],
                financial_history=[],
                sold=False,
                loaned=False
            )
            self.players.append(new_player)
        self._save_json(self.players_path, self.players)
        # Reload players to ensure consistency
        self.players = self._load_json(self.players_path, Player)
    
    def add_financial_data(self, player_name: str, financial_data: dict, season: str) -> None:
        """
        Adds a financial data snapshot to the specified player's financial history.

        Args:
            player_name (str): The name of the player to update.
            financial_data (dict): A dictionary containing financial details to be added.
            season (str): The season associated with the financial snapshot.
        """
        full_name = player_name.strip().lower()
        existing_player = next((p for p in self.players if p.name.strip().lower() == full_name), None)

        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot add financial data.")
            return

        logger.info(f"Saving financial snapshot for {player_name} (Season: {season})")

        cleaned_data = {
            k: v.replace(",", "") if isinstance(v, str) else v
            for k, v in financial_data.items()
        }
        snapshot = FinancialSnapshot(
            datetime=datetime.now(),
            season=season,
            **cleaned_data
        )

        existing_player.financial_history.append(snapshot)
        self._save_json(self.players_path, self.players)
        # Reload players to ensure consistency
        self.players = self._load_json(self.players_path, Player)
    
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
        existing_player = next((p for p in self.players if p.name.strip().lower() == full_name), None)
        
        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot update status '{status_key}'.")
            return
            
        setattr(existing_player, status_key, status_value)
        self._save_json(self.players_path, self.players)
        
        # Reload players to ensure consistency
        self.players = self._load_json(self.players_path, Player)
    
    def _generate_id(self, collection: list) -> int:
        """
        Generates a unique integer ID for a new item in the given collection.
        The ID is one greater than the current maximum ID in the collection, or 1 if the collection is empty.

        Args:
            collection (list): A list of dictionaries, each potentially containing an 'id' key.

        Returns:
            int: The next available unique ID.
        """
        return max((item.id for item in collection), default=0) + 1
    
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
                player.id
                for player in self.players
                if player.name.strip().lower() == name_norm
            ),
            None,
        )
    
    def add_match(self, match_data: dict, player_performances: list[dict]):
        match_id = self._generate_id(self.matches)
        timestamp = datetime.now()
        
        logger.info(f"Adding match {match_id} with {len(player_performances)} player performances.")
        
        normalized_performances = []
        for perf in player_performances:
            p_name = perf.get("player_name", "")
            p_id = self._find_player_id_by_name(p_name)
            
            # Remove name, add ID
            perf_data = {k: v for k, v in perf.items() if k != "player_name"}
            perf_data["player_id"] = p_id or 0
            
            if perf.get("performance_type") == "GK":
                normalized_performances.append(GoalkeeperPerformance(**perf_data))
            else:
                normalized_performances.append(OutfieldPlayerPerformance(**perf_data))
        
        new_match = Match(
            id=match_id,
            datetime=timestamp,
            data=MatchData(**match_data),
            player_performances=normalized_performances
        )
        
        self.matches.append(new_match)
        self._save_json(self.matches_path, self.matches)
        # Reload matches to ensure consistency
        self.matches = self._load_json(self.matches_path, Match)