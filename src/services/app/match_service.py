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
from typing import Literal, cast

from src.contracts.backend import (
    MatchOverviewPayload,
    MatchStatsPayload,
    PlayerPerformanceBuffer,
)
from src.data_manager import DataManager
from src.exceptions import (
    DataDiscrepancyError,
    DataPersistenceError,
    IncompleteDataError,
)

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
        force_save: bool = False,
    ) -> None:
        """Persist a match overview and optional player performances.

        Validate the supplied payload, normalize optional performance data, and
        delegate the save operation to the DataManager with error translation.

        Args:
            match_overview (MatchOverviewPayload): Core match metadata and summary
                details required to describe the match.
            player_performances (PlayerPerformanceBuffer | None, optional): Optional
                collection of player-level performance records for the match.
            force_save (bool, optional): If True, bypass certain validation checks
                and attempt to save the match regardless of data completeness. Use
                with caution.

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
        discrepancies: dict[str, dict[str, int]] = {}

        if (
            not force_save
            and normalized_performances
            and (
                discrepancies := self._check_stat_cohesion(
                    match_overview, normalized_performances
                )
            )
        ):
            logger.warning(f"Stat discrepancies detected: {discrepancies}")
            raise DataDiscrepancyError(
                "Mismatch between team totals and player sums.",
                discrepancies=discrepancies,
            )

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

    def _check_stat_cohesion(
        self, overview: MatchOverviewPayload, performances: PlayerPerformanceBuffer
    ) -> dict[str, dict[str, int]]:
        """Evaluate consistency between team statistics and player-level aggregates.

        This method cross-checks key match stats from the overview against the
        sum of outfield player performances, applying stat-specific tolerance
        rules and returning any detected discrepancies.

        Args:
            overview (MatchOverviewPayload): Match overview payload containing the
                user's team stats and scoreline.
            performances (PlayerPerformanceBuffer): Collection of player
                performance entries used to calculate aggregated player statistics.

        Returns:
            dict[str, dict[str, int]]: A mapping of stat names to discrepancy
                details, including expected team total, actual player sum, and
                a strictness flag indicating validation severity.
        """
        career_meta = self.data_manager.get_current_career_metadata()
        if not career_meta:
            logger.debug("No career metadata available for stat cohesion check.")
            return {}
        career_name: str = career_meta.club_name
        home_team = overview.get("home_team_name")
        home_or_away: Literal["home", "away"] = (
            "home" if home_team == career_name else "away"
        )
        raw_user_stats = overview.get(f"{home_or_away}_stats", {})
        if isinstance(raw_user_stats, dict):
            user_stats = cast(MatchStatsPayload, raw_user_stats)
        else:
            user_stats = {}

        # Define stats and their validation 'strictness'
        # True = Must match exactly (except Own Goal logic for goals)
        # False = Warning only
        stat_manifest = {
            "goals": True,
            "shots": True,
            "fouls_committed": True,
            "offsides": True,
            "tackles": False,
            "passes": True,
        }

        discrepancies = {}

        for stat, is_strict in stat_manifest.items():
            team_total = user_stats.get(stat, 0)
            player_sum = sum(
                p.get(stat, 0)
                for p in performances
                if p.get("performance_type") == "Outfield"
            )

            # Goals need to be processed differently, as they are not stored in
            # "home_stats"/"away_stats", but rather directly in the overview as
            # "home_score"/"away_score". We can infer the team total goals from these
            # fields instead of relying on the user_stats.
            if stat == "goals":
                team_total = overview.get(f"{home_or_away}_score", 0)

            # Special Case: Own Goals
            if stat == "goals" and team_total > player_sum:
                # This is likely an own goal, not an error.
                continue

            # Special Case: Passes tolerance
            # Allow up to 20 missing player passes vs team total,
            # to account for passes made by GK, which are not currently tracked
            # at the player level
            if (
                stat == "passes"
                and team_total >= player_sum
                and (team_total - player_sum) <= 20
            ):
                continue

            if team_total != player_sum:
                discrepancies[stat] = {
                    "expected": team_total,
                    "actual": player_sum,
                    "strict": is_strict,
                }

        return discrepancies

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
