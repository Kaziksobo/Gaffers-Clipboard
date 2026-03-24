from pathlib import Path
import json
import logging
from typing import List, Optional, Union, Type, TypeVar, Any
from pydantic import ValidationError, TypeAdapter, BaseModel
from datetime import datetime

from src.custom_types import (
    GKAttributeSnapshot,
    OutfieldAttributeSnapshot,
    FinancialSnapshot,
    InjuryRecord,
    Player,
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
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading JSON from {path}: {e}", exc_info=True)
            return default

        adapter = TypeAdapter(List[model_class] if is_list else model_class)

        try:
            return adapter.validate_python(raw_data)
        except ValidationError:
            if not is_list:
                logger.error(f"Validation failed for {path}, returning default.")
                return default
            if not isinstance(raw_data, list):
                logger.error(f"Expected list in {path} but got {type(raw_data).__name__}. Returning default.")
                return default
            # Partial recovery: validate each item individually
            logger.warning(f"Full list validation failed for {path}. Attempting partial recovery.")
            item_adapter = TypeAdapter(model_class)
            recovered = []
            skipped = 0
            for i, item in enumerate(raw_data):
                try:
                    recovered.append(item_adapter.validate_python(item))
                except ValidationError:
                    skipped += 1
                    logger.debug(f"Skipped invalid item at index {i} in {path}.")
            logger.warning(f"Partial recovery: {len(recovered)} valid, {skipped} skipped from {path}.")
            return recovered
    
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

    def _load_matches_strict_or_raise(self) -> list[Match]:
        """Strictly load matches.json and raise on any ambiguity.

        This is intentionally fail-closed to protect against destructive overwrites.
        """
        if not self.matches_path:
            raise RuntimeError("Cannot load matches: no active career/matches path is set.")

        if not self.matches_path.exists():
            return []

        try:
            with open(self.matches_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(
                f"Refusing to save: unable to read matches.json at {self.matches_path}: {e}"
            ) from e

        if not isinstance(raw_data, list):
            raise ValueError(
                f"Refusing to save: matches.json must contain a list, got {type(raw_data).__name__}."
            )

        try:
            adapter = TypeAdapter(List[Match])
            return adapter.validate_python(raw_data)
        except ValidationError as e:
            raise ValueError(
                f"Refusing to save: matches.json failed strict validation with {len(e.errors())} errors."
            ) from e

    def _load_players_strict_or_raise(self) -> list[Player]:
        """Strictly load players.json and raise on any ambiguity.

        This is intentionally fail-closed to protect against destructive overwrites.
        """
        if not self.players_path:
            raise RuntimeError("Cannot load players: no active career/players path is set.")

        if not self.players_path.exists():
            return []

        try:
            with open(self.players_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(
                f"Refusing to save: unable to read players.json at {self.players_path}: {e}"
            ) from e

        if not isinstance(raw_data, list):
            raise ValueError(
                f"Refusing to save: players.json must contain a list, got {type(raw_data).__name__}."
            )

        try:
            adapter = TypeAdapter(List[Player])
            return adapter.validate_python(raw_data)
        except ValidationError as e:
            raise ValueError(
                f"Refusing to save: players.json failed strict validation with {len(e.errors())} errors."
            ) from e

    def _save_json_atomic_or_raise(self, path: Path, data: Union[T, List[T], None] = None) -> None:
        """Atomically save JSON and raise on failure instead of swallowing errors."""
        if data is None:
            data = []

        if isinstance(data, list):
            export_data = [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in data
            ]
        elif isinstance(data, BaseModel):
            export_data = data.model_dump(mode="json")
        else:
            export_data = data

        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=4)
        tmp_path.replace(path)
    
    def create_new_career(
        self, 
        club_name: str, 
        manager_name: str, 
        starting_season: str, 
        half_length: int, 
        difficulty: DifficultyLevel,
        league: str) -> None:
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

        # Seed competitions for this league from the bundled config (if available)
        competitions: list[str] = []
        # Normalize league provided to title case for consistent lookup
        league_title = league.title() if isinstance(league, str) else league
        try:
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "league_competitions.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    defaults = json.load(f)
                    # Support both {"league": [...]} and {"leagues": { ... }} formats
                    if isinstance(defaults, dict) and "leagues" in defaults and isinstance(defaults["leagues"], dict):
                        defaults = defaults["leagues"]
                    if isinstance(defaults, dict) and league_title in defaults:
                        competitions = defaults.get(league_title) or []
        except Exception as e:
            logger.debug(f"Failed to load league defaults from config: {e}")

        # Create a metadata file for the career
        # Normalize competitions to title case as well
        competitions = [c.title() for c in competitions]

        metadata = CareerMetadata(
            career_id=career_id,
            club_name=club_name,
            folder_name=career_folder_name,
            manager_name=manager_name,
            created_at=datetime.now(),
            starting_season=starting_season,
            half_length=half_length,
            difficulty=difficulty,
            league=league_title,
            competitions=competitions,
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

    def get_latest_match_in_game_date(self) -> Optional[datetime]:
        """Return the most recent match's in-game date for the current career.

        The method refreshes the in-memory matches from disk and then returns
        the maximum `data.in_game_date` value across all stored matches.
        Returns None when no matches are present or when no career is loaded.
        """
        if not self.matches_path:
            logger.debug("No matches_path set; cannot determine latest match date.")
            return None

        # Ensure we have the latest view of matches on disk
        self.refresh_matches()

        if not self.matches:
            return None

        try:
            latest = max(self.matches, key=lambda m: m.data.in_game_date)
            return latest.data.in_game_date
        except Exception as e:
            logger.warning(f"Failed to compute latest match date: {e}")
            return None
    
    def add_or_update_player(
        self, 
        player_ui_data: dict, 
        position: Optional[PositionType], 
        in_game_date: str,
        is_gk: bool = False) -> None:
        """Add a new player or update an existing one based on their name.

        If the player name exists, appends the new attribute snapshot. 
        If not, creates a new Player record.

        Args:
            player_ui_data (dict): Dictionary containing player bio and attributes.
            position (PositionType): The position associated with this snapshot.
        """
        # Fail closed: if on-disk players cannot be fully validated, abort before any write.
        self.players = self._load_players_strict_or_raise()

        # Check if player already exists based on name to update them
        player_name = player_ui_data.get("name")
        existing_player = self._find_player_by_name(player_name)
        
        top_level_keys = ["name", "age", "height", "weight", "country", "in_game_date"]
        
        attributes = {k: v for k, v in player_ui_data.items() if k not in top_level_keys}
        if is_gk:
            attributes_snapshot = GKAttributeSnapshot(
                datetime=datetime.now(),
                in_game_date=in_game_date,
                position_type="GK",
                **attributes
            )
        else:
            attributes_snapshot = OutfieldAttributeSnapshot(
                datetime=datetime.now(),
                in_game_date=in_game_date,
                position_type="Outfield",
                **attributes
            )
        
        
        if existing_player:
            logger.info(f"Updating player: {player_name}")
            existing_player.attribute_history.append(attributes_snapshot)
            # Only update base attributes if new values are provided
            if player_ui_data.get("age") is not None:
                existing_player.age = int(player_ui_data.get("age"))
            if player_ui_data.get("height") is not None:
                existing_player.height = player_ui_data.get("height")
            if player_ui_data.get("weight") is not None:
                existing_player.weight = int(player_ui_data.get("weight"))
            if player_ui_data.get("country") is not None:
                existing_player.nationality = player_ui_data.get("country").strip()
            # If position is new, add it
            if position is not None and position not in existing_player.positions:
                existing_player.positions.append(position)
        else:
            if not all([
                player_name,
                player_ui_data.get("country"),
                player_ui_data.get("age"),
                player_ui_data.get("height"),
                player_ui_data.get("weight"),
                position
            ]):
                raise ValueError("New players require name, country, age, height, weight, and position.")
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
                date_sold=None,
                loaned=False
            )
            self.players.append(new_player)
        self._save_json_atomic_or_raise(self.players_path, self.players)
        # Reload players strictly to ensure consistency
        self.players = self._load_players_strict_or_raise()
    
    def add_financial_data(
        self, 
        player_name: str, 
        financial_data: dict, 
        in_game_date: str) -> None:
        """Add a financial snapshot to a specific player's history.

        Cleans currency strings (removes commas) before validating against 
        the FinancialSnapshot model.

        Args:
            player_name (str): The name of the player to update.
            financial_data (dict): Dictionary containing keys like 'wage', 
                                   'market_value', 'release_clause'.
            in_game_date (str): The in-game date for the financial snapshot (e.g., "24/11/24").
        """
        self.players = self._load_players_strict_or_raise()
        existing_player = self._find_player_by_name(player_name)

        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot add financial data.")
            return

        logger.info(f"Saving financial snapshot for {player_name}")

        # Clean Data (Remove commas from currency strings)
        # This ensures "120,000" becomes "120000" so Pydantic can parse it as int
        cleaned_data = {
            k: v.replace(",", "") if isinstance(v, str) else v
            for k, v in financial_data.items()
        }
        
        try:
            snapshot = FinancialSnapshot(
                datetime=datetime.now(),
                in_game_date=in_game_date,
                **cleaned_data
            )
            
            existing_player.financial_history.append(snapshot)
            
            self._save_json_atomic_or_raise(self.players_path, self.players)
            self.players = self._load_players_strict_or_raise()
            
        except ValidationError as e:
            logger.error(f"Validation failed for financial data: {e}")
    
    def add_injury_record(
        self, 
        player_name: str, 
        injury_data: dict) -> None:
        """Add an injury record to a player's history.

        Validates the injury data (including date formatting) against the 
        InjuryRecord model before saving.

        Args:
            player_name (str): The name of the player to update.
            injury_data (dict): Dictionary containing 'in_game_date', 
                                'injury_detail', 'time_out', etc.
        """
        self.players = self._load_players_strict_or_raise()
        existing_player = self._find_player_by_name(player_name)
        
        if not existing_player:
            logger.warning(f"Player '{player_name}' not found. Cannot add injury record.")
            return

        logger.info(f"Saving injury record for {player_name}")
        
        try:
            snapshot = InjuryRecord(
                datetime=datetime.now(),
                **injury_data
            )
            
            existing_player.injury_history.append(snapshot)
            
            self._save_json_atomic_or_raise(self.players_path, self.players)
            self.players = self._load_players_strict_or_raise()
            
        except (ValidationError, ValueError) as e:
            logger.error(f"Failed to add injury record: {e}")
        
    def sell_player(self, player_name: str, in_game_date: str) -> None:
        """Mark a player as sold in the database.

        Args:
            player_name (str): The name of the player to sell.
            in_game_date (str): The in-game date when the player was sold.
        """
        logger.info(f"Action: Selling player {player_name}")
        self._update_player_status(player_name, status_key="sold", status_value=True, in_game_date=in_game_date)
    
    def loan_out_player(self, player_name: str) -> None:
        """Mark a player as loaned out.

        Args:
            player_name (str): The name of the player to loan out.
        """
        logger.info(f"Action: Loaning out player {player_name}")
        self._update_player_status(player_name, status_key="loaned", status_value=True)
    
    def return_loan_player(self, player_name: str) -> None:
        """Mark a player as returned from loan (active again).

        Args:
            player_name (str): The name of the player returning.
        """
        logger.info(f"Action: Returning player {player_name} from loan")
        self._update_player_status(player_name, status_key="loaned", status_value=False)
        
    def _update_player_status(
        self, 
        player_name: str, 
        status_key: str, 
        status_value: bool,
        in_game_date: Optional[str] = None) -> None:
        """Helper method to update a boolean status flag on a player.

        Args:
            player_name (str): The name of the player.
            status_key (str): The attribute name to update (e.g., 'sold', 'loaned').
            status_value (bool): The new boolean value.
            in_game_date (Optional[str]): The in-game date for the status change, only needed for 'sold' status to set the date_sold field.
        """
        self.players = self._load_players_strict_or_raise()
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

        if status_key == "sold" and status_value:
            if not in_game_date:
                logger.error("In-game date is required when marking a player as sold.")
                return
            existing_player.date_sold = in_game_date

        setattr(existing_player, status_key, status_value)

        self._save_json_atomic_or_raise(self.players_path, self.players)
        self.players = self._load_players_strict_or_raise()
    
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

    def add_competition(self, competition: str) -> None:
        """Add a competition to the current career's metadata (idempotent).

        The competition name will be title-cased. Raises RuntimeError if no
        career is loaded.
        """
        if not self.current_career:
            raise RuntimeError("No career loaded")

        meta_path = self.data_folder / self.current_career / "metadata.json"
        metadata = self._load_json(meta_path, CareerMetadata, is_list=False)
        if metadata is None:
            raise RuntimeError("Career metadata missing")

        comp_title = competition.strip().title()
        if comp_title in (metadata.competitions or []):
            return

        metadata.competitions.append(comp_title)
        self._save_json(meta_path, metadata)

    def remove_competition(self, competition: str) -> None:
        """Remove a competition from the current career, blocking if referenced by any match.

        Raises ValueError if any saved match references the competition.
        """
        if not self.current_career:
            raise RuntimeError("No career loaded")

        # Ensure we have latest matches
        self.refresh_matches()
        # Check references
        for m in self.matches:
            try:
                if m.data.competition == competition:
                    raise ValueError(f"Competition '{competition}' is referenced by existing matches and cannot be removed.")
            except Exception:
                # If match structure unexpected, continue conservative path
                continue

        meta_path = self.data_folder / self.current_career / "metadata.json"
        metadata = self._load_json(meta_path, CareerMetadata, is_list=False)
        if metadata is None:
            raise RuntimeError("Career metadata missing")

        comps = [c for c in (metadata.competitions or []) if c != competition]
        metadata.competitions = comps
        self._save_json(meta_path, metadata)

    def update_career_metadata(self, updates: dict) -> None:
        """Update the current career's metadata with the provided fields.

        Loads the existing metadata, applies the updates, validates via the
        CareerMetadata model, and persists the result atomically.
        """
        if not self.current_career:
            raise RuntimeError("No career loaded")

        meta_path = self.data_folder / self.current_career / "metadata.json"
        metadata = self._load_json(meta_path, CareerMetadata, is_list=False)
        if metadata is None:
            raise RuntimeError("Career metadata missing")

        # Merge and validate by constructing a new CareerMetadata
        base = metadata.model_dump()
        base.update(updates)

        try:
            new_meta = CareerMetadata(**base)
        except ValidationError as e:
            logger.error(f"Metadata validation failed: {e}")
            raise

        # Save atomically
        self._save_json(meta_path, new_meta)
    
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
        # Fail closed: if on-disk matches cannot be fully validated, abort before any write.
        self.matches = self._load_matches_strict_or_raise()
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
        self._save_json_atomic_or_raise(self.matches_path, self.matches)
        self.matches = self._load_matches_strict_or_raise()