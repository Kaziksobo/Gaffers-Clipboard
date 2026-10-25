"""
ReliableRatingService - underlying-quality estimates from match ratings.

This module defines `ReliableRatingService`, a UI-agnostic analytics service that
turns a player's chronological match ratings into a single estimate of their
underlying quality, shrunk toward the population mean when evidence is thin.

Responsibilities:
- Run a local-level (Kalman-style) filter over rated appearances, seeded at the
  population mean.
- Inflate uncertainty at season boundaries so older evidence is gradually
  discounted (drift).
- Report the estimate alongside its uncertainty.

With zero season drift the filter reduces exactly to a shrunk mean. The service
is a pure function of its inputs; data loading, ordering, and filtering by
availability are handled elsewhere. The estimate is internal-only and feeds
downstream analytics such as the lineup optimiser.
"""

import logging
from typing import Final

from src.contracts.analytics import (
    PlayerRatingHistory,
    RatedAppearance,
    ReliableRating,
)
from src.utils import season_start_year

logger = logging.getLogger(__name__)


class ReliableRatingService:
    """Provide shrinkage-based underlying-quality estimates for players.

    ReliableRatingService ingests a player's rated appearances and applies a
    local-level filter to produce a rating estimate, the number of appearances it
    rests on, and its standard error.
    """

    # ── Prior ─────────────────────────────────────────────────────────────────────

    # Population mean of match ratings (the ratings sigmoid midpoint). Every
    # player's estimate starts here and is pulled back toward it when evidence is thin.
    PRIOR_MEAN: Final[float] = 6.0

    # Between-player variance of true quality (sigma_b^2). Provisional: a rough
    # estimate from early data, to be fitted offline in the workshop notebook.
    PRIOR_VARIANCE: Final[float] = 0.25

    # ── Observation noise ─────────────────────────────────────────────────────────

    # Within-player, match-to-match variance of ratings (sigma_o^2). Provisional: a
    # rough estimate from early data, to be fitted offline in the workshop notebook.
    OBSERVATION_VARIANCE: Final[float] = 0.58

    # ── Drift ─────────────────────────────────────────────────────────────────────

    # Variance added to a player's true-quality estimate per in-game season elapsed
    # since their previous rated appearance (q). 0 gives a plain shrunk mean.
    # Provisional: kept at 0 until the workshop notebook shows drift improves
    # held-out error.
    SEASON_DRIFT_VARIANCE: Final[float] = 0.0

    def calculate_player_rating(
        self, history: PlayerRatingHistory
    ) -> ReliableRating | None:
        """Calculate a player's reliable rating from their rated appearances.

        Runs the filter over the player's appearances and packages the final
        estimate. Returns None when the player has no rated appearances, since the
        prior alone is not a rating.

        Args:
            history (PlayerRatingHistory): The player's rated appearances in
                                           chronological order.

        Returns:
            ReliableRating | None: The estimate, appearance count, and standard
                                   error, or None if there are no rated appearances.
        """
        appearances = history["appearances"]

        if not appearances:
            logger.debug(
                "Player %s has no rated appearances; returning None",
                history["player_id"],
            )
            return None

        mean, variance = self._run_filter(appearances)

        return ReliableRating(
            player_id=history["player_id"],
            rating=mean,
            n=len(appearances),
            std_error=variance**0.5,
        )

    def _run_filter(self, appearances: list[RatedAppearance]) -> tuple[float, float]:
        """Run the local-level filter across a player's rated appearances.

        The estimate starts at PRIOR_MEAN with variance PRIOR_VARIANCE. For each
        appearance, variance is first inflated by SEASON_DRIFT_VARIANCE times the
        number of seasons since the previous appearance (none before the first,
        none within a season), then the estimate and variance are updated with
        the observed rating.

        Args:
            appearances (list[RatedAppearance]): Non-empty rated appearances in
                                                 chronological order.

        Returns:
            tuple[float, float]: The final estimate on the 0-10 rating scale and
                                 its posterior variance.
        """
        # Initialise the filter at the population mean with its variance.
        mean, variance = self.PRIOR_MEAN, self.PRIOR_VARIANCE

        prev_season: int | None = None

        for a in appearances:
            season: int = season_start_year(a["in_game_date"])
            if prev_season is not None:
                # Inflate variance for the number of seasons since the prev appearance.
                variance += self.SEASON_DRIFT_VARIANCE * (season - prev_season)
            # Calculate the Kalman gain for this observation, which determines how much
            # to weight the new rating versus the prior estimate.
            gain: float = variance / (variance + self.OBSERVATION_VARIANCE)
            mean += gain * (a["rating"] - mean)
            variance *= 1 - gain
            prev_season = season

        return mean, variance
