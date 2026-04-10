"""Filesystem-backed persistence layer for career, player, and match data.

This module defines DataManager, the central gateway between application
services and JSON storage on disk. It coordinates career setup, data loading,
validation, and persistence workflows across players, matches, and metadata.

Primary responsibilities:
- Create and initialize career folders and seed default files.
- Load, cache, and refresh players/matches for the active career.
- Normalize and validate UI payloads into Pydantic schema models.
- Use atomic writes for strict player/match mutation workflows.
- Persist bootstrap and metadata updates through standard JSON writes.

Storage layout:
- data/careers_details.json:
    Global registry of known careers and folder names.
- data/<career_folder>/metadata.json:
    Career configuration, manager identity, and competitions.
- data/<career_folder>/players.json:
    Player profiles plus attribute, injury, and financial histories.
- data/<career_folder>/matches.json:
    Match records and linked player performance snapshots.

Validation and safety model:
- Tolerant loaders return safe fallbacks for non-destructive read flows.
- Strict loaders guard player/match mutation paths and raise on malformed data.
- Conversion and schema enforcement are delegated to Pydantic models.
- Atomic writes use temporary files plus replace semantics where fail-closed
    mutation guarantees are required.
- Standard writes remain in use for selected bootstrap/metadata operations.

Together, these rules keep persistence behavior deterministic, auditable, and
resilient across UI workflows and service-layer operations.
"""

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

from src.contracts.backend import (
    CareerCreationArtifacts,
    CareerMetadataUpdate,
    FinancialDataPayload,
    InjuryDataPayload,
    JsonValue,
    MatchOverviewPayload,
    PlayerAttributePayload,
    PlayerCoreFields,
    PlayerPerformanceBuffer,
)
from src.schemas import (
    CareerDetail,
    CareerMetadata,
    DifficultyLevel,
    FinancialSnapshot,
    GKAttributeSnapshot,
    InjuryRecord,
    Match,
    OutfieldAttributeSnapshot,
    Player,
    PositionType,
)
from src.services import data as data_services

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class SupportsId(Protocol):
    """Protocol for model instances carrying an integer id field."""

    id: int


class DataManager:
    """Manage persistent storage for careers, players, matches, and metadata.

    This class provides high-level operations for creating, loading, and updating
    career-related data on disk using JSON files and Pydantic models.
    """

    # --- Lifecycle and Environment ---

    def __init__(self, project_root: Path) -> None:
        """Initialize a new DataManager instance with the project root.

        Derives the data folder from the project root and prepares internal
        paths and caches used to manage careers, players, and matches in JSON
        form.

        Args:
            project_root (Path): Root directory of the project.

        Raises:
            OSError: If the root data directory cannot be created.
        """
        self.project_root: Path = project_root
        self.data_folder: Path = self.project_root / "data"
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self._career_service = data_services.CareerService()
        self._match_service = data_services.MatchService()
        self._player_service = data_services.PlayerService()
        self._json_service = data_services.JsonService()

        self.current_career: str | None = None
        self.careers_details_path: Path = self.data_folder / "careers_details.json"

        # Paths are initialized as None; they are set when a career is selected
        self.players_path: Path | None = None
        self.matches_path: Path | None = None

        # In-memory data caches, initially empty
        self.players: list[Player] = []
        self.matches: list[Match] = []

    # --- Career Selection and Metadata Workflow ---

    def create_new_career(
        self,
        club_name: str,
        manager_name: str,
        starting_season: str,
        half_length: int,
        difficulty: DifficultyLevel,
        league: str,
    ) -> None:
        """Execute the disk provisioning and state initialization for a new career.

        Creates a dedicated subdirectory within the root data folder and writes
        the foundational JSON structures (`metadata.json`, `players.json`,
        `matches.json`). Appends the new career record to the global
        `careers_details.json` registry.

        Delegates payload mapping and artifact generation to `CareerDataService`,
        and strictly enforces that disk I/O occurs *before* internal pointer state
        (`self.current_career`, paths, cached lists) is mutated.

        Args:
            club_name (str): The chosen club name for directory generation.
            manager_name (str): The chosen manager name.
            starting_season (str): The season string (e.g., "24/25").
            half_length (int): Match half duration in minutes.
            difficulty (DifficultyLevel): Validated difficulty enum.
            league (str): League string used by the service to map default competitions.

        Raises:
            OSError: If permission is denied or the directory
                     structure cannot be created.
            ValidationError: If generated career metadata fails schema validation.
        """
        logger.info("Creating new career: %s (Manager: %s)", club_name, manager_name)

        # Generate ID first to use in folder name
        careers_details: list[CareerDetail] = self._json_service.load_json(
            self.careers_details_path, CareerDetail
        )
        career_id: int = self._generate_id(careers_details)

        artifacts: CareerCreationArtifacts = self._career_service.prepare_new_career(
            data_folder=self.data_folder,
            project_root=self.project_root,
            club_name=club_name,
            manager_name=manager_name,
            starting_season=starting_season,
            half_length=half_length,
            difficulty=difficulty,
            league=league,
            career_id=career_id,
            created_at=datetime.now(),
        )

        # Persist planned artifacts first; only then mutate manager state.
        artifacts.career_path.mkdir(exist_ok=True)
        self._json_service.save_json(
            artifacts.career_path / "metadata.json", artifacts.metadata
        )

        careers_details.append(artifacts.new_detail)
        self._json_service.save_json(self.careers_details_path, careers_details)

        # Initialize empty players and matches files
        self._json_service.save_json(artifacts.players_path)
        self._json_service.save_json(artifacts.matches_path)

        self.current_career: str = artifacts.career_folder_name
        self.players_path: Path = artifacts.players_path
        self.matches_path: Path = artifacts.matches_path
        self.players: list[Player] = []
        self.matches: list[Match] = []

    def get_all_career_names(self) -> list[str]:
        """Retrieve and format all career display names from the central registry.

        Reads the global `careers_details.json` to get the base list of generated
        careers. Delegates collision detection to the `CareerDataService` and performs
        targeted disk reads of specific `metadata.json` files for any directories
        that share a club name. Finally, delegates the string formatting logic back
        to the service to guarantee uniqueness.

        Returns:
            list[str]: A list of unique, formatted career display strings.
        """
        careers_details: list[CareerDetail] = self._json_service.load_json(
            self.careers_details_path, CareerDetail
        )

        duplicate_club_names: set[str] = self._career_service.get_duplicate_club_names(
            careers_details
        )

        # Loading stays in DataManager.
        metadata_by_folder: dict[str, CareerMetadata | None] = (
            self._load_duplicate_career_metadata(
                careers_details,
                duplicate_club_names,
            )
        )

        return self._career_service.build_display_names(
            careers_details=careers_details,
            duplicate_club_names=duplicate_club_names,
            metadata_by_folder=metadata_by_folder,
        )

    def get_career_details(self, career_name: str) -> CareerMetadata | None:
        """Load the metadata model for a specific career using its display string.

        Reads `careers_details.json` and performs selective `metadata.json` disk reads
        to map the provided display string back to its specific physical directory.
        Delegates this resolution logic to the `CareerDataService`. Once the target
        folder is identified, reads and validates the final `metadata.json` file.

        Args:
            career_name (str): The unique formatted string
                               representing the target career.

        Returns:
            CareerMetadata | None: The parsed Pydantic metadata model, or None if the
                mapping fails or the underlying file is missing.
        """
        careers_details: list[CareerDetail] = self._json_service.load_json(
            self.careers_details_path, CareerDetail
        )

        duplicate_club_names: set[str] = self._career_service.get_duplicate_club_names(
            careers_details
        )

        # Loading stays in DataManager.
        metadata_by_folder: dict[str, CareerMetadata | None] = (
            self._load_duplicate_career_metadata(
                careers_details,
                duplicate_club_names,
            )
        )

        selected_career: CareerDetail | None = (
            self._career_service.find_career_by_display_name(
                careers_details=careers_details,
                duplicate_club_names=duplicate_club_names,
                metadata_by_folder=metadata_by_folder,
                selected_name=career_name,
            )
        )
        if selected_career is None:
            logger.warning("Career details not found for name: %s", career_name)
            return None

        if selected_career.club_name in duplicate_club_names:
            # Reuse preloaded metadata for duplicate-name careers.
            metadata: CareerMetadata | None = metadata_by_folder.get(
                selected_career.folder_name
            )
            if metadata is not None:
                return metadata

        # Found match, return full metadata loaded by DataManager.
        meta_path: Path = (
            self.data_folder / selected_career.folder_name / "metadata.json"
        )
        return self._json_service.load_json(meta_path, CareerMetadata, is_list=False)

    def load_career(self, career_name: str) -> bool:
        """Update internal instance state to target a specific career directory.

        Resolves the provided display string to a physical directory structure
        using `get_career_details`. Upon success, it rebinds the internal path
        pointers (`self.current_career`, `self.players_path`, `self.matches_path`)
        and populates the in-memory `Player` and `Match` caches by delegating
        bulk file reads to the `JsonService`.

        Args:
            career_name (str): The unique formatted string
                               representing the target career.

        Returns:
            bool: True if the directory was resolved and internal state was successfully
                  mutated. False if the directory mapping failed.
        """
        logger.info("Loading career context: %s", career_name)

        career_metadata: CareerMetadata | None = self.get_career_details(career_name)
        if not career_metadata:
            logger.warning("Career '%s' not found.", career_name)
            return False

        # Set context
        career_folder_name: str = career_metadata.folder_name
        self.current_career: str = career_folder_name
        self.players_path: Path = self.data_folder / career_folder_name / "players.json"
        self.matches_path: Path = self.data_folder / career_folder_name / "matches.json"

        self.players: list[Player] = self._json_service.load_json(
            self.players_path, Player
        )
        self.matches: list[Match] = self._json_service.load_json(
            self.matches_path, Match
        )

        logger.info(
            "Career '%s' loaded successfully. Players: %s, Matches: %s",
            career_name,
            len(self.players),
            len(self.matches),
        )
        return True

    def get_current_career_metadata(self) -> CareerMetadata | None:
        """Read and parse the metadata.json file for the currently active directory.

        Relies on the internal `self.current_career` pointer to construct the
        absolute file path. Delegates the raw disk I/O and strict Pydantic model
        mapping to `JsonService.load_json`.

        Returns:
            CareerMetadata | None: The parsed Pydantic model. Returns None if the
                                   internal state pointer is unset, or if the underlying
                                   JSON file is missing or corrupted on disk.
        """
        if not self.current_career:
            return None

        meta_path: Path = self.data_folder / self.current_career / "metadata.json"
        metadata: CareerMetadata | None = self._json_service.load_json(
            meta_path, CareerMetadata, is_list=False
        )
        if metadata is None:
            logger.warning(
                "Active career metadata missing or invalid for folder: %s",
                self.current_career,
            )
        return metadata

    def add_competition(self, competition: str) -> None:
        """Execute a disk write to append a competition to the active metadata.json.

        Enforces that a career context is active, then reads the current `metadata.json`
        file. Delegates the actual array manipulation and deduplication logic to
        `CareerDataService`. Writes the updated metadata model back to disk if changes
        were applied by the service.

        Args:
            competition (str): The raw competition string to append.

        Raises:
            RuntimeError: If called without an initialized career context, or if the
                          target `metadata.json` file is missing/corrupted.
        """
        if not self.current_career:
            raise RuntimeError("No career loaded")

        meta_path: Path = self.data_folder / self.current_career / "metadata.json"
        metadata: CareerMetadata | None = self._json_service.load_json(
            meta_path, CareerMetadata, is_list=False
        )
        if metadata is None:
            raise RuntimeError("Career metadata missing")

        if self._career_service.add_competition_to_metadata(
            metadata=metadata,
            competition=competition,
        ):
            self._json_service.save_json(meta_path, metadata)

    def remove_competition(self, competition: str) -> None:
        """Execute a disk write to remove a competition from the active metadata.json.

        Forces a cache synchronization via `refresh_matches` to ensure the disk state
        is accurate. Delegates referential integrity checks (ensuring no saved matches
        actively use the competition) and array mutation to `CareerDataService`. Upon
        successful validation, reads and updates the target
        `metadata.json` file on disk.

        Args:
            competition (str): The exact competition string to remove.

        Raises:
            RuntimeError: If called without an initialized career context, or if the
                          target `metadata.json` file is missing/corrupted.
            ValueError: If `CareerDataService` detects that the competition is actively
                        referenced by a saved match, aborting the disk write.
        """
        if not self.current_career:
            raise RuntimeError("No career loaded")

        # Ensure we have latest matches
        self.refresh_matches()
        self._career_service.ensure_competition_not_referenced(
            matches=self.matches,
            competition=competition,
        )

        meta_path: Path = self.data_folder / self.current_career / "metadata.json"
        metadata: CareerMetadata | None = self._json_service.load_json(
            meta_path, CareerMetadata, is_list=False
        )
        if metadata is None:
            raise RuntimeError("Career metadata missing")

        self._career_service.remove_competition_from_metadata(
            metadata=metadata,
            competition=competition,
        )
        self._json_service.save_json(meta_path, metadata)

    def update_career_metadata(self, updates: CareerMetadataUpdate) -> None:
        """Run a targeted disk write to modify fields within the active metadata.json.

        Validates the presence of an active career context and reads the current
        metadata from disk. Delegates the Pydantic field merging and validation to
        `CareerDataService`. Persists the resulting merged model back to the target
        `metadata.json` file.

        Args:
            updates (CareerMetadataUpdate): A validated partial Pydantic model
                                            containing the explicit fields to modify.

        Raises:
            RuntimeError: If called without an initialized career context, or if the
                          target `metadata.json` file is missing/corrupted.
            ValidationError: If the newly merged data fails strict Pydantic
                             schema validation.
        """
        if not self.current_career:
            raise RuntimeError("No career loaded")

        meta_path: Path = self.data_folder / self.current_career / "metadata.json"
        metadata: CareerMetadata | None = self._json_service.load_json(
            meta_path, CareerMetadata, is_list=False
        )
        if metadata is None:
            raise RuntimeError("Career metadata missing")

        new_meta: CareerMetadata = self._career_service.build_updated_metadata(
            metadata=metadata,
            updates=updates,
        )

        # Save atomically
        self._json_service.save_json(meta_path, new_meta)

    # --- Cache Sync and Read Helpers ---

    def refresh_players(self) -> None:
        """Read players.json from disk to synchronize the internal instance cache.

        Relies on the internal `self.players_path` pointer. Delegates raw disk I/O
        and Pydantic model mapping to `JsonService.load_json`. Rebinds the
        `self.players` attribute with the newly parsed list of models.
        """
        if not self.players_path:
            logger.warning("Attempted to refresh players before loading a career.")
            return

        self.players: list[Player] = self._json_service.load_json(
            self.players_path, Player
        )

    def refresh_matches(self) -> None:
        """Read matches.json from disk to synchronize the internal instance cache.

        Relies on the internal `self.matches_path` pointer. Delegates raw disk I/O
        and Pydantic model mapping to `JsonService.load_json`. Rebinds the
        `self.matches` attribute with the newly parsed list of models.
        """
        if not self.matches_path:
            logger.warning("Attempted to refresh matches before loading a career.")
            return

        self.matches: list[Match] = self._json_service.load_json(
            self.matches_path, Match
        )

    def get_latest_match_in_game_date(self) -> datetime | None:
        """Trigger a disk sync of matches.json and extract the most recent match date.

        Forces an internal state mutation via `refresh_matches` to guarantee the
        cache perfectly reflects the current disk state. Once synchronized, delegates
        the chronological sorting and parsing logic to
        `MatchDataService.get_latest_in_game_date`.

        Returns:
            datetime | None: The parsed maximum date from the cached match models.
                             Returns None if the career context is unset or if the
                             synchronized JSON file contains no match records.
        """
        if not self.matches_path:
            logger.debug("No matches_path set; cannot determine latest match date.")
            return None

        # Ensure we have the latest view of matches on disk
        self.refresh_matches()
        return self._match_service.get_latest_in_game_date(self.matches)

    def find_player_by_name(self, name: str) -> Player | None:
        """Query the synchronized internal instance cache to resolve a player record.

        Acts as a fast in-memory read operation rather than a direct disk access. Relies
        on the `self.players` array being accurately synchronized via prior
        `refresh_players` or mutation calls. Delegates the string matching
        logic to `PlayerDataService`.

        Args:
            name (str): The string identifier to search for within the active cache.

        Returns:
            Player | None: The Pydantic model reference from memory, or None if
                           no match exists in the current career context.
        """
        return self._player_service.find_player_by_name(self.players, name)

    # --- Player Mutation Workflow ---

    def add_or_update_player(
        self,
        player_ui_data: PlayerAttributePayload,
        position: PositionType | None,
        in_game_date: str,
        is_gk: bool = False,
    ) -> None:
        """Execute an atomic upsert of a player record to the active players.json file.

        Enforces a strict fail-closed state validation before and after mutation.
        Delegates the Pydantic model construction—either appending a new temporal
        snapshot to an existing player or initializing a new player record—to the
        `PlayerDataService`.

        Writes the mutated list back to disk using a safe atomic operation to prevent
        file corruption, then immediately forces an internal cache re-sync to guarantee
        perfect alignment between disk and memory.

        Args:
            player_ui_data (PlayerAttributePayload): Validated dictionary payload
                                                     containing the raw biographical
                                                     and statistical data.
            position (PositionType | None): The specific position enum
                                            for this snapshot.
            in_game_date (str): The EA FC chronological date of the snapshot.
            is_gk (bool, optional): Boolean flag dictating which Pydantic snapshot
                                    subclass (Outfield vs. Goalkeeper) should be
                                    constructed. Defaults to False.

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If the current disk state or the resulting mutation fails strict
                        schema validation.
            OSError: If the atomic file replacement fails due to filesystem permissions.
            ValidationError: If new player model construction fails validation.
        """
        # Fail closed: abort if on-disk players cannot be fully validated.
        players_path: Path = self._require_players_path()
        self.players: list[Player] = self._load_players_strict_or_raise()

        core_fields: PlayerCoreFields = self._player_service.extract_player_core_fields(
            player_ui_data
        )
        existing_player: Player | None = self.find_player_by_name(core_fields.name)
        attributes_snapshot: GKAttributeSnapshot | OutfieldAttributeSnapshot = (
            self._player_service.build_attribute_snapshot(
                player_ui_data=player_ui_data,
                is_gk=is_gk,
                in_game_date=in_game_date,
                position=position,
                player_name=core_fields.name,
            )
        )

        if existing_player:
            self._player_service.update_existing_player(
                existing_player=existing_player,
                attributes_snapshot=attributes_snapshot,
                core_fields=core_fields,
                position=position,
            )
        else:
            new_id: int = self._generate_id(self.players)
            self.players.append(
                self._player_service.create_new_player(
                    player_id=new_id,
                    core_fields=core_fields,
                    position=position,
                    attributes_snapshot=attributes_snapshot,
                )
            )

        self._json_service.save_json_atomic_or_raise(players_path, self.players)
        # Reload players strictly to ensure consistency
        self.players: list[Player] = self._load_players_strict_or_raise()

    def add_financial_data(
        self, player_name: str, financial_data: FinancialDataPayload, in_game_date: str
    ) -> None:
        """Execute an atomic append of a financial snapshot to a player's record.

        Enforces strict fail-closed state validation before mutation. Validates the
        existence of the target player in the active registry and delegates Pydantic
        snapshot construction to `PlayerDataService`. Appends the resulting model to
        the player's internal financial history array.

        Writes the mutated list to the active `players.json` file using a safe atomic
        operation, then immediately forces an internal cache re-sync to guarantee
        alignment between disk and memory.

        Args:
            player_name (str): The exact registered name of the target player.
            financial_data (FinancialDataPayload): Validated dictionary payload
                                                   containing raw wage, value,
                                                   and contract details.
            in_game_date (str): The in-game chronological date of the snapshot.

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If the target player is not found, or if the snapshot data
                        fails strict Pydantic schema validation.
            OSError: If the atomic file replacement fails due to filesystem permissions.
        """
        players_path: Path = self._require_players_path()
        self.players: list[Player] = self._load_players_strict_or_raise()
        existing_player: Player = self._player_service.require_existing_player(
            players=self.players,
            player_name=player_name,
            action_description="add financial data",
        )

        logger.info("Saving financial snapshot for %s", player_name)
        snapshot: FinancialSnapshot = self._player_service.create_financial_snapshot(
            player_name=player_name,
            financial_data=financial_data,
            in_game_date=in_game_date,
        )
        existing_player.financial_history.append(snapshot)

        self._json_service.save_json_atomic_or_raise(players_path, self.players)
        self.players: list[Player] = self._load_players_strict_or_raise()

    def add_injury_record(
        self, player_name: str, injury_data: InjuryDataPayload
    ) -> None:
        """Execute an atomic append of an injury event to a player's medical history.

        Enforces strict fail-closed state validation prior to mutation. Verifies the
        target player exists in the current registry and delegates Pydantic model
        construction to `PlayerDataService`. Appends the resulting injury model to
        the player's internal injury history array.

        Writes the mutated list to the active `players.json` file using a safe atomic
        operation, followed by an immediate internal cache re-sync to ensure stability.

        Args:
            player_name (str): The exact registered name of the target player.
            injury_data (InjuryDataPayload): Validated dictionary payload containing
                                             the injury specifics
                                             (e.g., type, duration).

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If the target player does not exist, or if the injury data
                        fails strict Pydantic schema validation.
            OSError: If the atomic file replacement fails due to filesystem permissions.
        """
        players_path: Path = self._require_players_path()
        self.players: list[Player] = self._load_players_strict_or_raise()
        existing_player: Player = self._player_service.require_existing_player(
            players=self.players,
            player_name=player_name,
            action_description="add injury record",
        )

        logger.info("Saving injury record for %s", player_name)
        snapshot: InjuryRecord = self._player_service.create_injury_snapshot(
            player_name=player_name,
            injury_data=injury_data,
        )

        existing_player.injury_history.append(snapshot)

        self._json_service.save_json_atomic_or_raise(players_path, self.players)
        self.players: list[Player] = self._load_players_strict_or_raise()

    def sell_player(self, player_name: str, in_game_date: str) -> None:
        """Execute a status mutation to permanently mark a player record as sold.

        Delegates the state validation, atomic disk writing to `players.json`,
        and internal cache synchronization to `_update_player_status`.

        Args:
            player_name (str): The exact registered name of the target player.
            in_game_date (str): The chronological date of the transaction to append.

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If the target player does not exist, or if the status
                        update data fails validation.
            OSError: If the atomic file replacement fails due to filesystem permissions.
        """
        logger.info("Action: Selling player %s", player_name)
        self._update_player_status(
            player_name, status_key="sold", status_value=True, in_game_date=in_game_date
        )

    def loan_out_player(self, player_name: str) -> None:
        """Execute a status mutation to toggle a player record to an active loan state.

        Delegates the state validation, atomic disk writing to `players.json`,
        and internal cache synchronization to `_update_player_status`.

        Args:
            player_name (str): The exact registered name of the target player.

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If the target player does not exist, or if the status
                        update data fails validation.
            OSError: If the atomic file replacement fails due to filesystem permissions.
        """
        logger.info("Action: Loaning out player %s", player_name)
        self._update_player_status(player_name, status_key="loaned", status_value=True)

    def return_loan_player(self, player_name: str) -> None:
        """Execute a status mutation to reverse a player record's active loan state.

        Delegates the state validation, atomic disk writing to `players.json`,
        and internal cache synchronization to `_update_player_status`.

        Args:
            player_name (str): The exact registered name of the target player.

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If the target player does not exist, or if the status
                        update data fails validation.
            OSError: If the atomic file replacement fails due to filesystem permissions.
        """
        logger.info("Action: Returning player %s from loan", player_name)
        self._update_player_status(player_name, status_key="loaned", status_value=False)

    # --- Match Mutation Workflow ---

    def add_match(
        self,
        match_data: MatchOverviewPayload,
        player_performances: PlayerPerformanceBuffer,
    ):
        """Execute an atomic append of a fully constructed match record to matches.json.

        Uses a raw-list append strategy to preserve any historical invalid rows
        already present on disk, while still validating the newly built match model.
        Delegates complex relational mapping—including linking raw performance
        payloads to cached `Player` IDs and resolving polymorphic schemas—to
        `MatchDataService`.

        Args:
            match_data (MatchOverviewPayload): Validated dictionary containing global
                                               match statistics (e.g., score, opponent).
            player_performances (PlayerPerformanceBuffer): List of raw performance
                                                           dictionaries extracted
                                                           from the UI.

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If matches.json cannot be loaded as a raw JSON list.
            ValidationError: If the newly constructed match model fails
                             schema validation.
            KeyError: If expected keys are missing from player performance payloads.
            OSError: If the atomic file replacement fails due to filesystem permissions.
        """
        matches_path: Path = self._require_matches_path()
        raw_matches: list[JsonValue] = self._json_service.load_raw_list_or_raise(
            matches_path
        )
        match_id: int = self._generate_match_id_from_raw_rows(raw_matches)
        timestamp: datetime = datetime.now()

        logger.info(
            "Adding match %s vs %s with %s player performances.",
            match_id,
            match_data.get("away_team_name", "Unknown"),
            len(player_performances),
        )

        # Get team names from match_data
        home_raw = match_data.get("home_team_name")
        away_raw = match_data.get("away_team_name")
        home_team_name = (
            home_raw.strip()
            if isinstance(home_raw, str) and home_raw.strip()
            else "Unknown"
        )
        away_team_name = (
            away_raw.strip()
            if isinstance(away_raw, str) and away_raw.strip()
            else "Unknown"
        )

        # Get career team name from metadata
        career_metadata = self.get_current_career_metadata()
        career_team_name = career_metadata.club_name if career_metadata else None

        if not career_team_name:
            logger.warning(
                "Career team name is unknown; normalization may be inaccurate."
            )
        normalized_team_names = self._match_service.normalize_team_names(
            match_names=[home_team_name, away_team_name],
            full_matches_list=self.matches,
            career_team_name=career_team_name,
        )

        # Update match_data with normalized team names
        match_data["home_team_name"], match_data["away_team_name"] = (
            normalized_team_names
        )

        new_match: Match = self._match_service.build_match(
            match_id=match_id,
            match_data=match_data,
            player_performances=player_performances,
            players=self.players,
            timestamp=timestamp,
        )

        self._json_service.append_item_to_json_list_atomic_or_raise(
            matches_path,
            new_match,
        )
        self.refresh_matches()
        logger.info(
            "Match %s persisted successfully. Total cached matches: %s",
            match_id,
            len(self.matches),
        )

    # --- Internal Career Resolution Helpers ---

    def _load_duplicate_career_metadata(
        self,
        careers_details: list[CareerDetail],
        duplicate_club_names: set[str],
    ) -> dict[str, CareerMetadata | None]:
        """Load metadata only for careers whose club names are duplicated.

        Performs targeted disk I/O by constructing absolute paths to career
        subdirectories only if their associated club name appears in the duplicates set.
        Delegates the raw file reading and Pydantic model mapping to
        `JsonService.load_json`.

        Args:
            careers_details (list[CareerDetail]): The global registry of known
                                                  career profiles.
            duplicate_club_names (set[str]): The subset of club names requiring deeper
                                             metadata inspection (e.g.
                                             fetching manager names).

        Returns:
            dict[str, CareerMetadata | None]: A mapping of the career's folder name to
                                              its parsed metadata model. Values may be
                                              None if the underlying file is missing
                                              or corrupted.
        """
        metadata_by_folder: dict[str, CareerMetadata | None] = {}
        for career in careers_details:
            if career.club_name not in duplicate_club_names:
                continue

            meta_path: Path = self.data_folder / career.folder_name / "metadata.json"
            metadata_by_folder[career.folder_name] = self._json_service.load_json(
                meta_path,
                CareerMetadata,
                is_list=False,
            )

        return metadata_by_folder

    # --- Internal Path and Strict-Load Guards ---

    def _require_players_path(self) -> Path:
        """Validate and retrieve the internal pointer for the active players.json file.

        Acts as a strict pre-flight safety check for disk write operations. Enforces
        that the global career context has been successfully initialized (via
        `load_career`) before allowing mutation methods to proceed.

        Returns:
            Path: The absolute file path to the target players.json file.

        Raises:
            RuntimeError: If the internal state pointer is unset, indicating that
                          disk I/O was attempted without an active career context.
        """
        players_path: Path | None = self.players_path
        if players_path is None:
            raise RuntimeError(
                "Cannot save players: no active career/players path is set."
            )
        return players_path

    def _require_matches_path(self) -> Path:
        """Validate and retrieve the internal pointer for the active matches.json file.

        Acts as a strict pre-flight safety check for disk write operations. Enforces
        that the global career context has been successfully initialized (via
        `load_career`) before allowing mutation methods to proceed.

        Returns:
            Path: The absolute file path to the target matches.json file.

        Raises:
            RuntimeError: If the internal state pointer is unset, indicating that
                          disk I/O was attempted without an active career context.
        """
        matches_path: Path | None = self.matches_path
        if matches_path is None:
            raise RuntimeError(
                "Cannot save matches: no active career/matches path is set."
            )
        return matches_path

    def _load_players_strict_or_raise(self) -> list[Player]:
        """Read and validate the active career's players.json file from disk.

        Enforces a strict fail-closed data contract. If the file is missing,
        malformed, or contains data that violates the Pydantic schema, it refuses
        to proceed. Delegates the raw disk I/O and parsing to
        `JsonService.load_list_strict_or_raise`.

        Returns:
            list[Player]: A fully validated list of Pydantic Player models.

        Raises:
            RuntimeError: If called before a career context path is initialized.
            ValueError: If the JSON cannot be decoded or fails schema validation.
        """
        if not (players_path := self.players_path):
            raise RuntimeError(
                "Cannot load players: no active career/players path is set."
            )

        return self._json_service.load_list_strict_or_raise(players_path, Player)

    def _load_matches_strict_or_raise(self) -> list[Match]:
        """Read and validate the active career's matches.json file from disk.

        Enforces a strict fail-closed data contract. If the file is missing,
        malformed, or contains data that violates the Pydantic schema, it refuses
        to proceed. Delegates the raw disk I/O and parsing to
        `JsonService.load_list_strict_or_raise`.

        Returns:
            list[Match]: A fully validated list of Pydantic Match models.

        Raises:
            RuntimeError: If called before a career context path is initialized.
            ValueError: If the JSON cannot be decoded or fails schema validation.
        """
        if not (matches_path := self.matches_path):
            raise RuntimeError(
                "Cannot load matches: no active career/matches path is set."
            )

        return self._json_service.load_list_strict_or_raise(matches_path, Match)

    # --- Internal Mutation Utilities ---

    def _update_player_status(
        self,
        player_name: str,
        status_key: Literal["sold", "loaned"],
        status_value: bool,
        in_game_date: str | None = None,
    ) -> None:
        """Execute a mutation of a specific boolean status flag on a player record.

        Enforces strict fail-closed state validation prior to mutation. Verifies the
        target player exists in the active registry and delegates the precise field
        modification to `PlayerDataService`.

        Writes the mutated list to the active `players.json` file using a safe atomic
        operation, followed by an immediate internal cache re-sync to guarantee
        alignment between disk and memory.

        Args:
            player_name (str): The exact registered name of the target player.
            status_key (Literal["sold", "loaned"]): The specific Pydantic status
                                                    field to mutate.
            status_value (bool): The new boolean state to apply to the field.
            in_game_date (str | None, optional): The chronological date of the mutation,
                                                 required if processing a sale.
                                                 Defaults to None.

        Raises:
            RuntimeError: If called without an initialized career context.
            ValueError: If the target player does not exist, or if the mutation data
                        fails strict Pydantic validation (e.g., missing sale date).
            OSError: If the atomic file replacement fails due to filesystem permissions.
        """
        self.players: list[Player] = self._load_players_strict_or_raise()
        players_path: Path = self._require_players_path()
        existing_player: Player = self._player_service.require_existing_player(
            players=self.players,
            player_name=player_name,
            action_description=f"update status '{status_key}'",
        )

        self._player_service.apply_player_status(
            existing_player=existing_player,
            status_key=status_key,
            status_value=status_value,
            in_game_date=in_game_date,
        )

        self._json_service.save_json_atomic_or_raise(players_path, self.players)
        self.players: list[Player] = self._load_players_strict_or_raise()

    def _generate_id(self, collection: Sequence[SupportsId]) -> int:
        """Calculate the next sequential integer ID for a data collection.

        Scans the provided sequence of objects (which must expose an `.id` attribute)
        to determine the current maximum ID, returning the next available integer.
        Used internally to guarantee unique primary keys
        before appending models to disk.

        Args:
            collection (Sequence[SupportsId]): The loaded sequence of data objects.

        Returns:
            int: The next available ID, defaulting to 1 if the collection is empty.
        """
        return max((item.id for item in collection), default=0) + 1

    @staticmethod
    def _generate_match_id_from_raw_rows(raw_rows: list[JsonValue]) -> int:
        """Calculate the next match ID from raw JSON list entries.

        Only dictionary rows with an integer `id` are considered. Malformed IDs
        and non-dict rows are ignored.

        Args:
            raw_rows (list[JsonValue]): Raw decoded entries from matches.json.

        Returns:
            int: The next available match ID, defaulting to 1 when none exist.
        """
        max_id = 0
        for row in raw_rows:
            if not isinstance(row, dict):
                continue

            row_id = row.get("id")
            if type(row_id) is int:
                max_id = max(max_id, row_id)

        return max_id + 1
