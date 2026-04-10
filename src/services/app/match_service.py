"""
MatchService - application-facing match persistence and lookup operations.

This module defines `MatchService`, a thin service layer over `DataManager`
for saving match records and retrieving match-related metadata. It enforces
minimal preconditions for match writes, normalizes optional performance payloads,
and translates lower-level persistence failures into service-level exceptions.

Responsibilities:
- Persist match overview data and optional player performance payloads.
- Guard against incomplete match saves (missing overview data).
- Wrap DataManager write failures as `DataPersistenceError`.
- Provide safe access to the latest in-game match date.

The service is UI-agnostic and focused on orchestration, validation gates,
and error-boundary behavior for match workflows.
"""

import logging
from datetime import datetime

from src.contracts.backend import MatchOverviewPayload, PlayerPerformanceBuffer
from src.data_manager import DataManager
from src.exceptions import DataPersistenceError, IncompleteDataError

logger = logging.getLogger(__name__)


class MatchService:
    """Provide match persistence and lookup operations for the application.

    MatchService coordinates saving match payloads and retrieving match metadata
    through a shared DataManager instance while enforcing simple validation
    and error handling boundaries.
    """

    def __init__(self, data_manager: DataManager) -> None:
        """Initialize the match service with a shared DataManager instance.

        Args:
            data_manager (DataManager): Persistence layer used for match reads
                and writes.
        """
        self.data_manager = data_manager

    def save_match(
        self,
        match_overview: MatchOverviewPayload,
        player_performances: PlayerPerformanceBuffer | None = None,
    ) -> None:
        """Persist a match overview and optional player performances.

        Validate the supplied payload, normalize optional performance data, and
        delegate the save operation to the DataManager with error translation.

        Args:
            match_overview (MatchOverviewPayload): Core match metadata and summary
                details required to describe the match.
            player_performances (PlayerPerformanceBuffer | None, optional): Optional
                collection of player-level performance records for the match.

        Raises:
            IncompleteDataError: If the match overview payload is missing or
                empty.
            DataPersistenceError: If the underlying DataManager fails while
                saving the match.
        """
        if not match_overview:
            logger.error("Match save aborted: Match overview payload is missing.")
            raise IncompleteDataError("Cannot save match: Missing match overview data.")

        normalized_performances = player_performances or []

        logger.info(
            "Persisting match (competition: %s, opponent: %s, performances: %s).",
            match_overview.get("competition", "Unknown"),
            match_overview.get("away_team_name", "Unknown"),
            len(normalized_performances),
        )

        try:
            self.data_manager.add_match(
                match_data=match_overview,
                player_performances=normalized_performances,
            )
            logger.info(
                "Match persisted successfully for opponent: %s",
                match_overview.get("away_team_name", "Unknown"),
            )
        except Exception as e:
            logger.error("DataManager failed to save match: %s", e, exc_info=True)
            raise DataPersistenceError(f"Failed to save match data: {e}") from e

    def get_latest_match_in_game_date(self) -> datetime | None:
        """Fetch the in-game date of the most recently recorded match.

        Provides a safe wrapper around the DataManager, returning None instead of
        propagating errors if the lookup fails or no matches are available.

        Returns:
            datetime | None: The in-game date of the latest match, or None on failure.
        """
        try:
            return self.data_manager.get_latest_match_in_game_date()
        except Exception as e:
            logger.debug("Failed to get latest match date from DataManager: %s", e)
            return None
