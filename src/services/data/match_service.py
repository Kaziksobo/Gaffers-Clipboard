"""Match-focused pure helpers for DataManager orchestration.

This module holds transformation and validation helpers used by DataManager's
match write flow. It intentionally performs no filesystem I/O and does not
depend on other data services.
"""

import logging
from datetime import datetime

from src.contracts.backend import (
    GoalkeeperPerformancePayload,
    MatchOverviewPayload,
    OutfieldPerformancePayload,
    PlayerPerformanceBuffer,
)
from src.schemas import (
    GoalkeeperPerformance,
    Match,
    MatchData,
    OutfieldPlayerPerformance,
    Player,
)
from src.utils import normalize_team_name

logger = logging.getLogger(__name__)


class MatchService:
    """Provide pure match-domain helpers for DataManager."""

    # ----------------- Match Construction Flow -----------------

    def build_match(
        self,
        *,
        match_id: int,
        match_data: MatchOverviewPayload,
        player_performances: PlayerPerformanceBuffer,
        players: list[Player],
        timestamp: datetime,
    ) -> Match:
        """Build a validated Match model from raw input data.

        This method orchestrates the transformation of raw match overview data and
        player performance buffers into a fully-formed Match instance ready for
        persistence. It handles player name resolution, performance type
        differentiation, and delegates the construction of specific performance models
        to dedicated helpers.

        Args:
            match_id (int): Unique identifier for the match, typically assigned
                            by DataManager.
            match_data (MatchOverviewPayload): The raw match overview data.
            player_performances (PlayerPerformanceBuffer): The raw player
                                                           performance data.
            players (list[Player]): The list of available players.
            timestamp (datetime): The timestamp for the match.

        Returns:
            Match: A validated Match instance.

        Raises:
            ValidationError: If any part of the match data or player performances fails
                            validation checks during model construction.
            KeyError: If expected fields are missing from the input data.
        """
        normalized_performances = self.normalize_player_performances(
            player_performances=player_performances,
            players=players,
            match_id=match_id,
        )

        return Match(
            id=match_id,
            datetime=timestamp,
            data=MatchData.model_validate(match_data),
            player_performances=normalized_performances,
        )

    def normalize_player_performances(
        self,
        *,
        player_performances: PlayerPerformanceBuffer,
        players: list[Player],
        match_id: int,
    ) -> list[GoalkeeperPerformance | OutfieldPlayerPerformance]:
        """Normalize raw player performance data into validated performance models.

        This method iterates through the raw performance buffer, resolves player names
        to IDs, differentiates between goalkeeper and outfield performances, and builds
        the corresponding performance models using dedicated helper methods. It also
        logs warnings for any player names that cannot be resolved
        to ensure data integrity.

        Args:
            player_performances (PlayerPerformanceBuffer): The raw player performance
                                                           data to normalize.
            players (list[Player]): The list of available players.
            match_id (int): The ID of the match for which to normalize performances.

        Returns:
            list[GoalkeeperPerformance | OutfieldPlayerPerformance]: The list of
                                                                     normalized
                                                                     performance models.

        Raises:
            ValidationError: If any performance data fails validation
                             during model construction.
            KeyError: If expected fields are missing from the performance data.
        """
        normalized_performances: list[
            GoalkeeperPerformance | OutfieldPlayerPerformance
        ] = []

        for performance in player_performances:
            player_name = performance["player_name"]
            player_id = self.find_player_id_by_name(players, player_name)

            if player_id is None:
                logger.warning(
                    "Skipping stats for '%s' in match %s: "
                    "Player not found in database.",
                    player_name,
                    match_id,
                )
                continue

            if performance["performance_type"] == "GK":
                normalized_performances.append(
                    self._build_goalkeeper_performance(performance, player_id)
                )
            else:
                normalized_performances.append(
                    self._build_outfield_performance(performance, player_id)
                )

        return normalized_performances

    @staticmethod
    def find_player_id_by_name(players: list[Player], name: str) -> int | None:
        """Find a player's ID by name (case-insensitive) from a supplied list."""
        if not name:
            return None

        name_norm = name.strip().lower()
        player = next(
            (
                existing
                for existing in players
                if existing.name.strip().lower() == name_norm
            ),
            None,
        )
        return player.id if player else None

    @staticmethod
    def _build_goalkeeper_performance(
        performance: GoalkeeperPerformancePayload,
        player_id: int,
    ) -> GoalkeeperPerformance:
        """Build a validated goalkeeper performance model from typed payload data.

        Raises:
            ValidationError: If the performance data fails validation
                             during model construction.
        """
        return GoalkeeperPerformance(
            performance_type="GK",
            shots_against=performance["shots_against"],
            shots_on_target=performance["shots_on_target"],
            saves=performance["saves"],
            goals_conceded=performance["goals_conceded"],
            save_success_rate=performance["save_success_rate"],
            punch_saves=performance["punch_saves"],
            rush_saves=performance["rush_saves"],
            penalty_saves=performance["penalty_saves"],
            penalty_goals_conceded=performance["penalty_goals_conceded"],
            shoot_out_saves=performance["shoot_out_saves"],
            shoot_out_goals_conceded=performance["shoot_out_goals_conceded"],
            match_rating=performance.get("match_rating"),
            player_id=player_id,
        )

    @staticmethod
    def _build_outfield_performance(
        performance: OutfieldPerformancePayload,
        player_id: int,
    ) -> OutfieldPlayerPerformance:
        """Build a validated outfield performance model from typed payload data.

        Raises:
            ValidationError: If the performance data fails validation
                             during model construction.
        """
        return OutfieldPlayerPerformance(
            performance_type="Outfield",
            positions_played=performance["positions_played"],
            goals=performance["goals"],
            assists=performance["assists"],
            shots=performance["shots"],
            shot_accuracy=performance["shot_accuracy"],
            passes=performance["passes"],
            pass_accuracy=performance["pass_accuracy"],
            dribbles=performance["dribbles"],
            dribble_success_rate=performance["dribble_success_rate"],
            tackles=performance["tackles"],
            tackle_success_rate=performance["tackle_success_rate"],
            offsides=performance["offsides"],
            fouls_committed=performance["fouls_committed"],
            possession_won=performance["possession_won"],
            possession_lost=performance["possession_lost"],
            minutes_played=performance["minutes_played"],
            distance_covered=performance["distance_covered"],
            distance_sprinted=performance["distance_sprinted"],
            match_rating=performance.get("match_rating"),
            player_id=player_id,
        )

    # ----------------- Helpers -----------------

    def get_latest_in_game_date(self, matches: list[Match]) -> datetime | None:
        """Return the latest in-game date from an in-memory match list."""
        if not matches:
            return None

        try:
            latest = max(matches, key=lambda match: match.data.in_game_date)
            return latest.data.in_game_date
        except Exception as e:
            logger.warning("Failed to compute latest match date: %s", e)
            return None

    def normalize_team_names(
        self,
        match_names: list[str],
        full_matches_list: list[Match],
        career_team_name: str | None = None,
    ) -> list[str]:
        """Normalize team names from match overview data against existing matches."""
        reference_names: set[str] = set()
        for match in full_matches_list:
            reference_names.add(match.data.home_team_name)
            reference_names.add(match.data.away_team_name)

        if career_team_name:
            reference_names.add(career_team_name)
        return [
            normalize_team_name(name, list(reference_names)) for name in match_names
        ]
