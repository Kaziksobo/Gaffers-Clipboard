"""
CareerService - application-facing career context operations.

This module provides a thin service layer over DataManager for creating,
activating, querying, and updating the currently selected career. It keeps
controller code small by centralizing career-specific workflows such as
loading a career, refreshing related collections, and managing competition and
metadata changes.

Responsibilities:
- Create and activate new careers.
- Load an existing career into the active application context.
- Expose safe accessors for current career metadata and display names.
- Guard mutations that require an active career context.

Persistence remains the responsibility of DataManager; CareerService exists to
coordinate those operations behind a controller-friendly API.
"""

import logging

from src.contracts.backend import CareerMetadataUpdate
from src.data_manager import DataManager
from src.schemas import CareerMetadata, DifficultyLevel

logger = logging.getLogger(__name__)


class CareerService:
    """Provide career-context operations for the application.

    CareerService is a thin controller-facing wrapper around DataManager. It
    handles creating and activating careers, exposing current career metadata,
    and guarding updates that require an active career context.
    """

    def __init__(self, data_manager: DataManager) -> None:
        """Initialize the career service.

        Args:
            data_manager (DataManager): Shared persistence manager used to load,
                                        create, and update career data.
        """
        self._data_manager = data_manager

    # ----------------- Career Selection Methods -----------------

    def get_all_career_names(self) -> list[str]:
        """Retrieve all registered career names from persistent storage.

        Returns:
            list[str]: A list of formatted career display names retrieved from disk.
        """
        return self._data_manager.get_all_career_names()

    def activate_career(self, career_name: str) -> None:
        """Switch the active application context to the specified career.

        Loads the selected career into the DataManager context.

        Args:
            career_name (str): Unique name of the career to activate.

        Raises:
            ValueError: If the career cannot be loaded.
        """
        logger.info("Setting current career to: %s", career_name)

        if not self._data_manager.load_career(career_name):
            raise ValueError(f"Career '{career_name}' could not be loaded.")

    def save_new_career(
        self,
        club_name: str,
        manager_name: str,
        starting_season: str,
        half_length: int,
        match_difficulty: DifficultyLevel,
        league: str,
    ) -> None:
        """Create and activate a new career.

        Persist a new career via DataManager.create_new_career.

        Args:
            club_name (str): Display name of the club.
            manager_name (str): Manager's name for the career.
            starting_season (str): Season label (e.g., "2024/25").
            half_length (int): Match half length in minutes.
            match_difficulty (DifficultyLevel): Difficulty setting.
            league (str): League identifier.

        Raises:
            ValidationError: If the provided career details fail
                             validation in DataManager.
        """
        self._data_manager.create_new_career(
            club_name,
            manager_name,
            starting_season,
            half_length,
            match_difficulty,
            league,
        )

    def get_current_career_details(self) -> CareerMetadata | None:
        """Return metadata for the currently active career, if one is selected.

        Fetch the active career metadata from DataManager. If no career is active,
        return None and log the absence of an active context.

        Returns:
            CareerMetadata | None: Metadata for the active career, or None if no
                                   career is currently selected.
        """
        metadata = self._data_manager.get_current_career_metadata()
        if metadata is None:
            logger.debug(
                "Attempted to get career details, but no active career context is set."
            )
            return None

        return metadata

    # ----------------- Career Mutation Methods -----------------

    def add_competition(self, competition: str) -> None:
        """Add a competition to the current career via the DataManager.

        Ensure an active career context exists before delegating the operation
        to the underlying DataManager.

        Args:
            competition (str): Name of the competition to add.

        Raises:
            RuntimeError: If no active career is set in the DataManager.
        """
        self._ensure_active_career_context()
        self._data_manager.add_competition(competition)

    def remove_competition(self, competition: str) -> None:
        """Remove a competition from the current career via the DataManager.

        Ensure an active career context exists before delegating the operation
        to the underlying DataManager.

        Args:
            competition (str): Name of the competition to remove.

        Raises:
            RuntimeError: If no active career is set in the DataManager.
            ValueError: If the specified competition does not exist
                        in the current career.
        """
        self._ensure_active_career_context()
        self._data_manager.remove_competition(competition)

    def update_career_metadata(self, updates: CareerMetadataUpdate) -> None:
        """Update current career metadata via the DataManager.

        Ensure an active career context exists before delegating the operation
        to the underlying DataManager.

        Args:
            updates (CareerMetadataUpdate): Partial metadata patch payload.

        Raises:
            RuntimeError: If no active career is set in the DataManager.
            ValidationError: If the provided updates fail validation in DataManager.
        """
        self._ensure_active_career_context()
        self._data_manager.update_career_metadata(updates)

    # ----------------- Internal Helpers -----------------

    def _ensure_active_career_context(self) -> None:
        """Ensure an active career is loaded in the DataManager context.

        Raises:
            RuntimeError: If no active career is set in the DataManager.
        """
        if not self._data_manager.current_career:
            raise RuntimeError("No career loaded")
