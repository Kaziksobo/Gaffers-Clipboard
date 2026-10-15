"""
FormScoresService - recent-form tracking from match ratings.

This module defines `FormScoresService`, a UI-agnostic analytics service that
turns a player's chronological match ratings into an exponential moving average
(EMA) form series and a colour-ready form score.

Responsibilities:
- Build the EMA series from rated appearances, seeded at the neutral rating.
- Decay current form toward the neutral rating while a player goes unrated.
- Rescale and clamp current form into a -1 to 1 score for gradient mapping.

The service is a pure function of its inputs; data loading, ordering, absence
counting, colour mapping, and persistence are handled elsewhere.
"""

import logging
from typing import Final

from src.contracts.analytics import (
    FormPoint,
    PlayerForm,
    PlayerRatingHistory,
    RatedAppearance,
)

logger = logging.getLogger(__name__)


class FormScoresService:
    """Provide EMA-based recent-form calculations for players.

    FormScoresService ingests a player's rated appearances and absence count,
    then applies exponential smoothing, absence decay, and rescaling to produce
    a form series, a current form value, and a clamped form score.
    """

    # ── EMA smoothing ─────────────────────────────────────────────────────────────

    # Weight given to each new rating; ~5-6 match effective memory.
    ALPHA: Final[float] = 0.3

    # Midpoint of the ratings sigmoid ("completely average"). Seeds the EMA and is
    # the value form decays toward while a player goes unrated.
    PRIOR_MEAN: Final[float] = 6.0

    # Rated appearances required before a series, current value or score is shown.
    MIN_APPEARANCES: Final[int] = 3

    # ── Absence decay ─────────────────────────────────────────────────────────────

    # Fraction of the gap to PRIOR_MEAN retained per missed tracked team match.
    DECAY_PER_MISSED_MATCH: Final[float] = 0.9

    # ── Score scaling ─────────────────────────────────────────────────────────────

    # Rating points above / below PRIOR_MEAN at which the form score saturates at
    # +1 / -1. Asymmetric because ratings are right-skewed; calibrated on real
    # careers so full colour is about as rare (~1% of readings) at each end.
    FORM_SATURATION_UP: Final[float] = 2.0
    FORM_SATURATION_DOWN: Final[float] = 0.5

    def calculate_player_form(self, history: PlayerRatingHistory) -> PlayerForm:
        """Calculate a player's current form from their rated appearances.

        Builds the EMA series, applies absence decay to the final value, and
        rescales it to a -1 to 1 score. Below the minimum number of rated
        appearances the series is empty and the current value and score are None.

        Args:
            history (PlayerRatingHistory): The player's rated appearances in
                                           chronological order, plus the number
                                           of tracked matches since the last one.

        Returns:
            PlayerForm: The form series, current value, and form score.
        """
        appearances: list[RatedAppearance] = history["appearances"]
        n = len(appearances)
        k: int = history["matches_since_last_rated"]
        logger.debug(
            "Calculating form (player_id=%s, rated=%d, missed=%d).",
            history["player_id"],
            n,
            k,
        )
        if n < self.MIN_APPEARANCES:
            logger.debug(
                "Not enough appearances to calculate form (player_id=%s, rated=%d).",
                history["player_id"],
                n,
            )
            return PlayerForm(
                player_id=history["player_id"],
                player_name=history["player_name"],
                rated_count=n,
                series=[],
                current=None,
                form_score=None,
                matches_since_last_rated=k,
            )

        full_series: list[FormPoint] = self._build_ema_series(appearances)
        current_ema: float = self._apply_absence_decay(full_series[-1]["ema"], k)
        form_score: float = self._calculate_form_score(current_ema)
        full_series_trimmed: list[FormPoint] = full_series[self.MIN_APPEARANCES - 1 :]

        return PlayerForm(
            player_id=history["player_id"],
            player_name=history["player_name"],
            rated_count=n,
            series=full_series_trimmed,
            current=current_ema,
            form_score=form_score,
            matches_since_last_rated=k,
        )

    def _build_ema_series(self, appearances: list[RatedAppearance]) -> list[FormPoint]:
        """Build the EMA series across all rated appearances.

        The EMA is seeded at PRIOR_MEAN and updated once per appearance. Every
        appearance yields a point; trimming to the displayable portion is left
        to the caller.

        Args:
            appearances (list[RatedAppearance]): Rated appearances in
                                                 chronological order.

        Returns:
            list[FormPoint]: One point per appearance, each holding the EMA after
                             that appearance.
        """
        ema: float = self.PRIOR_MEAN
        series: list[FormPoint] = []
        for appearance in appearances:
            ema: float = self.ALPHA * appearance["rating"] + (1 - self.ALPHA) * ema
            series.append(
                FormPoint(
                    match_id=appearance["match_id"],
                    in_game_date=appearance["in_game_date"],
                    rating=appearance["rating"],
                    ema=ema,
                )
            )
        return series

    def _apply_absence_decay(self, ema: float, matches_since_last_rated: int) -> float:
        """Decay an EMA value toward PRIOR_MEAN for each missed team match.

        Args:
            ema (float): The EMA after the player's last rated appearance.
            matches_since_last_rated (int): Tracked team matches since that
                                            appearance.

        Returns:
            float: The decayed form value on the 0-10 rating scale.
        """
        return (
            self.PRIOR_MEAN
            + (ema - self.PRIOR_MEAN)
            * self.DECAY_PER_MISSED_MATCH**matches_since_last_rated
        )

    def _calculate_form_score(self, current: float) -> float:
        """Rescale a form value around PRIOR_MEAN and clamp it to -1 to 1.

        Gaps above and below PRIOR_MEAN use separate saturation distances, so the
        score is steeper on the downside where real ratings rarely fall far.

        Args:
            current (float): The (decayed) form value on the 0-10 rating scale.

        Returns:
            float: The form score, where -1 is the worst, 0 is exactly average,
                   and 1 is the best.
        """
        gap: float = current - self.PRIOR_MEAN
        saturation: float = (
            self.FORM_SATURATION_UP if gap >= 0 else self.FORM_SATURATION_DOWN
        )
        return max(-1.0, min(1.0, gap / saturation))
