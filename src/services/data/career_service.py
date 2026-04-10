"""Career-focused planning helpers for DataManager orchestration.

This module provides pure construction logic for creating a new career while
leaving orchestration and persistence ownership in DataManager.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from src.contracts.backend import CareerCreationArtifacts, CareerMetadataUpdate
from src.schemas import CareerDetail, CareerMetadata, DifficultyLevel, Match
from src.utils import capitalize_competition_name

logger = logging.getLogger(__name__)


class CareerService:
    """Build career creation artifacts without mutating DataManager state."""

    # ----------------- Career Creation Planning -----------------

    def prepare_new_career(
        self,
        *,
        data_folder: Path,
        project_root: Path,
        club_name: str,
        manager_name: str,
        starting_season: str,
        half_length: int,
        difficulty: DifficultyLevel,
        league: str,
        career_id: int,
        created_at: datetime | None = None,
    ) -> CareerCreationArtifacts:
        """Construct paths and metadata needed to create a new career.

        This helper normalizes input values, derives derived folder names, and
        assembles a validated set of artifacts for DataManager to persist.

        Args:
            data_folder (Path): Base directory where all career data is stored.
            project_root (Path): Root directory of the project used to locate
                configuration files such as default competitions.
            club_name (str): Display name of the managed club.
            manager_name (str): Name of the human or in-game manager.
            starting_season (str): Identifier for the first season of the career.
            half_length (int): Match half length in minutes.
            difficulty (DifficultyLevel): Selected difficulty level for the career.
            league (str): League name in which the club competes.
            career_id (int): Unique numeric identifier for the career.
            created_at (datetime | None): Optional creation timestamp; defaults
                to the current time when omitted.

        Returns:
            CareerCreationArtifacts: Aggregated file paths, metadata, and summary
            detail needed by DataManager to initialize the career on disk.

        Raises:
            ValidationError: If the assembled metadata fails validation checks.
        """
        normalized_club = club_name.replace(" ", "_").lower()
        career_folder_name = f"{normalized_club}_{career_id}"
        career_path = data_folder / career_folder_name
        players_path = career_path / "players.json"
        matches_path = career_path / "matches.json"

        league_title = capitalize_competition_name(league)
        competitions = self._load_default_competitions(project_root, league_title)
        competitions = [
            capitalize_competition_name(competition) for competition in competitions
        ]

        metadata = CareerMetadata(
            career_id=career_id,
            club_name=club_name,
            folder_name=career_folder_name,
            manager_name=manager_name,
            created_at=created_at or datetime.now(),
            starting_season=starting_season,
            half_length=half_length,
            difficulty=difficulty,
            league=league_title,
            competitions=competitions,
        )

        new_detail = CareerDetail(
            id=career_id,
            club_name=club_name,
            folder_name=career_folder_name,
        )

        return CareerCreationArtifacts(
            career_folder_name=career_folder_name,
            career_path=career_path,
            players_path=players_path,
            matches_path=matches_path,
            metadata=metadata,
            new_detail=new_detail,
        )

    def _load_default_competitions(
        self,
        project_root: Path,
        league_title: str,
    ) -> list[str]:
        """Load default competitions for a league from the configuration file.

        This helper inspects the league configuration JSON and returns a
        sanitized list of competition names for the given league title.
        """
        competitions: list[str] = []
        config_path = project_root / "config" / "league_competitions.json"
        if not config_path.exists():
            return competitions

        try:
            with Path.open(config_path, encoding="utf-8") as f:
                defaults = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to load league defaults from config: %s", e)
            return competitions

        if (
            isinstance(defaults, dict)
            and "leagues" in defaults
            and isinstance(defaults["leagues"], dict)
        ):
            defaults = defaults["leagues"]

        if isinstance(defaults, dict) and league_title in defaults:
            loaded = defaults.get(league_title)
            if isinstance(loaded, list):
                competitions = [entry for entry in loaded if isinstance(entry, str)]

        return competitions

    # ----------------- Career Display Name Resolution -----------------

    @staticmethod
    def get_duplicate_club_names(careers_details: list[CareerDetail]) -> set[str]:
        """Identify club names that occur more than once across careers.

        This helper scans already-loaded career details to find clubs that need
        disambiguation when building display names.
        """
        name_counts: dict[str, int] = {}
        for career in careers_details:
            name_counts[career.club_name] = name_counts.get(career.club_name, 0) + 1

        return {club_name for club_name, count in name_counts.items() if count > 1}

    @staticmethod
    def build_display_name(
        career: CareerDetail,
        *,
        is_duplicate: bool,
        metadata: CareerMetadata | None,
    ) -> str:
        """Build a human-friendly display label for a single career entry.

        When multiple careers share a club name, this helper appends either the
        manager name or career id to disambiguate them.
        """
        if not is_duplicate:
            return career.club_name

        if metadata is not None:
            return f"{career.club_name} ({metadata.manager_name})"

        return f"{career.club_name} ({career.id})"

    def build_display_names(
        self,
        careers_details: list[CareerDetail],
        duplicate_club_names: set[str],
        metadata_by_folder: dict[str, CareerMetadata | None],
    ) -> list[str]:
        """Build display labels for a collection of careers.

        This helper coordinates duplicate-name detection and metadata lookup to
        produce a stable list of user-facing career names.
        """
        return [
            self.build_display_name(
                career,
                is_duplicate=career.club_name in duplicate_club_names,
                metadata=metadata_by_folder.get(career.folder_name),
            )
            for career in careers_details
        ]

    def find_career_by_display_name(
        self,
        *,
        careers_details: list[CareerDetail],
        duplicate_club_names: set[str],
        metadata_by_folder: dict[str, CareerMetadata | None],
        selected_name: str,
    ) -> CareerDetail | None:
        """Given a display name selected by the user, find the related CareerDetail.

        This helper reverses the display name construction process to match a
        user-selected name back to its underlying CareerDetail, which contains
        the necessary folder and ID information for loading the career.

        Args:
            careers_details (list[CareerDetail]): List of all career details
                                                  loaded from the registry.
            duplicate_club_names (set[str]): Set of club names that appear
                                             more than once.
            metadata_by_folder (dict[str, CareerMetadata  |  None]): Mapping of folder
                                                                     names to their
                                                                     corresponding
                                                                     metadata.
            selected_name (str): The display name selected by the user.

        Returns:
            CareerDetail | None: The matching career detail or None if not found.
        """
        for career in careers_details:
            candidate_name = self.build_display_name(
                career,
                is_duplicate=career.club_name in duplicate_club_names,
                metadata=metadata_by_folder.get(career.folder_name),
            )
            if candidate_name == selected_name:
                return career

        return None

    # ----------------- Competition Metadata Updates -----------------

    def add_competition_to_metadata(
        self,
        *,
        metadata: CareerMetadata,
        competition: str,
    ) -> bool:
        """Add a competition to metadata when not already present.

        Normalizes the competition name and checks for existence before adding to avoid
        duplicates. Returns True if the metadata was modified, False if the competition
        was already present.

        Args:
            metadata (CareerMetadata): The career metadata to update.
            competition (str): The competition name to add.

        Returns:
            bool: True if the metadata was modified, False if
                  the competition was already present.
        """
        normalized = capitalize_competition_name(competition)
        competitions = metadata.competitions or []

        if normalized in competitions:
            return False

        competitions.append(normalized)
        metadata.competitions = competitions
        return True

    def ensure_competition_not_referenced(
        self,
        *,
        matches: list[Match],
        competition: str,
    ) -> None:
        """Raise when any existing match references the given competition.

        Raises:
            ValueError: If any match in the provided list references the normalized
                        competition name, indicating that it cannot be safely removed.
        """
        normalized = capitalize_competition_name(competition)

        for match in matches:
            existing = capitalize_competition_name(match.data.competition)
            if existing == normalized:
                raise ValueError(
                    f"Competition '{normalized}' is referenced by existing "
                    "matches and cannot be removed."
                )

    def remove_competition_from_metadata(
        self,
        *,
        metadata: CareerMetadata,
        competition: str,
    ) -> bool:
        """Remove a competition from metadata when present and not used by matches.

        Normalizes the competition name and checks for existence before removing.
        Returns True if the metadata was modified,
        False if the competition was not found.

        Args:
            metadata (CareerMetadata): The career metadata to update.
            competition (str): The competition name to remove.

        Returns:
            bool: True if the metadata was modified, False if the
                  competition was not found.
        """
        normalized = capitalize_competition_name(competition)
        current = metadata.competitions or []
        filtered = [existing for existing in current if existing != normalized]
        metadata.competitions = filtered
        return len(filtered) != len(current)

    # ----------------- Metadata Patch Validation -----------------

    def build_updated_metadata(
        self,
        *,
        metadata: CareerMetadata,
        updates: CareerMetadataUpdate,
    ) -> CareerMetadata:
        """Return a validated CareerMetadata after applying partial updates.

        Raises:
            ValidationError: If the merged metadata fails validation checks.
        """
        merged = metadata.model_dump()
        merged.update(updates)

        try:
            return CareerMetadata(**merged)
        except ValidationError as e:
            logger.error("Metadata validation failed: %s", e)
            raise
