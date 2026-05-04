"""
MatchRatingsService - match rating orchestration and scoring utilities.

This module defines `MatchRatingsService`, a UI-agnostic analytics service that
normalizes raw match performance data, applies positional weighting rules, and
translates standardized performance signals into 0-10 match ratings.

Responsibilities:
- Normalize performance metrics to match length and per-90 rates.
- Apply Bayesian smoothing for small-sample stability.
- Compute Z-scores against positional means/standard deviations.
- Apply position-specific floors, caps, bonuses, and penalties.
- Convert adjusted Z-scores to 0-10 ratings with contextual match scalars.

The service focuses on rating calculation and context-aware modifiers; data
loading, persistence, and UI presentation are handled elsewhere.
"""

import logging
from typing import cast

import numpy as np

from src.contracts.backend import (
    MatchOverviewPayload,
    MatchStatsPayload,
    PerformanceMeansStdsMap,
    PerformanceWeightsMap,
    PlayerPerformancePayload,
)

logger = logging.getLogger(__name__)


class MatchRatingsService:
    """Provide match rating calculations for goalkeepers and outfield players.

    MatchRatingsService ingests raw performance payloads and match context,
    then applies normalization, smoothing, weighting, and position-specific
    heuristics to produce final 0-10 ratings.
    """

    H_BASE = 10.0
    DUMMY_MINUTES = 30.0

    def __init__(
        self,
        weights: PerformanceWeightsMap,
        means_stds: PerformanceMeansStdsMap,
    ):
        """Initialize the MatchRatingsService with calculation configurations.

        This sets the weighting scheme and normalization benchmarks used to convert
        raw performance data into match ratings.

        Args:
            weights (PerformanceWeightsMap): Mapping of performance metrics to their
                                             relative weights in rating formulas.
            means_stds (PerformanceMeansStdsMap): Mean and standard deviation values
                                                  for supported performance types.
        """
        self.weights = weights
        self.means_stds = means_stds

    def calculate_gk_rating(
        self,
        performance: PlayerPerformancePayload,
        match_overview: MatchOverviewPayload,
        half_length: int,
        team_name: str,
    ) -> float:
        """Calculate a goalkeepers match rating on a 0-10 scale.

        The rating reflects shot-stopping, goals conceded context, penalties, and
        overall match difficulty. The method normalizes raw performance metrics to
        match length, derives a heuristic score, and then adjusts it with contextual
        floors, bonuses, and a supremacy scalar before mapping to the final rating.

        Args:
            performance (PlayerPerformancePayload): The raw performance metrics for the
                                                    goalkeeper in the match
            match_overview (MatchOverviewPayload): High-level match data including xG
                                                   and team statistics.
            half_length (int): Length of each half in in-game minutes used to
                               normalize volume stats.
            team_name (str): Name of the goalkeeper's team to contextualize
                             stats and xG.

        Returns:
            float: The calculated goalkeepers match rating on a 0-10 scale.
        """
        # Placeholder implementation
        is_user_home = match_overview.get("home_team_name") == team_name
        if is_user_home:
            user_stats = cast(MatchStatsPayload, match_overview.get("home_stats", {}))
            opponent_stats = cast(
                MatchStatsPayload, match_overview.get("away_stats", {})
            )
        else:
            user_stats = cast(MatchStatsPayload, match_overview.get("away_stats", {}))
            opponent_stats = cast(
                MatchStatsPayload, match_overview.get("home_stats", {})
            )

        team_xg: float = user_stats.get("xg", 0)
        xg_against: float = opponent_stats.get("xg", 0)

        # Remove the performance_type and player_id keys for weight application
        performance_metrics: dict[str, object] = {
            k: v
            for k, v in performance.items()
            if k not in ["performance_type", "player_id"]
        }
        # Ensure all values are numeric, replace non-numeric with 0
        normalized_metrics: dict[str, float] = {
            k: v if isinstance(v, (int, float)) else 0
            for k, v in performance_metrics.items()
        }

        # Normalize to 10-minute-half units; thresholds are tuned to this scale.
        # Apply formula: metric = metric * (H_BASE / half_length)
        # for every metric in vol_cols
        time_scalar = self.H_BASE / half_length
        team_xg *= time_scalar
        xg_against *= time_scalar

        vol_cols = [
            "shots_against",
            "shots_on_target",
            "saves",
            "goals_conceded",
        ]
        for k in normalized_metrics:
            normalized_metrics[k] = (
                normalized_metrics[k] * time_scalar
                if k in vol_cols
                else normalized_metrics[k]
            )

        goals_conceded: float = normalized_metrics.get("goals_conceded", 0)

        xgp: float = xg_against - goals_conceded
        saves: float = normalized_metrics.get("saves", 0)
        save_success_rate: float = normalized_metrics.get("save_success_rate", 0)
        shots_against: float = normalized_metrics.get("shots_against", 0)
        shots_on_target: float = normalized_metrics.get("shots_on_target", 0)
        penalty_saves = normalized_metrics.get("penalty_saves", 0)
        penalty_goals_conceded = normalized_metrics.get("penalty_goals_conceded", 0)
        shoot_out_saves = normalized_metrics.get("shoot_out_saves", 0)
        shoot_out_goals_conceded = normalized_metrics.get("shoot_out_goals_conceded", 0)

        gk_heuristic: float = (xgp * 1.5) + (
            np.log(saves + 1) * (save_success_rate / 100.0)
        )
        gk_means_stds = cast(dict[str, float], self.means_stds.get("GK", {}))
        gk_mean: float = gk_means_stds.get("mean", 0.0)
        gk_std: float = gk_means_stds.get("std", 1.0)  # Avoid division by zero
        raw_score: float = (gk_heuristic - gk_mean) / gk_std if gk_std > 0 else 0

        # ---------------------------------------------------------
        # 1. Adjustments expressed with explicit conditionals
        # ---------------------------------------------------------
        raw_score = self._apply_gk_explicit_adjustments(
            raw_score=raw_score,
            shots_on_target=shots_on_target,
            goals_conceded=goals_conceded,
            xgp=xgp,
        )
        # ---------------------------------------------------------
        # 2. Low-Volume Forgiveness (The Match 69 Fix)
        # ---------------------------------------------------------
        raw_score = self._apply_gk_low_volume_forgiveness(
            raw_score=raw_score,
            shots_against=shots_against,
            goals_conceded=goals_conceded,
        )
        raw_score = self._apply_gk_final_floor(raw_score=raw_score)
        # ---------------------------------------------------------
        # 3. Additive Bonuses (Penalties & Reliable Shifts)
        # ---------------------------------------------------------
        raw_score = self._apply_gk_additive_bonuses(
            raw_score=raw_score,
            penalty_saves=penalty_saves,
            shoot_out_saves=shoot_out_saves,
            goals_conceded=goals_conceded,
            xgp=xgp,
            save_success_rate=save_success_rate,
        )
        # ---------------------------------------------------------
        # 4. Inverted Clean Sheet Bonuses (use nested conditionals)
        # ---------------------------------------------------------
        clean_sheet: bool = (
            (goals_conceded == 0)
            and (penalty_goals_conceded == 0)
            and (shoot_out_goals_conceded == 0)
        )
        if clean_sheet:
            raw_score = self._apply_gk_clean_sheet_bonuses(
                raw_score=raw_score,
                xg_against=xg_against,
                xgp=xgp,
                saves=saves,
            )
        # ---------------------------------------------------------
        # Match Supremacy Scalar
        # ---------------------------------------------------------
        supremacy_scalar: float = self._calculate_match_supremacy_scalar(
            team_xg=team_xg,
            xg_against=xg_against,
        )
        # ---------------------------------------------------------
        # Inverse sigmoid transformation to convert Z-Score to a 0-10 scale
        # ---------------------------------------------------------
        raw_rating: float = self._apply_sigmoid_transformation(raw_score=raw_score)

        # Apply supremacy scalar
        final_rating: float = raw_rating - supremacy_scalar

        # Fix the final rating to be between 0 and 10
        final_rating: float = max(0.0, min(10.0, final_rating))
        return round(final_rating, 1)

    def _apply_gk_explicit_adjustments(
        self,
        raw_score: float,
        shots_on_target: float,
        goals_conceded: float,
        xgp: float,
    ) -> float:
        """Apply explicit conditional adjustments to the raw goalkeeper score.

        This method encapsulates the logic for applying specific floors and bonuses
        based on match context, such as the "Spectator Exemption" for zero shots on
        target or the "1-Goal Narrow Miss" adjustment. It ensures that these
        adjustments are applied in a clear and maintainable way, separate from the
        core heuristic calculation.

        Args:
            raw_score (float): The initial raw score calculated from the heuristic.
            shots_on_target (float): The number of shots on target faced by the GK.
            goals_conceded (float): The number of goals conceded by the GK.
            xgp (float): The expected goals prevented by the GK.
            shots_against (float): The total number of shots faced by the GK.

        Returns:
            float: The adjusted raw score after applying explicit conditionals.
        """
        # A. Spectator Exemption
        if (shots_on_target == 0) and (goals_conceded == 0):
            return 0.0

        # B. The 1-Goal Narrow Miss — floor at -0.15
        if (goals_conceded == 1) and (xgp >= -0.25) and (raw_score < -0.15):
            return -0.15

        # C. Positive Impact Anchor — floor at 0.0
        if (xgp >= 0) and (goals_conceded <= 2) and (raw_score < 0.0):
            return 0.0

        # D. The Shootout Victim — floor at -0.35
        if (goals_conceded >= 3) and (xgp >= -0.50) and (raw_score < -0.35):
            return -0.35

        return raw_score

    def _apply_gk_low_volume_forgiveness(
        self,
        raw_score: float,
        shots_against: float,
        goals_conceded: float,
    ) -> float:
        """Apply low-volume forgiveness adjustments to the raw goalkeeper score.

        This method implements the "Match 69 Fix" and related adjustments that provide
        forgiveness for goalkeepers who face very few shots or concede few goals, which
        can lead to disproportionately low ratings due to small sample sizes. The
        adjustments set minimum floors for the raw score based on specific thresholds of
        shots against and goals conceded.

        Args:
            raw_score (float): The initial raw score calculated from the heuristic.
            shots_against (float): The total number of shots faced by the GK.
            goals_conceded (float): The number of goals conceded by the GK.
        Returns:
            float: The adjusted raw score after applying low-volume forgiveness.
        """
        # A. Match 69 Fix: If faced <=3 shots and conceded <=1 goal, floor at -0.5
        if (shots_against <= 3) and (goals_conceded <= 1) and (raw_score < -0.5):
            return -0.5

        # B. If conceded <=2 goals, floor at -0.8
        if (goals_conceded <= 2) and (raw_score < -0.8):
            return -0.8

        # C. If conceded 3 goals, floor at -0.95
        return -0.95 if (goals_conceded == 3) and (raw_score < -0.95) else raw_score

    def _apply_gk_final_floor(self, raw_score: float) -> float:
        """Apply a final floor to the raw goalkeeper score.

        This method ensures that after all adjustments, the raw score does not fall
        below a certain threshold, which prevents extreme negative ratings in very
        poor performance contexts.

        Args:
            raw_score (float): The raw score after all previous adjustments.

        Returns:
            float: The final adjusted raw score with a floor applied.
        """
        return max(raw_score, -1.25)

    def _apply_gk_additive_bonuses(
        self,
        raw_score: float,
        penalty_saves: float,
        shoot_out_saves: float,
        goals_conceded: float,
        xgp: float,
        save_success_rate: float,
    ) -> float:
        """Apply additive bonuses to the raw goalkeeper score.

        This method calculates and applies bonuses for penalty saves, shootout saves,
        and reliable shifts. It adds a fixed bonus for each penalty save and shootout
        save, and an additional bonus for reliable shifts based on specific performance
        criteria.

        Args:
            raw_score (float): The raw score after all previous adjustments.
            penalty_saves (float): The number of penalty saves made by the GK.
            shoot_out_saves (float): The number of shootout saves made by the GK.
            goals_conceded (float): The number of goals conceded by the GK.
            xgp (float): The expected goals prevented by the GK.
            save_success_rate (float): The save success rate percentage of the GK.
        Returns:
            float: The final adjusted raw score after applying additive bonuses.
        """
        # A. Penalty Heroics (asymmetric bonus)
        total_penalty_saves: float = penalty_saves + shoot_out_saves
        raw_score += total_penalty_saves * 0.5  # Each penalty save adds 0.5 to Z-Score

        # B. Reliable shift bonus
        if (goals_conceded == 1) and (xgp > 0.0) and (save_success_rate >= 80):
            raw_score += 0.25

        return raw_score

    def _apply_gk_clean_sheet_bonuses(
        self,
        raw_score: float,
        xg_against: float,
        xgp: float,
        saves: float,
    ) -> float:
        """Apply inverted clean sheet bonuses to the raw goalkeeper score.

        This method implements a nuanced bonus system for clean sheets, where the
        bonus amount is determined by the quality of the defensive performance. It
        provides a higher bonus for clean sheets achieved against stronger attacking
        performances (higher xG against) and a lower bonus for clean sheets against
        weaker attacks.

        Args:
            raw_score (float): The raw score after all previous adjustments.
            xg_against (float): The expected goals against the GK.
            xgp (float): The expected goals prevented by the GK.
            saves (float): The total number of saves made by the GK.
        Returns:
            float: The final adjusted raw score after applying clean sheet bonuses.
        """
        # 1. Passenger: Low threat, keeper didn't have to do much
        if xg_against <= 1.0 and xgp < 0.95:
            return raw_score + 0.30

        # 2. Bailout: High threat, keeper made a ton of saves
        elif xg_against > 2.0 and saves >= 5:
            return raw_score + 0.80

        # 3. Standard: Any other clean sheet scenario
        else:
            return raw_score + 0.50

    def _calculate_match_supremacy_scalar(
        self,
        team_xg: float,
        xg_against: float,
    ) -> float:
        """Calculate the match supremacy scalar based on team xG and opponent xG.

        This method computes a scalar that adjusts the goalkeeper's rating based on the
        relative quality of the attacking performance of their own team compared to the
        opponent. It uses a logarithmic function to determine the scalar, which is then
        capped to prevent excessive adjustments.

        Args:
            team_xg (float): The expected goals for the goalkeeper's team.
            xg_against (float): The expected goals against the goalkeeper's team.
        Returns:
            float: The calculated match supremacy scalar to be applied
                   to the final rating.
        """
        gamma: float = 0.2
        delta_xg: float = (team_xg + 1) / (xg_against + 1)
        supremacy_scalar: float = gamma * np.log(delta_xg)

        # Cap the scalar to a max of 0.25
        return min(supremacy_scalar, 0.25)

    def _apply_sigmoid_transformation(self, raw_score: float) -> float:
        """Apply an inverse sigmoid transformation to convert a Z-Score to a 0-10 scale.

        This method takes the final adjusted raw score (Z-Score) and maps it to a
        rating on a 0-10 scale using an inverse sigmoid function. The parameters of the
        sigmoid are chosen to ensure that a Z-Score of 0 corresponds to a rating of
        around 6.0, and that the curve provides a reasonable distribution of ratings
        across typical Z-Score ranges.

        Args:
            raw_score (float): The final adjusted raw score (Z-Score) for the GK.

        Returns:
            float: The calculated match rating on a 0-10 scale before applying the
                   supremacy scalar.
        """
        k: float = 0.85
        s_0: float = np.log(2 / 3) / k  # Z-Score corresponding to a 6.0 rating
        return 10 * (1 / (1 + np.exp(-k * (raw_score - s_0))))

    def calculate_outfield_rating(
        self,
        performance: PlayerPerformancePayload,
        match_overview: MatchOverviewPayload,
        half_length: int,
        team_name: str,
    ) -> float | None:
        """Calculate an outfield players match rating on a 0-10 scale.

        The rating reflects contribution across attacking, defensive, and possession
        actions, adjusted for position, minutes played, and match context such as team
        xG and opponent strength.

        Args:
            performance (PlayerPerformancePayload): The raw performance metrics and
                                                    positions played for the player.
            match_overview (MatchOverviewPayload): High-level match data including xG,
                                                   goals, and team statistics.
            half_length (int): Length of each half in in-game minutes used to
                               normalize cumulative statistics.
            team_name (str): Name of the player's team to correctly resolve home/away
                             context and opponent data.

        Returns:
            float | None: The calculated outfield player rating on a 0-10 scale, or
                          None if the player did not play enough minutes for a
                          reliable rating.
        """
        positions_played = performance.get("positions_played", [])
        if not positions_played:
            logger.warning(
                f"No positions played data for player {performance.get('player_id')}. "
                "Defaulting to 6.0 rating."
            )
            return 6.0
        is_user_home = match_overview.get("home_team_name") == team_name
        if is_user_home:
            user_stats = cast(MatchStatsPayload, match_overview.get("home_stats", {}))
            opponent_stats = cast(
                MatchStatsPayload, match_overview.get("away_stats", {})
            )
        else:
            user_stats = cast(MatchStatsPayload, match_overview.get("away_stats", {}))
            opponent_stats = cast(
                MatchStatsPayload, match_overview.get("home_stats", {})
            )

        team_xg: float = user_stats.get("xg", 0)
        opponent_xg: float = opponent_stats.get("xg", 0)
        opponent_goals = (
            match_overview.get("away_score", 0)
            if is_user_home
            else match_overview.get("home_score", 0)
        )
        opponent_goals = self._normalize_opponent_goals(opponent_goals)

        performance_metrics: dict[str, object] = {
            k: v
            for k, v in performance.items()
            if k not in ["performance_type", "player_id", "positions_played"]
        }
        performance_metrics: dict[str, float] = {
            k: v if isinstance(v, (int, float)) else 0
            for k, v in performance_metrics.items()
        }

        minutes_played: float = performance_metrics.get("minutes_played", 0)
        if minutes_played < 10:
            return None  # Not enough data to calculate a reliable rating

        cum_columns = [
            "goals",
            "assists",
            "shots",
            "passes",
            "dribbles",
            "tackles",
            "possession_won",
            "possession_lost",
            "fouls_committed",
            "offsides",
            "distance_covered",
            "distance_sprinted",
        ]

        # Normalize to 10-minute-half units; thresholds are tuned to this scale.
        normalized_metrics: dict[str, float] = performance_metrics.copy()
        for col in cum_columns:
            if col in normalized_metrics:
                normalized_metrics[col] = normalized_metrics[col] * (
                    self.H_BASE / half_length
                )

        calculated_ratings: list[float] = []
        for pos in positions_played:
            p90_metrics: dict[str, int | float] = self._apply_bayesian_smoothing(
                normalized_metrics=normalized_metrics,
                pos=pos,
                minutes_played=minutes_played,
            )
            # Add the raw accuracy metrics to the p90_metrics
            # dict for weight application
            perc_cols = [
                "shot_accuracy",
                "pass_accuracy",
                "dribble_success_rate",
                "tackle_success_rate",
            ]
            for col in perc_cols:
                if col in performance_metrics:
                    p90_metrics[col] = performance_metrics[col]

            xt: float = self._calculate_xt_bonus(
                pass_accuracy=performance_metrics.get("pass_accuracy", 0),
                passes_p90=p90_metrics.get("passes_p90", 0),
                distance_sprinted_p90=p90_metrics.get("distance_sprinted_p90", 0),
                distance_covered_p90=p90_metrics.get("distance_covered_p90", 0),
            )
            p90_metrics["xt_bonus_p90"] = xt

            col_names = [
                "goals_p90",
                "assists_p90",
                "shots_p90",
                "shot_accuracy",
                "passes_p90",
                "pass_accuracy",
                "dribbles_p90",
                "dribble_success_rate",
                "tackles_p90",
                "tackle_success_rate",
                "offsides_p90",
                "fouls_committed_p90",
                "possession_won_p90",
                "possession_lost_p90",
                "distance_covered_p90",
                "distance_sprinted_p90",
                "xt_bonus_p90",
            ]
            pos_weights: dict[str, float] = self.weights.get(pos, {})
            final_weights: np.ndarray = np.array(
                [pos_weights.get(col, 0) for col in col_names]
            )
            z_scores: dict[str, int | float] = self._calculate_z_scores(
                p90_metrics=p90_metrics,
                pos_means_stds=cast(
                    dict[str, dict[str, float]], self.means_stds.get(pos, {})
                ),
            )

            z_scores: dict[str, int | float] = self._apply_volume_masks(
                performance_metrics=normalized_metrics,
                z_scores=z_scores,
            )

            processed_raw_score: float = self._apply_pos_modifiers(
                z_scores=z_scores,
                pos=pos,
                opponent_goals=opponent_goals,
                opponent_xg=opponent_xg,
                final_weights=final_weights,
                performance_metrics=normalized_metrics,
                minutes_played=minutes_played,
            )
            match_supremacy_scalar: float = self._calculate_match_supremacy_scalar(
                team_xg=team_xg,
                xg_against=opponent_xg,
            )
            raw_rating: float = self._apply_sigmoid_transformation(
                raw_score=processed_raw_score
            )
            final_rating: float = raw_rating - match_supremacy_scalar
            final_rating: float = max(0.0, min(10.0, final_rating))
            calculated_ratings.append(final_rating)

        if len(calculated_ratings) == 1:
            return round(calculated_ratings[0], 1)

        r_max: float = max(calculated_ratings)
        r_mean = np.mean(calculated_ratings)

        alpha = 0.25

        hybrid_rating = r_max - (alpha * (r_max - r_mean))

        return round(max(0.0, min(10.0, hybrid_rating)), 1)

    def _apply_bayesian_smoothing(
        self, normalized_metrics: dict[str, float], pos: str, minutes_played: float
    ) -> dict[str, float]:
        """Apply Bayesian smoothing to raw metrics to calculate stable per-90 rates.

        Mitigate small-sample volatility by blending the observed rate with a
        positional prior. This uses a dummy minutes anchor (d=30). Rare stats
        use a prior of 0, while volume stats use the historical average.

        For computational efficiency, the conceptual blending formula:
        r_smoothed = [M / (M + d)] * r_obs + [d / (M + d)] * r_prior

        Is algebraically reduced to a single operation on adjusted volume (X):
        X_p90 = [(X + r_prior * (d / 90)) / (M + d)] * 90

        Args:
            normalized_metrics (dict[str, float]): Raw performance metrics that
                have already been scaled by the half-length modifier.
            pos (str): The tactical position currently being evaluated (e.g.,
                "CM", "ST"). Used to fetch the correct historical prior.
            minutes_played (float): The actual number of in-game minutes the
                player was on the pitch.

        Returns:
            dict[str, float]: A new dictionary containing the smoothed `_p90`
                metrics.
        """
        rare_cols = ["goals", "assists", "shots"]
        p90_metrics: dict[str, float] = {
            f"{col}_p90": (
                normalized_metrics[col] / (minutes_played + self.DUMMY_MINUTES)
            )
            * 90.0
            for col in rare_cols
            if col in normalized_metrics
        }
        volume_cols = [
            "passes",
            "dribbles",
            "tackles",
            "possession_won",
            "possession_lost",
            "fouls_committed",
            "offsides",
            "distance_covered",
            "distance_sprinted",
        ]
        for col in volume_cols:
            if col in normalized_metrics:
                col_stats = self.means_stds.get(pos, {}).get(
                    f"{col}_p90", {"mean": 0.0, "std": 1.0}
                )
                if isinstance(col_stats, dict):
                    league_average_p90: float = col_stats.get("mean", 0.0)
                    dummy_stat: float = league_average_p90 * (self.DUMMY_MINUTES / 90.0)
                    p90_metrics[f"{col}_p90"] = (
                        (normalized_metrics[col] + dummy_stat)
                        / (minutes_played + self.DUMMY_MINUTES)
                    ) * 90.0
        return p90_metrics

    def _calculate_xt_bonus(
        self,
        pass_accuracy: float,
        passes_p90: float,
        distance_sprinted_p90: float,
        distance_covered_p90: float,
    ) -> float:
        """Calculate an Expected Threat (xT) proxy bonus based on dynamic actions.

        This heuristically measures a player's ability to drive the ball into
        dangerous areas. It assumes players who sprint a high percentage of their
        total distance while maintaining high passing volume/accuracy are breaking
        lines and progressing the ball.

        Formula:
        xT_bonus = 0.25 * (sprint_dist / total_dist) * ln(accuracy * passes_p90 + 1)

        Args:
            pass_accuracy (float): The player's pass completion percentage
                (represented as a float, typically 0.0 to 100.0, but works
                proportionally).
            passes_p90 (float): Total passes completed per 90 minutes.
            distance_sprinted_p90 (float): Total sprint distance covered per 90.
            distance_covered_p90 (float): Total distance covered per 90.

        Returns:
            float: The calculated expected threat bonus value. Returns 0.0 if
                total distance covered is zero to prevent division by zero.
        """
        if distance_covered_p90 == 0:
            return 0.0
        return (
            0.25
            * (distance_sprinted_p90 / distance_covered_p90)
            * np.log(pass_accuracy * passes_p90 + 1)
        )

    def _calculate_z_scores(
        self,
        p90_metrics: dict[str, float],
        pos_means_stds: dict[str, dict[str, float]],
    ) -> dict[str, float]:
        """Calculate Z-scores for per-90 metrics against positional averages.

        Standardize player metrics to determine how many standard deviations
        above or below the positional mean a performance was. Crucially, this
        inverts the calculation for negative actions (e.g., fouls, offsides)
        so that a positive Z-score universally indicates a good performance.

        Standard formula: Z = (x - mean) / std
        Negative formula: Z = (mean - x) / std

        Args:
            p90_metrics (dict[str, float]): The smoothed, per-90 metrics
                calculated for the player.
            pos_means_stds (dict[str, dict[str, float]]): Reference dictionary
                containing the historical 'mean' and 'std' for each metric,
                specific to the player's tactical position.

        Returns:
            dict[str, float]: A dictionary containing the calculated Z-scores,
                with original metric keys suffixed by '_z'.
        """
        negative_stats = [
            "fouls_committed_p90",
            "possession_lost_p90",
            "offsides_p90",
        ]
        z_scores: dict[str, float] = {}
        for col, value in p90_metrics.items():
            col_stats: dict[str, float] = pos_means_stds.get(
                col, {"mean": 0.0, "std": 1.0}
            )
            if isinstance(col_stats, dict):
                mean: float = col_stats.get("mean", 0.0)
                std: float = col_stats.get("std", 1.0)
                if std == 0:
                    z_scores[f"{col}_z"] = 0.0
                elif col in negative_stats:
                    z_scores[f"{col}_z"] = (mean - value) / std
                else:
                    z_scores[f"{col}_z"] = (value - mean) / std
        return z_scores

    def _apply_volume_masks(
        self,
        performance_metrics: dict[str, float],
        z_scores: dict[str, float],
    ) -> dict[str, float]:
        volume_masks = {"passes": 5, "shots": 2, "dribbles": 3, "tackles": 2}
        volume_z_pairs = {
            "passes": "pass_accuracy_z",
            "shots": "shot_accuracy_z",
            "dribbles": "dribble_success_rate_z",
            "tackles": "tackle_success_rate_z",
        }
        for vol_col, z_col in volume_z_pairs.items():
            if performance_metrics.get(vol_col, 0) < volume_masks.get(vol_col, 0):
                z_scores[z_col] = 0.0
        return z_scores

    def _normalize_opponent_goals(self, opponent_goals: object) -> float:
        """Normalize the opponent goals value into a float.

        Args:
            opponent_goals (object): The raw representation of opponent goals, which
                may be an int, float, string, or another type.

        Returns:
            float: The opponent goal count as a float, or 0.0 if the value is not a
                numeric or string representation of a number.
        """
        if isinstance(opponent_goals, (int, float, str)):
            return float(opponent_goals)
        return 0.0

    def _apply_pos_modifiers(
        self,
        z_scores: dict[str, float],
        pos: str,
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> float:
        """Apply position-specific modifier pipelines to the raw outfield score.

        This dispatcher routes the standardized metrics through the appropriate
        positional adjustment logic so each role is evaluated according to its
        tactical responsibilities and defensive context.

        Args:
            z_scores (dict[str, float]): The per-90 Z-scores for the player's
                performance metrics.
            pos (str): The primary position code for the current rating pass
                (e.g., "CB", "CM", "ST").
            opponent_goals (int | float): The number of goals conceded by the
                player's team in the match.
            opponent_xg (float): The expected goals generated by the opponent.
            final_weights (np.ndarray): The positional weighting vector applied
                in the base dot-product score.
            performance_metrics (dict[str, float]): The raw or normalized
                counting stats for the player, used for bonus logic.
            minutes_played (float): The number of minutes the player was on the
                pitch, used to gate certain bonuses or penalties.

        Returns:
            float: The adjusted raw score after applying the position-specific
                modifier logic.
        """
        if pos == "CB":
            return self._apply_cb_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                opponent_xg=opponent_xg,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
            )
        elif pos in {"LB", "RB"}:
            return self._apply_fb_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                opponent_xg=opponent_xg,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
            )
        elif pos in {"LWB", "RWB"}:
            return self._apply_wb_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                opponent_xg=opponent_xg,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
            )
        elif pos == "CDM":
            return self._apply_cdm_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
            )
        elif pos == "CM":
            return self._apply_cm_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
            )
        elif pos == "CAM":
            return self._apply_cam_modifiers(
                z_scores=z_scores,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
            )
        elif pos in {"RM", "LM"}:
            return self._apply_wm_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
            )
        elif pos in {"RW", "LW"}:
            return self._apply_winger_modifiers(
                z_scores=z_scores,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
            )
        elif pos == "ST":
            return self._apply_st_modifiers(
                z_scores=z_scores,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
            )
        else:
            return 0.0

    def _calculate_dot_product(
        self, z_scores: dict[str, float], weights: np.ndarray
    ) -> float:
        """Calculate the weighted sum of player performance Z-scores.

        This method aligns a strictly defined, 17-element ordered list of metric
        Z-scores into a NumPy array and computes the dot product against a
        corresponding weight vector. This scalar value serves as the raw,
        unbounded mathematical foundation for our custom match rating system.

        By utilizing `np.dot`, we achieve fast, vectorized linear combinations
        while keeping the analytics engine lightweight and free of bloated
        machine learning dependencies.

        Args:
            z_scores (dict[str, float]): A dictionary containing standardized
                performance metrics. Keys are expected to match the internal
                feature list suffixed with '_z' (e.g., 'goals_p90_z').
            weights (np.ndarray): A 1D array of floats representing the tactical
                importance of each metric for a specific position. Must align
                precisely with the internal 17-element feature vector.

        Returns:
            float: The raw, weighted performance score resulting from the
                dot product of the Z-scores and positional weights.
        """
        col_names = [
            "goals_p90",
            "assists_p90",
            "shots_p90",
            "shot_accuracy",
            "passes_p90",
            "pass_accuracy",
            "dribbles_p90",
            "dribble_success_rate",
            "tackles_p90",
            "tackle_success_rate",
            "offsides_p90",
            "fouls_committed_p90",
            "possession_won_p90",
            "possession_lost_p90",
            "distance_covered_p90",
            "distance_sprinted_p90",
            "xt_bonus_p90",
        ]
        return np.dot(
            np.array([z_scores.get(f"{col}_z", 0) for col in col_names]),
            weights,
        )

    def _apply_cb_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> float:  # sourcery skip: class-extract-method
        """Apply Center Back (CB) specific scoring logic and situational bonuses.

        Philosophy:
        - Forgives low attacking volume and poor shooting efficiency (Attacking and
          Efficiency floors).
        - Caps penalties for fouls committed, acknowledging that tactical or
          professional fouls are an inherent part of the position.
        - Rewards elite ball-playing ability (exceptionally high passing volume).
        - Rewards dominant defensive displays (exceptionally high tackles and
          possession won).
        - Provides flat boosts for rare attacking contributions (goals/assists).
        - Contextually rewards clean sheets based on opponent xG and penalizes
          heavy defensive collapses (conceding 3+ goals while on the pitch).

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            opponent_goals (int | float): Total goals scored by the opposing team.
            opponent_xg (float): Expected goals (xG) generated by the opponent.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists).
            minutes_played (float): The number of minutes the player was on the pitch.

        Returns:
            float: The calculated raw match rating score for the center back.
        """
        z_scores = self._apply_attacking_floor(z_scores)

        z_scores = self._apply_efficiency_floor(z_scores)

        if z_scores.get("fouls_committed_p90_z", 0) < -2.0:
            z_scores["fouls_committed_p90_z"] = -2.0

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        raw_score += performance_metrics.get("goals", 0) * 0.6
        raw_score += performance_metrics.get("assists", 0) * 0.4

        if z_scores.get("tackles_p90_z", 0) > 2.0:
            raw_score += (z_scores["tackles_p90_z"] - 2.0) * 0.25
        if z_scores.get("possession_won_p90_z", 0) > 2.0:
            raw_score += (z_scores["possession_won_p90_z"] - 2.0) * 0.25
        if z_scores.get("passes_p90_z", 0) > 1.5:
            raw_score += (z_scores["passes_p90_z"] - 1.5) * 0.30

        raw_score = self._apply_defender_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            opponent_xg=opponent_xg,
        )
        if opponent_goals >= 3 and minutes_played >= 60:
            raw_score -= 0.3

        return raw_score

    def _apply_efficiency_floor(self, z_scores: dict[str, float]) -> dict[str, float]:
        """Apply a minimum threshold to efficiency-based performance metrics.

        Philosophy:
        - Mitigates the impact of low-volume statistical anomalies (e.g., a player
          completing 1 of 3 passes resulting in a mathematically abysmal 33% accuracy).
        - Ensures a poor success rate in isolated actions acts as a standard "bad day"
          penalty (capped at -0.75 standard deviations) rather than creating an
          unrecoverable black hole for the overall match rating.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            dict[str, float]: The updated Z-scores dictionary with efficiency
                metrics floored at -0.75.
        """
        efficiency_stats = [
            "tackle_success_rate_z",
            "pass_accuracy_z",
            "dribble_success_rate_z",
            "shot_accuracy_z",
        ]
        for col in efficiency_stats:
            if col in z_scores and z_scores[col] < -0.75:
                z_scores[col] = -0.75
        return z_scores

    def _apply_defender_clean_sheet_bonus(
        self,
        raw_score: float,
        opponent_goals: int | float,
        opponent_xg: float,
    ) -> float:
        """Calculate and apply a context-aware clean sheet bonus for defenders.

        Philosophy:
        - Rewards the ultimate defensive objective: keeping a clean sheet.
        - Scales the reward dynamically using Expected Goals (xG) to reflect true
          defensive dominance versus luck.
        - A clean sheet with low opponent xG (<= 1.0) indicates a stifling, dominant
          defensive performance, yielding the maximum bonus.
        - A clean sheet with high opponent xG (>= 2.0) suggests the defense was
          porous and relied heavily on poor opponent finishing or exceptional
          goalkeeping, yielding a minimal bonus.

        Args:
            raw_score (float): The current, pre-bonus match rating for the defender.
            opponent_goals (int | float): Total goals scored by the opposing team.
            opponent_xg (float): Expected goals (xG) generated by the opponent.

        Returns:
            float: The adjusted match rating including the contextual clean sheet bonus.
        """
        if opponent_goals == 0:
            if opponent_xg <= 1.0:
                return raw_score + 0.5
            elif opponent_xg >= 2.0:
                return raw_score + 0.15
            else:
                return raw_score + 0.35
        return raw_score

    def _apply_attacking_floor(self, z_scores: dict[str, float]) -> dict[str, float]:
        """Neutralize mathematical penalties for lack of attacking output.

        Philosophy:
        - Forgives defensive or deep-lying players (like CBs or DMs) for not
          registering shots, goals, or assists.
        - Prevents the standardized Z-score system from penalizing a player simply
          because they did not participate in the final third, effectively treating
          a lack of attacking output as a neutral baseline (0.0) rather than a negative.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            dict[str, float]: The updated Z-scores dictionary with attacking
                metrics floored at 0.0.
        """
        attacking_stats = [
            "goals_p90_z",
            "assists_p90_z",
            "shots_p90_z",
            "shot_accuracy_z",
        ]
        for stat in attacking_stats:
            if stat in z_scores and z_scores[stat] < 0:
                z_scores[stat] = 0.0
        return z_scores

    def _apply_fb_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> float:
        """Apply Fullback (FB/LB/RB) specific scoring logic and situational bonuses.

        Philosophy:
        - Forgives a lack of direct attacking output (shots/goals) and isolated
          efficiency drops.
        - Implements a "Tactical Instruction" floor: prevents severe penalties for
          low dribbling volume, Expected Threat (xT), and distance covered. This
          protects players who are tactically instructed to "Stay Back While Attacking"
          from being statistically punished for following managerial orders.
        - Caps penalties for fouls committed, recognizing that fullbacks are often
          isolated out wide and forced into professional fouls.
        - Rewards direct goal contributions, valuing assists slightly higher than
          goals to reflect the modern fullback's role as a wide creator.
        - Applies dedicated, modular bonuses for exceptional defensive solidity and
          attacking progression.
        - Contextually rewards clean sheets based on opponent xG and penalizes heavy
          defensive collapses (conceding 3+ goals while on the pitch).

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            opponent_goals (int | float): Total goals scored by the opposing team.
            opponent_xg (float): Expected goals (xG) generated by the opponent.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists).
            minutes_played (float): The number of minutes the player was on the pitch.

        Returns:
            float: The calculated raw match rating score for the fullback.
        """
        z_scores = self._apply_attacking_floor(z_scores)
        # The "Tactical Instruction" Floor
        # If the LB is told to stay back, they will have 0 dribbles, low xt,
        # and low distance. We floor these at -0.50 (a microscopic penalty) so
        # they aren't destroyed for following tactics.
        tactical_stats = [
            "dribbles_p90_z",
            "xt_bonus_p90_z",
            "distance_covered_p90_z",
            "distance_sprinted_p90_z",
        ]
        for col in tactical_stats:
            if col in z_scores and z_scores[col] < -0.50:
                z_scores[col] = -0.50

        z_scores = self._apply_efficiency_floor(z_scores)

        if z_scores.get("fouls_committed_p90_z", 0) < -1.5:
            z_scores["fouls_committed_p90_z"] = -1.5

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        raw_score += performance_metrics.get("goals", 0) * 0.4
        raw_score += performance_metrics.get("assists", 0) * 0.6

        raw_score = self._apply_defensive_fb_bonuses(
            raw_score=raw_score,
            z_scores=z_scores,
        )

        raw_score = self._apply_attacking_fb_bonuses(
            raw_score=raw_score,
            z_scores=z_scores,
        )

        raw_score = self._apply_defender_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            opponent_xg=opponent_xg,
        )
        if opponent_goals >= 3 and minutes_played >= 60:
            raw_score -= 0.3

        return raw_score

    def _apply_defensive_fb_bonuses(
        self, raw_score: float, z_scores: dict[str, float]
    ) -> float:
        """Apply situational defensive bonuses for Fullbacks.

        Philosophy:
        - Rewards the "Third CB" archetype (e.g., a tucked-in, inverted, or
          defensively-minded fullback).
        - Triggers positive modifiers only when the player registers elite
          defensive volume (tackles and possession won) that significantly
          exceeds the positional average.
        - Ensures that fullbacks who secure the flank but don't overlap are
          still recognized for dominant defensive displays.

        Args:
            raw_score (float): The current, pre-bonus match rating for the fullback.
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            float: The adjusted match rating including defensive bonuses.
        """
        # Reward Path A: The "Third CB" (For the Tucked-In LB)
        # Triggers if they dominate defensively and recycle the ball safely
        if z_scores.get("tackles_p90_z", 0) > 1.5:
            raw_score += (z_scores["tackles_p90_z"] - 1.5) * 0.15
        if z_scores.get("possession_won_p90_z", 0) > 1.5:
            raw_score += (z_scores["possession_won_p90_z"] - 1.5) * 0.15
        return raw_score

    def _apply_attacking_fb_bonuses(
        self, raw_score: float, z_scores: dict[str, float]
    ) -> float:
        """Apply situational attacking and progression bonuses for Fullbacks.

        Philosophy:
        - Rewards the "Express Train" archetype (e.g., an aggressive overlapping
          fullback or wing-back).
        - Triggers positive modifiers for elite physical exertion (distance covered
          and sprinted) coupled with high Expected Threat (xT) generation.
        - Includes a secondary "Creativity Bonus" to reward fullbacks acting as
          primary ball-progressors or wide playmakers via elite passing and
          dribbling volume.

        Args:
            raw_score (float): The current, pre-bonus match rating for the fullback.
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            float: The adjusted match rating including attacking bonuses.
        """
        # Reward Path B: The "Express Train" (For the Overlapping RB)
        # Triggers if they cover massive ground and create expected threat
        if z_scores.get("distance_covered_p90_z", 0) > 1.5:
            raw_score += (z_scores["distance_covered_p90_z"] - 1.5) * 0.10
        if z_scores.get("distance_sprinted_p90_z", 0) > 1.5:
            raw_score += (z_scores["distance_sprinted_p90_z"] - 1.5) * 0.10
        if z_scores.get("xt_bonus_p90_z", 0) > 1.5:
            raw_score += (z_scores["xt_bonus_p90_z"] - 1.5) * 0.15

        # Creativity Bonus: If they make a larger-than-expected number
        # of passes or dribbles
        if z_scores.get("passes_p90_z", 0) > 2.0:
            raw_score += (z_scores["passes_p90_z"] - 2.0) * 0.15
        if z_scores.get("dribbles_p90_z", 0) > 1.5:
            raw_score += (z_scores["dribbles_p90_z"] - 1.5) * 0.15

        return raw_score

    def _apply_wb_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
    ) -> float:
        """Apply Wingback (WB/LWB/RWB) specific scoring logic and situational bonuses.

        Philosophy:
        - Forgives a lack of direct attacking output (shots/goals) and isolated
          efficiency drops.
        - Implements an "Active Detriment Cap": Punishes bad turnovers and fouls,
          but stops the free-fall at -1.5 standard deviations to prevent a few bad
          decisions from mathematically ruining an otherwise decent performance.
        - Implements a "Passenger Cap": Floors volume-based penalties at -1.0. If
          the tactical flow of the match bypasses their flank, they are treated as
          uninvolved rather than an active threat to the team.
        - Heavily rewards direct goal contributions, valuing assists (0.8) higher
          than goals (0.6) to reflect their primary role as wide playmakers.
        - Applies scaling bonuses for elite physical exertion (distance covered
          and sprinted) and ball progression (Expected Threat).
        - Applies a flat synergy bonus if the wingback registers above-average
          output in both tackles and possession won, rewarding elite two-way play.
        - Contextually rewards clean sheets based on opponent xG.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            opponent_goals (int | float): Total goals scored by the opposing team.
            opponent_xg (float): Expected goals (xG) generated by the opponent.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists).

        Returns:
            float: The calculated raw match rating score for the wingback.
        """
        z_scores = self._apply_attacking_floor(z_scores)

        z_scores = self._apply_efficiency_floor(z_scores)

        # The Active Detriment Cap
        # Punishes them for bad turnovers/fouls, but stops the free-fall at -1.5
        detriment_stats = ["fouls_committed_p90_z", "possession_lost_p90_z"]
        for col in detriment_stats:
            if col in z_scores and z_scores[col] < -1.5:
                z_scores[col] = -1.5

        # The Passenger Cap (Volume Floors)
        # Volume stats measure involvement. If they are a passenger, cap the
        # penalty at -1.0 so they aren't mathematically treated as an
        # active threat to the team.
        passenger_stats = [
            "passes_p90_z",
            "dribbles_p90_z",
            "tackles_p90_z",
            "possession_won_p90_z",
            "distance_covered_p90_z",
            "distance_sprinted_p90_z",
            "xt_bonus_p90_z",
        ]
        for col in passenger_stats:
            if col in z_scores and z_scores[col] < -1.0:
                z_scores[col] = -1.0

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        raw_score += performance_metrics.get("goals", 0) * 0.6
        raw_score += performance_metrics.get("assists", 0) * 0.8

        if z_scores.get("distance_covered_p90_z", 0) > 1.5:
            raw_score += (z_scores["distance_covered_p90_z"] - 1.5) * 0.15
        if z_scores.get("distance_sprinted_p90_z", 0) > 1.5:
            raw_score += (z_scores["distance_sprinted_p90_z"] - 1.5) * 0.15
        if z_scores.get("xt_bonus_p90_z", 0) > 1.5:
            raw_score += (z_scores["xt_bonus_p90_z"] - 1.5) * 0.20

        if (z_scores.get("tackles_p90_z", 0) > 1.0) and (
            z_scores.get("possession_won_p90_z", 0) > 1.0
        ):
            raw_score += 0.35

        return self._apply_defender_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            opponent_xg=opponent_xg,
        )

    def _apply_cdm_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> float:
        """Apply Central Defensive Midfielder (CDM) specific scoring logic and bonuses.

        Philosophy:
        - Implements a "Do No Harm" attacking floor, forgiving CDMs for lacking
          shots, goals, or assists, as their primary role lies deeper.
        - Applies an efficiency floor to prevent isolated statistical anomalies from
          derailing the rating.
        - Caps the penalty for fouls committed (-1.0 Z-score). This acknowledges
          the "dark arts" of the position, where tactical and professional fouls
          are often necessary to break up counter-attacks.
        - Rewards rare attacking contributions, valuing goals slightly higher than
          assists for deep-lying players.
        - Applies elite scaling bonuses for "Defensive Dominance" (exceptionally
          high tackles and possession won) and "Passing Prowess" (acting as the
          team's metronome with incredibly high pass volume).
        - Rewards perfect ball retention (zero possession lost) and effective
          defensive shielding (zero opponent goals) for players completing the
          majority of the match (60+ minutes).

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            opponent_goals (int | float): Total goals scored by the opposing team.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists, possession lost).
            minutes_played (float): The number of minutes the player was on the pitch.

        Returns:
            float: The calculated raw match rating score for the defensive midfielder.
        """
        # The "Do No Harm" Attacking Floor for CDMs
        z_scores = self._apply_attacking_floor(z_scores)

        z_scores = self._apply_efficiency_floor(z_scores)

        if z_scores.get("fouls_committed_p90_z", 0) < -1.0:
            z_scores["fouls_committed_p90_z"] = -1.0

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        raw_score += performance_metrics.get("goals", 0) * 0.5
        raw_score += performance_metrics.get("assists", 0) * 0.4

        # Defensive Dominance
        if z_scores.get("tackles_p90_z", 0) > 2.0:
            raw_score += (z_scores["tackles_p90_z"] - 2.0) * 0.25
        if z_scores.get("possession_won_p90_z", 0) > 2.0:
            raw_score += (z_scores["possession_won_p90_z"] - 2.0) * 0.25

        # Passing Prowess
        if z_scores.get("passes_p90_z", 0) > 2.0:
            raw_score += (z_scores["passes_p90_z"] - 2.0) * 0.35

        if minutes_played >= 60:
            if performance_metrics.get("possession_lost") == 0:
                raw_score += 0.20

            if opponent_goals == 0:
                raw_score += 0.20

        return raw_score

    def _apply_cm_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> float:
        """Apply Central Midfielder (CM) specific scoring logic and situational bonuses.

        Philosophy:
        - Implements attacking and efficiency floors, acknowledging that a CM's role
          can be highly variable (e.g., deep-lying playmaker vs. shuttler) and
          forgiving a lack of direct goal contributions.
        - Caps the standardized impact of goals and assists at 1.5 standard deviations.
          This prevents mathematical inflation from anomalous per-90 metrics, replacing
          it with a reliable, flat scalar reward for direct goal contributions.
        - Values goals (0.8) slightly higher than assists (0.6)
          for flat performance rewards.
        - Rewards the "Complete Midfielder" (Box-to-Box) with scaling bonuses for
          registering elite volume (> 2.0 Z-score) across various disciplines.
        - Heavily weights elite ball-winning (possession won) and distribution (passes),
          reflecting the primary objectives of central midfield:
          win the ball and keep it.
        - Applies a contextual clean sheet bonus for contributing to a solid overall
          defensive structure.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            opponent_goals (int | float): Total goals scored by the opposing team.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists).
            minutes_played (float): The number of minutes the player was on the pitch.

        Returns:
            float: The calculated raw match rating score for the central midfielder.
        """
        z_scores = self._apply_attacking_floor(z_scores)

        z_scores = self._apply_efficiency_floor(z_scores)

        # Cap goals and assists at 1.5
        if z_scores.get("goals_p90_z", 0) > 1.5:
            z_scores["goals_p90_z"] = 1.5
        if z_scores.get("assists_p90_z", 0) > 1.5:
            z_scores["assists_p90_z"] = 1.5

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        if performance_metrics.get("goals", 0) > 0:
            raw_score += performance_metrics.get("goals", 0) * 0.8
        if performance_metrics.get("assists", 0) > 0:
            raw_score += performance_metrics.get("assists", 0) * 0.6

        if z_scores.get("tackles_p90_z", 0) > 2.0:
            raw_score += (z_scores["tackles_p90_z"] - 2.0) * 0.20
        if z_scores.get("possession_won_p90_z", 0) > 2.0:
            raw_score += (z_scores["possession_won_p90_z"] - 2.0) * 0.40
        if z_scores.get("passes_p90_z", 0) > 2.0:
            raw_score += (z_scores["passes_p90_z"] - 2.0) * 0.40
        if z_scores.get("dribbles_p90_z", 0) > 2.0:
            raw_score += (z_scores["dribbles_p90_z"] - 2.0) * 0.20

        return self._apply_cm_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            minutes_played=minutes_played,
        )

    def _apply_cm_clean_sheet_bonus(
        self,
        raw_score: float,
        opponent_goals: int | float,
        minutes_played: float,
    ) -> float:
        """Apply a contextual clean sheet bonus for central midfielders.

        Philosophy:
        - Central and Defensive Midfielders act as the first line of the defensive
          block. If the team secures a clean sheet, it strongly implies the midfield
          effectively screened the backline and controlled transition spaces.
        - Rewards the player with a flat +0.15 bump if the opponent scores zero
          goals, provided the player was on the pitch long enough (60+ minutes)
          to have meaningfully contributed to the defensive effort.

        Args:
            raw_score (float): The current, pre-bonus match rating for the midfielder.
            opponent_goals (int | float): Total goals scored by the opposing team.
            minutes_played (float): The number of minutes the player was on the pitch.

        Returns:
            float: The adjusted match rating including the clean
                   sheet bonus (if applicable).
        """
        if (opponent_goals == 0) and (minutes_played >= 60):
            raw_score += 0.15
        return raw_score

    def _apply_cam_modifiers(
        self,
        z_scores: dict[str, float],
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
    ) -> float:
        """Apply Central Attacking Midfielder (CAM) specific scoring logic and bonuses.

        Philosophy:
        - Applies a robust suite of floors (defensive, efficiency, detriment, and
          passenger) to account for the unique, often polarizing nature of a pure
          playmaker, forgiving them for a lack of defensive output provided they
          are actively involved in the attack.
        - Caps goal and assist Z-scores at 2.0. This is a higher ceiling than central
          midfielders, reflecting their advanced role,
          but still controls extreme variance.
        - Values assists (0.9) higher than goals (0.7) for flat performance metrics,
          cementing their role as the primary creative hub.
        - "Maestro Bonus": Rewards high passing volume combined with elite expected
          threat (xT) generation.
        - "Shadow Striker Bonus": Provides a scaling reward for high shot volume.
        - "Risky Creator Bonus": Rewards players who maintain high overall pass accuracy
          despite high possession lost, indicating progressive, line-breaking intent.
        - "Modern 10 Bonus": A massive flat reward (+0.50) for advanced playmakers
          who successfully contribute to a high press (tackles and possession won).

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists).

        Returns:
            float: The calculated raw match rating score for the attacking midfielder.
        """
        z_scores = self._apply_defensive_floor(z_scores)

        z_scores = self._apply_efficiency_floor(z_scores)

        z_scores = self._apply_detriment_floor(z_scores)

        z_scores = self._apply_passenger_floors(z_scores)

        # Cap goals and assists at 2.0
        if z_scores.get("goals_p90_z", 0) > 2.0:
            z_scores["goals_p90_z"] = 2.0
        if z_scores.get("assists_p90_z", 0) > 2.0:
            z_scores["assists_p90_z"] = 2.0

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        raw_score += performance_metrics.get("goals", 0) * 0.7
        raw_score += performance_metrics.get("assists", 0) * 0.9

        if (z_scores.get("passes_p90_z", 0) > 1.0) and (
            z_scores.get("xt_bonus_p90_z", 0) > 1.5
        ):
            raw_score += 0.40
        if z_scores.get("shots_p90_z", 0) > 1.5:
            raw_score += (z_scores["shots_p90_z"] - 1.5) * 0.10
        if (z_scores.get("pass_accuracy_z", 0) > 1.0) and (
            z_scores.get("possession_lost_p90_z", 0) > 1.0
        ):
            raw_score += 0.15
        if (z_scores.get("tackles_p90_z", 0) > 1.0) and (
            z_scores.get("possession_won_p90_z", 0) > 1.0
        ):
            raw_score += 0.50

        return raw_score

    def _apply_defensive_floor(self, z_scores: dict[str, float]) -> dict[str, float]:
        """Apply a floor to defensive metrics to prevent harsh penalties.

        Philosophy:
        - Central Attacking Midfielders (CAMs) are primarily creative players.
        - They should not be severely punished for failing to register high
          defensive outputs (e.g., tackles or possession won).
        - Caps negative variance for defensive stats at -0.5 standard deviations.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            dict[str, float]: The modified Z-scores dictionary
                              with defensive floors applied.
        """
        defensive_exemptions = [
            "tackles_p90_z",
            "tackle_success_rate_z",
            "possession_won_p90_z",
        ]
        for stat in defensive_exemptions:
            if stat in z_scores and z_scores[stat] < -0.5:
                z_scores[stat] = -0.5
        return z_scores

    def _apply_passenger_floors(self, z_scores: dict[str, float]) -> dict[str, float]:
        """Apply a floor to involvement metrics to limit 'passenger' penalties.

        Philosophy:
        - While a CAM must be involved in the game, punishing them infinitely for
          low volume in specific matches can skew ratings unfairly (e.g., in games
          where the team is heavily out-possessed and defending deep).
        - Caps the negative variance for involvement/volume stats at -1.0 standard
          deviations.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            dict[str, float]: The modified Z-scores dictionary
                              with passenger floors applied.
        """
        passenger_stats = [
            "passes_p90_z",
            "dribbles_p90_z",
            "shots_p90_z",
            "distance_covered_p90_z",
            "distance_sprinted_p90_z",
            "xt_bonus_p90_z",
        ]
        for col in passenger_stats:
            if col in z_scores and z_scores[col] < -1.0:
                z_scores[col] = -1.0
        return z_scores

    def _apply_detriment_floor(self, z_scores: dict[str, float]) -> dict[str, float]:
        """Apply a floor to detrimental metrics to forgive calculated risks.

        Philosophy:
        - A true playmaker is expected to attempt high-risk, high-reward plays.
        - Consequently, they will lose possession or drift offside more frequently
          than safer, deeper players.
        - Caps the penalty for these detrimental stats at -1.5 standard deviations,
          preventing a creative player from being statistically ruined by simply
          trying to pick the lock.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            dict[str, float]: The modified Z-scores dictionary
                              with detriment floors applied.
        """
        detriment_stats = [
            "fouls_committed_p90_z",
            "possession_lost_p90_z",
            "offsides_p90_z",
        ]
        for col in detriment_stats:
            if col in z_scores and z_scores[col] < -1.5:
                z_scores[col] = -1.5
        return z_scores

    def _apply_wm_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> float:
        """Apply Wide Midfielder (RM/LM) specific scoring logic and bonuses.

        Philosophy:
        - Wide Midfielders are the engines of the flanks, expected to contribute
          in both phases of play.
        - Forgives a lack of direct goalscoring (via attacking floor) to account for
          deeper, more traditional wide roles.
        - Values assists (0.8) slightly higher than goals (0.6) to reflect their
          role as wide creators and crossers.
        - "Two-Way Engine Bonus": Rewards high passing volume combined with high
          tackling output, perfectly capturing the quintessential
          box-to-box wide player.
        - "Wide Progression Bonus": Provides a scaling reward for elite expected
          threat (xT) generation, highlighting players who consistently drive the
          team up the pitch.
        - Reuses the Central Midfielder clean sheet bonus, as traditional wide
          midfielders are vital to maintaining the team's defensive shape in a
          low or mid block.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            opponent_goals (int | float): Total goals scored by the opposing team.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized
                                                    performance metrics.
            minutes_played (float): The number of minutes the player was on the pitch.

        Returns:
            float: The calculated raw match rating score for the wide midfielder.
        """
        attacking_stats = [
            "goals_p90_z",
            "assists_p90_z",
            "shots_p90_z",
            "shot_accuracy_z",
        ]
        for stat in attacking_stats:
            if stat in z_scores and z_scores[stat] < -0.5:
                z_scores[stat] = -0.5

        z_scores = self._apply_efficiency_floor(z_scores)
        z_scores = self._apply_detriment_floor(z_scores)
        z_scores = self._apply_passenger_floors(z_scores)

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        if performance_metrics.get("goals", 0) > 0:
            raw_score += performance_metrics.get("goals", 0) * 0.6
        if performance_metrics.get("assists", 0) > 0:
            raw_score += performance_metrics.get("assists", 0) * 0.8

        if (z_scores.get("passes_p90_z", 0) > 1.0) and (
            z_scores.get("tackles_p90_z", 0) > 1.0
        ):
            raw_score += 0.40
        if z_scores.get("xt_bonus_p90_z", 0) > 1.5:
            raw_score += (z_scores["xt_bonus_p90_z"] - 1.5) * 0.15

        return self._apply_cm_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            minutes_played=minutes_played,
        )

    def _apply_winger_modifiers(
        self,
        z_scores: dict[str, float],
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
    ) -> float:
        """Apply Winger (LW/RW) specific scoring logic, bonuses, and penalties.

        Philosophy:
        - Evaluates the player as a modern inside-forward or direct attacking threat,
          emphasizing direct goalscoring (0.8 multiplier) over pure creation (0.6).
        - Grants tactical forgiveness for offsides (capped at -2.0 standard deviations),
          recognizing that playing on the shoulder of the defense and making runs in
          behind is a core positional requirement.
        - "Elite Outlier Bonuses": Grants scaling rewards for
          statistically extraordinary
          performances (> 2.0 Z-score) in dribbling, expected threat (xT), and passing,
          highlighting players who single-handedly dismantle defenses.
        - "High Press Bonus": Rewards wingers who actively win the ball back high up
          the pitch (tackles > 1.5 Z-score).
        - "Wastefulness Penalty": Actively punishes "selfish winger syndrome" by
          reducing the score if the player takes 3 or more shots in a match
          without registering a goal.

        Args:
            z_scores (dict[str, float]): Dictionary containing standardized
                                         per-90 metrics.
            final_weights (np.ndarray): The base positional weights used for the dot
                                        product calculation.
            performance_metrics (dict[str, float]): Dictionary of raw, unstandardized
                                                    performance metrics for the match
                                                    (e.g., goals, assists, shots).

        Returns:
            float: The final calculated raw match rating score for the winger.
        """
        z_scores = self._apply_defensive_floor(z_scores)
        z_scores = self._apply_efficiency_floor(z_scores)

        if z_scores.get("fouls_committed_p90_z", 0) < -1.5:
            z_scores["fouls_committed_p90_z"] = -1.5
        if z_scores.get("offsides_p90_z", 0) < -2.0:
            z_scores["offsides_p90_z"] = -2.0

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )
        raw_score += performance_metrics.get("goals", 0) * 0.8
        raw_score += performance_metrics.get("assists", 0) * 0.6

        if z_scores.get("dribbles_p90_z", 0) > 2.0:
            raw_score += (z_scores["dribbles_p90_z"] - 2.0) * 0.25
        if z_scores.get("xt_bonus_p90_z", 0) > 2.0:
            raw_score += (z_scores["xt_bonus_p90_z"] - 2.0) * 0.20
        if z_scores.get("passes_p90_z", 0) > 2.0:
            raw_score += (z_scores["passes_p90_z"] - 2.0) * 0.20
        if z_scores.get("tackles_p90_z", 0) > 1.5:
            raw_score += (z_scores["tackles_p90_z"] - 1.5) * 0.10

        if (performance_metrics.get("shots", 0) >= 3) and (
            performance_metrics.get("goals", 0) == 0
        ):
            raw_score -= (performance_metrics.get("shots", 0) - 2) * 0.10

        return raw_score

    def _apply_st_modifiers(
        self,
        z_scores: dict[str, float],
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
    ) -> float:
        """Apply Striker specific scoring logic, bonuses, and penalties.

        Philosophy:
        - Evaluates the player as the focal point of the attack, applying the highest
          premium in the engine for direct goalscoring (1.2 multiplier).
        - "Ghosting Forgiveness": Caps negative variance for goals, assists, and shots
          at -2.0 standard deviations. Strikers are heavily reliant on service; they
          should not be mathematically ruined for isolated
          matches where the team is dominated.
        - "Offside Forgiveness": Grants a generous detriment floor for offsides (-1.5),
          as playing on the shoulder of the last defender is a
          core positional requirement.
        - "Complete Forward Bonuses": Rewards statistically extraordinary passing and
          dribbling (> 2.0 Z-score) to highlight elite deep-lying
          forwards or complete number 9s.
        - Integrates specific sub-routines to reward target man play (hold-up bonus),
          and punish offensive possession drains (black hole penalty) or poor conversion
          rates (wasteful finisher penalty).

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            final_weights (np.ndarray): The base positional weights
                                        for dot product calculation.
            performance_metrics (dict[str, float]): Raw, unstandardized
                                                    performance metrics.

        Returns:
            float: The calculated raw match rating score for the striker.
        """
        z_scores = self._apply_defensive_floor(z_scores)
        z_scores = self._apply_efficiency_floor(z_scores)

        ghosting_stats = ["goals_p90_z", "assists_p90_z", "shots_p90_z"]
        for stat in ghosting_stats:
            if stat in z_scores and z_scores[stat] < -2.0:
                z_scores[stat] = -2.0

        if z_scores.get("offsides_p90_z", 0) < -1.5:
            z_scores["offsides_p90_z"] = -1.5

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        raw_score += performance_metrics.get("goals", 0) * 1.2
        raw_score += performance_metrics.get("assists", 0) * 0.6

        if z_scores.get("passes_p90_z", 0) > 2.0:
            raw_score += (z_scores["passes_p90_z"] - 2.0) * 0.20
        if z_scores.get("dribbles_p90_z", 0) > 2.0:
            raw_score += (z_scores["dribbles_p90_z"] - 2.0) * 0.20

        raw_score = self._apply_st_black_hole_penalty(
            raw_score=raw_score,
            performance_metrics=performance_metrics,
        )
        raw_score = self._apply_st_hold_up_bonus(
            raw_score=raw_score,
            performance_metrics=performance_metrics,
        )

        raw_score = self._apply_st_wasteful_finisher_penalty(
            raw_score=raw_score,
            performance_metrics=performance_metrics,
        )

        return raw_score

    def _apply_st_black_hole_penalty(
        self,
        raw_score: float,
        performance_metrics: dict[str, float],
    ) -> float:
        """Apply a penalty for strikers who consistently turn over possession.

        Philosophy:
        - Punishes the "black hole" striker who demands the ball but frequently
          loses it without generating positive involvements (passes, dribbles, shots).
        - Triggers only if the player loses possession excessively (> 4) and their
          turnover ratio (losses per positive involvement) is critically high (> 1.5).
        - The penalty scales linearly with excess losses but is strictly capped at 0.6.

        Args:
            raw_score (float): The current calculated match rating.
            performance_metrics (dict[str, float]): Raw, unstandardized
                                                    performance metrics.

        Returns:
            float: The modified match rating after applying the penalty.
        """
        positive_involvements = (
            performance_metrics.get("passes", 0)
            + performance_metrics.get("dribbles", 0)
            + performance_metrics.get("shots", 0)
        )
        safe_positive_involvements = max(
            positive_involvements, 1
        )  # Avoid division by zero

        turnover_ratio = (
            performance_metrics.get("possession_lost", 0) / safe_positive_involvements
        )

        if performance_metrics.get("possession_lost", 0) > 4 and turnover_ratio > 1.5:
            excess_losses = max(
                0,
                performance_metrics.get("possession_lost", 0) - positive_involvements,
            )
            black_hole_penalty = excess_losses * 0.08
            # cap penalty at 0.6
            black_hole_penalty = min(black_hole_penalty, 0.6)
            raw_score -= black_hole_penalty

        return raw_score

    def _apply_st_hold_up_bonus(
        self,
        raw_score: float,
        performance_metrics: dict[str, float],
    ) -> float:
        """Apply a bonus for strikers who excel at holding up the ball.

        Philosophy:
        - Rewards the "target man" or complete forward who absorbs pressure and
          retains the ball efficiently to bring teammates into play.
        - Triggers for highly active players (>= 15 positive involvements) who
          maintain an excellent retention ratio (> 4.0 positive involvements per loss).
        - The bonus scales with retention efficiency but is capped at 0.4.

        Args:
            raw_score (float): The current calculated match rating.
            performance_metrics (dict[str, float]): Raw, unstandardized
                                                    performance metrics.

        Returns:
            float: The modified match rating after applying the bonus.
        """
        positive_involvements = (
            performance_metrics.get("passes", 0)
            + performance_metrics.get("dribbles", 0)
            + performance_metrics.get("shots", 0)
        )
        safe_losses = max(
            performance_metrics.get("possession_lost", 0), 1
        )  # Avoid division by zero
        if (positive_involvements >= 15) and (
            (positive_involvements / safe_losses) > 4.0
        ):
            normal_expected_touches = (
                performance_metrics.get("possession_lost", 0) * 3.0
            )
            excess_retention = max(0, positive_involvements - normal_expected_touches)
            hold_up_bonus = excess_retention * 0.02
            # cap the hold-up bonus at 0.4
            hold_up_bonus = min(hold_up_bonus, 0.4)
            raw_score += hold_up_bonus

        return raw_score

    def _apply_st_wasteful_finisher_penalty(
        self,
        raw_score: float,
        performance_metrics: dict[str, float],
    ) -> float:
        """Apply a penalty for poor shot conversion.

        Philosophy:
        - Evaluates finishing efficiency by assigning a flat 0.20 Expected Goals (xG)
          value per shot.
        - Punishes strikers who take a high volume of shots (> 3) but significantly
          underperform their estimated xG (finishing deficit > 0.75).
        - The penalty scales with the deficit but is capped at 0.8.

        Args:
            raw_score (float): The current calculated match rating.
            performance_metrics (dict[str, float]): Raw, unstandardized
                                                    performance metrics.

        Returns:
            float: The modified match rating after applying the penalty.
        """
        estimated_xg = performance_metrics.get("shots", 0) * 0.20
        finishing_deficit = estimated_xg - performance_metrics.get("goals", 0)
        if (performance_metrics.get("shots", 0) > 3) and (finishing_deficit > 0.75):
            wasteful_penalty = finishing_deficit * 0.25
            # cap the wasteful finisher penalty at 0.8
            wasteful_penalty = min(wasteful_penalty, 0.8)
            raw_score -= wasteful_penalty

        return raw_score
