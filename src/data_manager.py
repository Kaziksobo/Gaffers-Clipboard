from pathlib import Path
import json
import logging
from typing import List, Optional, Union, Type, TypeVar, Any
from pydantic import ValidationError, TypeAdapter, BaseModel
from datetime import datetime

from src.types import (
    GKAttributeSnapshot,
    OutfieldAttributeSnapshot,
    FinancialSnapshot,
    InjuryRecord,
    Player,
    MatchStats,
    MatchData,
    OutfieldPlayerPerformance,
    GoalkeeperPerformance,
    Match,
    CareerMetadata,
    CareerDetail,
    DifficultyLevel,
    PositionType
)

logger = logging.getLogger(__name__)

# Define a generic type variable bound to Pydantic models
T = TypeVar("T", bound=BaseModel)

class DataManager:
    def __init__(self, data_folder: Path) -> None:
        """Initialize the DataManager with the specified root data directory.

        Sets up the base data folder and defines the path for the global
        careers registry. Specific player and match data are not loaded 
        until a specific career is selected via `load_career`.

        Args:
            data_folder (Path): The root directory where application data is stored.
        """
        self.data_folder = data_folder
        self.data_folder.mkdir(exist_ok=True)
        
        self.current_career: Optional[str] = None
        self.careers_details_path = self.data_folder / "careers_details.json"
        
        # Paths are initialized as None; they are set when a career is selected
        self.players_path: Optional[Path] = None
        self.matches_path: Optional[Path] = None
        
        # In-memory data caches, initially empty
        self.players: list[Player] = []
        self.matches: list[Match] = []
    
    def _load_json(
        self, 
        path: Path, 
        model_class: Type[T], 
        is_list: bool = True, 
        default: Any = None) -> Union[T, List[T], Any]:
        """Load JSON data from the specified file path and validate against a model.

        Args:
            path (Path): The path to the JSON file.
            model_class (Type[T]): The Pydantic model class for validation.
            is_list (bool): Whether the expected data is a list of models. 
                Defaults to True.
            default (Any): The value to return if loading fails. 
                Defaults to [] if is_list is True, else None.

        Returns:
            Union[T, List[T], Any]: The validated model(s) or the default value.
        """
        if default is None:
            default = [] if is_list else None
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
    
    def _save_json(self, path: Path, data: Union[T, List[T], None] = None) -> None:
        """Save the provided data as JSON to the specified file path.

        Automatically handles serialization for both single Pydantic models 
        and lists of models. Overwrites the file if it already exists.

        Args:
            path (Path): The path to the JSON file.
            data (Union[T, List[T], None]): The data to save. 
                If None, an empty list is saved to clear the file.
        """
        if data is None:
            data = []
        try:
            if isinstance(data, list):
                # Dump each item in the list
                export_data = [
                    item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                    for item in data
                ]
            elif isinstance(data, BaseModel):
                # Dump the single model
                export_data = data.model_dump(mode="json")
            else:
                # Fallback for dicts or primitives (e.g. simple config files)
                export_data = data
            
            # Write to file
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4)
        
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save JSON to {path}: {e}", exc_info=True)
    
    def create_new_career(
        self, 
        club_name: str, 
        manager_name: str, 
        starting_season: str, 
        half_length: int, 
        difficulty: DifficultyLevel) -> None:
        """Create a new career for the given club and starting season.

        Sets up the career's storage structure (using a unique folder name), 
        records its configuration, and initializes empty data files.

        Args:
            club_name (str): The display name of the club.
            manager_name (str): The name of the manager.
            starting_season (str): The season identifier (e.g., "24/25").
            half_length (int): The match half length in minutes.
            difficulty (DifficultyLevel): The difficulty level (must match DifficultyLevel type).
        """
        logger.info(f"Creating new career: {club_name} (Manager: {manager_name})")

        # Generate ID first to use in folder name
        careers_details = self._load_json(self.careers_details_path, CareerDetail)
        career_id = self._generate_id(careers_details)

        # Create folder name: lowercase team name with underscore and career ID
        career_folder_name = f"{club_name.replace(' ', '_').lower()}_{career_id}"
        self.current_career = career_folder_name
        career_path = self.data_folder / career_folder_name
        career_path.mkdir(exist_ok=True)

        self.players_path = career_path / "players.json"
        self.matches_path = career_path / "matches.json"

        # Create a metadata file for the career
        metadata = CareerMetadata(
            career_id=career_id,
            club_name=club_name,
            folder_name=career_folder_name,
            manager_name=manager_name,
            created_at=datetime.now(),
            starting_season=starting_season,
            half_length=half_length,
            difficulty=difficulty,
        )
        self._save_json(career_path / "metadata.json", metadata)
        
        # Update the global careers details registry
        new_detail = CareerDetail(
            id=career_id,
            club_name=club_name,
            folder_name=career_folder_name
        )
        careers_details.append(new_detail)
        self._save_json(self.careers_details_path, careers_details)

        # Initialize empty players and matches files
        self._save_json(self.players_path)
        self._save_json(self.matches_path)
        self.players = []
        self.matches = []
    
    def get_all_career_names(self) -> list[str]:
        """Retrieve display names for all stored careers.

        Smart Deduplication:
        If multiple careers share the same club name, this method dynamically 
        loads the specific `metadata.json` for those careers to append the 
        Manager's name (e.g., 'Arsenal (Arteta)' vs 'Arsenal (User)').

        Returns:
            list[str]: A list of formatted strings for UI selection.
        """
        careers_details = self._load_json(self.careers_details_path, CareerDetail)

        # Identify any duplicate occurrences of club names
        name_counts = {}
        for career in careers_details:
            name_counts[career.club_name] = name_counts.get(career.club_name, 0) + 1

        display_names = []

        # Build list and resolve duplicates
        for career in careers_details:
            if name_counts[career.club_name] > 1:
                # If there are duplicates, include manager name in the display name for clarity
                meta_path = self.data_folder / career.folder_name / "metadata.json"
                if metadata := self._load_json(
                    meta_path, CareerMetadata, is_list=False
                ):
                    display_names.append(f"{career.club_name} ({metadata.manager_name})")
                else:
                    display_names.append(f"{career.club_name} ({career.id})")
            else:
                # If the name is unique, just use the club name
                display_names.append(career.club_name)
    
        return display_names
    
    def get_career_details(self, career_name: str) -> Optional[CareerMetadata]:
        """Retrieve the metadata for a specific career based on its display name.

        Matches the 'Smart Deduplication' logic used in `get_all_career_names`
        to identify the correct career folder, even if multiple careers exist
        for the same club.

        Args:
            career_name (str): The unique display string selected in the UI 
                                 (e.g., "Arsenal" or "Arsenal (Arteta)").

        Returns:
            Optional[CareerMetadata]: The full metadata object if found, else None.
        """
        careers_details = self._load_json(self.careers_details_path, CareerDetail)
        
        # Count occurrences of each club name to identify duplicates
        name_counts = {}
        for career in careers_details:
            name_counts[career.club_name] = name_counts.get(career.club_name, 0) + 1
        
        for career in careers_details:
            candidate_name = career.club_name
            
            if name_counts[candidate_name] > 1:
                # If it was a duplicate, we expect the input name to include the manager name in parentheses
                meta_path = self.data_folder / career.folder_name / "metadata.json"
                metadata = self._load_json(meta_path, CareerMetadata, is_list=False)
                
                if metadata:
                    candidate_name = f"{career.club_name} ({metadata.manager_name})"
                else:
                    candidate_name = f"{career.club_name} ({career.id})"
            
            if candidate_name == career_name:
                # Found match, return full metadata
                meta_path = self.data_folder / career.folder_name / "metadata.json"
                return self._load_json(meta_path, CareerMetadata, is_list=False)
        
        logger.warning(f"Career details not found for name: {career_name}")
        return None
    
    def load_career(self, career_name: str) -> None:
        """Load an existing career and prepare it for data operations.

        Updates the current career context and hydrates the player and 
        match lists from the filesystem into Pydantic models.

        Args:
            career_name (str): The unique display name of the career to load 
                               (as returned by get_all_career_names).
        """
        logger.info(f"Loading career context: {career_name}")
        
        career_metadata = self.get_career_details(career_name)
        if not career_metadata:
            logger.warning(f"Career '{career_name}' not found.")
            return
        
        # Set context
        career_folder_name = career_metadata.folder_name
        self.current_career = career_folder_name
        self.players_path = self.data_folder / career_folder_name / "players.json"
        self.matches_path = self.data_folder / career_folder_name / "matches.json"
        
        self.players = self._load_json(self.players_path, Player)
        self.matches = self._load_json(self.matches_path, Match)
        
        logger.info(
            f"Career '{career_name}' loaded successfully. "
            f"Players: {len(self.players)}, Matches: {len(self.matches)}"
        )

    def refresh_players(self) -> None:
        """Reload the players list from the current career's JSON file.

        Updates self.players with the latest data from disk. 
        Safe to call even if the file hasn't been written to yet (returns empty list).
        """
        if not self.players_path:
            logger.warning("Attempted to refresh players before loading a career.")
            return

        self.players = self._load_json(self.players_path, Player)

    def refresh_matches(self) -> None:
        """Reload the matches list from the current career's JSON file.

        Updates self.matches with the latest data from disk.
        """
        if not self.matches_path:
            logger.warning("Attempted to refresh matches before loading a career.")
            return

        self.matches = self._load_json(self.matches_path, Match)
    
    def add_or_update_player(
        self, 
        player_ui_data: dict, 
        position: PositionType, 
        season: str) -> None:
        """Add a new player or update an existing one based on their name.

        If the player name exists, appends the new attribute snapshot. 
        If not, creates a new Player record.

        Args:
            player_ui_data (dict): Dictionary containing player bio and attributes.
            position (PositionType): The position associated with this snapshot.
            season (str): The season identifier (e.g., "24/25").
        """
        # Check if player already exists based on name to update them
        player_name = player_ui_data.get("name")
        existing_player = self._find_player_by_name(player_name)
        
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
            logger.info(f"Updating player: {player_name}")
            existing_player.attribute_history.append(attributes_snapshot)
            # If age, height or weight are different, update it
            existing_player.age = int(player_ui_data.get("age"))
            existing_player.height = player_ui_data.get("height")
            existing_player.weight = int(player_ui_data.get("weight"))
            # If position is new, add it
            if position not in existing_player.positions:
                existing_player.positions.append(position)
        else:
            logger.info(f"Adding new player: {player_name}")
            new_id = self._generate_id(self.players)
            new_player = Player(
                id=new_id,
                name=player_name.strip(),
                nationality=player_ui_data.get("country").strip(),
                age=int(player_ui_data.get("age")),
                height=player_ui_data.get("height").strip(),
                weight=int(player_ui_data.get("weight")),
                positions=[position],
                attribute_history=[attributes_snapshot],
                financial_history=[],
                injury_history=[],
                sold=False,
                loaned=False
            )
            self.players.append(new_player)
        self._save_json(self.players_path, self.players)
        # Reload players to ensure consistency
        self.players = self._load_json(self.players_path, Player)
    
    def add_financial_data(
        self, 
        player_name: str, 
        financial_data: dict, 
        season: str) -> None:
        """Add a financial snapshot to a specific player's history.

        Cleans currency strings (removes commas) before validating against 
        the FinancialSnapshot model.

        Args:
            player_name (str): The name of the player to update.
            financial_data (dict): Dictionary containing keys like 'wage', 
                                   'market_value', 'release_clause'.
            season (str): The season identifier (e.g., "2024/2025").
        """
        existing_player = self._find_player_by_name(player_name)

        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot add financial data.")
            return

        logger.info(f"Saving financial snapshot for {player_name} (Season: {season})")

        # Clean Data (Remove commas from currency strings)
        # This ensures "120,000" becomes "120000" so Pydantic can parse it as int
        cleaned_data = {
            k: v.replace(",", "") if isinstance(v, str) else v
            for k, v in financial_data.items()
        }
        
        try:
            snapshot = FinancialSnapshot(
                datetime=datetime.now(),
                season=season,
                **cleaned_data
            )
            
            existing_player.financial_history.append(snapshot)
            
            self._save_json(self.players_path, self.players)
            self.players = self._load_json(self.players_path, Player)
            
        except ValidationError as e:
            logger.error(f"Validation failed for financial data: {e}")
    
    def add_injury_record(
        self, 
        player_name: str, 
        season: str, 
        injury_data: dict) -> None:
        """Add an injury record to a player's history.

        Validates the injury data (including date formatting) against the 
        InjuryRecord model before saving.

        Args:
            player_name (str): The name of the player to update.
            season (str): The season identifier.
            injury_data (dict): Dictionary containing 'in_game_date', 
                                'injury_detail', 'time_out', etc.
        """
        existing_player = self._find_player_by_name(player_name)
        
        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot add injury record.")
            return

        logger.info(f"Saving injury record for {player_name} (Season: {season})")
        
        try:
            snapshot = InjuryRecord(
                datetime=datetime.now(),
                season=season,
                **injury_data
            )
            
            existing_player.injury_history.append(snapshot)
            
            self._save_json(self.players_path, self.players)
            self.players = self._load_json(self.players_path, Player)
            
        except (ValidationError, ValueError) as e:
            logger.error(f"Failed to add injury record: {e}")
        
    def sell_player(self, player_name: str) -> None:
        """Mark a player as sold in the database.

        Args:
            player_name (str): The name of the player to sell.
        """
        logger.info(f"Action: Selling player {player_name}")
        self._update_player_status(player_name, "sold", True)
    
    def loan_out_player(self, player_name: str) -> None:
        """Mark a player as loaned out.

        Args:
            player_name (str): The name of the player to loan out.
        """
        logger.info(f"Action: Loaning out player {player_name}")
        self._update_player_status(player_name, "loaned", True)
    
    def return_loan_player(self, player_name: str) -> None:
        """Mark a player as returned from loan (active again).

        Args:
            player_name (str): The name of the player returning.
        """
        logger.info(f"Action: Returning player {player_name} from loan")
        self._update_player_status(player_name, "loaned", False)
        
    def _update_player_status(
        self, 
        player_name: str, 
        status_key: str, 
        status_value: bool):
        """Helper method to update a boolean status flag on a player.

        Args:
            player_name (str): The name of the player.
            status_key (str): The attribute name to update (e.g., 'sold', 'loaned').
            status_value (bool): The new boolean value.
        """
        existing_player = self._find_player_by_name(player_name)
        
        if not existing_player:
            logger.warning(
                f"Player '{player_name}' not found. "
                f"Cannot update status '{status_key}'."
            )
            return
        
        if not hasattr(existing_player, status_key):
            logger.error(
                f"Invalid status key '{status_key}' for Player model. Update aborted."
            )
            return
        
        setattr(existing_player, status_key, status_value)
        
        self._save_json(self.players_path, self.players)
        self.players = self._load_json(self.players_path, Player)
    
    def _generate_id(self, collection: list[Any]) -> int:
        """Generate a unique ID for a new item in a collection.

        Calculates the next integer ID based on the maximum existing ID.
        Assumes every item in the collection is an object with an '.id' attribute.

        Args:
            collection (list): A list of objects (e.g., Player models).

        Returns:
            int: The next available ID (starting at 1 if empty).
        """
        return max((item.id for item in collection), default=0) + 1
    
    def _find_player_by_name(self, name: str) -> Optional[Player]:
        """Find a player by their name (case-insensitive).

        Args:
            name (str): The player's name to search for.

        Returns:
            Optional[Player]: The player object if found, else None.
        """
        if not name:
            return None
        name_norm = name.strip().lower()
        return next(
            (
                player
                for player in self.players
                if player.name.strip().lower() == name_norm
            ),
            None,
        )
    
    def _find_player_id_by_name(self, name: str) -> int | None:
        """Find the unique ID of a player by their name (case-insensitive).

        Args:
            name (str): The player's name to search for.

        Returns:
            Optional[int]: The player's ID if found, else None.
        """
        player = self._find_player_by_name(name)
        return player.id if player else None
    
    def add_match(self, match_data: dict, player_performances: list[dict]):
        """Add a complete match record to the database.

        Links individual player performances to existing Player IDs.
        Handles polymorphic creation of Goalkeeper vs Outfield performance objects.

        Args:
            match_data (dict): General match info (score, opponent, competition, etc.).
            player_performances (list[dict]): List of raw performance dictionaries 
                                              from the UI.
        """
        match_id = self._generate_id(self.matches)
        timestamp = datetime.now()
        
        logger.info(
            f"Adding match {match_id} vs {match_data.get('away_team_name', 'Unknown')} "
            f"with {len(player_performances)} player performances."
        )
        
        normalized_performances = []
        for perf in player_performances:
            p_name = perf.get("player_name", "")
            p_id = self._find_player_id_by_name(p_name)
            
            if not p_id:
                logger.warning(
                    f"Skipping stats for '{p_name}' in match {match_id}: "
                    f"Player not found in database."
                )
                continue
            
            # Remove name, add ID
            perf_data = {k: v for k, v in perf.items() if k != "player_name"}
            perf_data["player_id"] = p_id
            
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
        self.matches = self._load_json(self.matches_path, Match)