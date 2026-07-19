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
from types import MappingProxyType
from typing import Final, cast

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

    H_BASE: Final[float] = 10.0
    # Vectorized Bayesian Anchors (d) based on metric stabilization rates
    DUMMY_WEIGHTS: Final = MappingProxyType(
        {
            # High-Frequency (Fast stabilization)
            "passes": 15.0,
            "distance_covered": 15.0,
            "distance_sprinted": 15.0,
            "possession_won": 15.0,
            "possession_lost": 15.0,
            # Medium-Frequency (Moderate stabilization)
            "dribbles": 30.0,
            "tackles": 30.0,
            "fouls_committed": 30.0,
            "offsides": 30.0,
            # Low-Frequency / Rare Events (Slow stabilization, high volatility)
            "goals": 45.0,
            "assists": 45.0,
            "shots": 45.0,
        }
    )
    DEFAULT_DUMMY: Final[float] = 30.0
    # Shot volume at which the GK confidence shrink factor reaches 1.0 (no shrinkage).
    # Below this threshold, raw_score is scaled toward 0 by √(shots_against / K).
    GK_SHOTS_CONFIDENCE_K: Final[float] = 5.0

    # Dynamic xT Multipliers based on positional progression responsibility
    XT_POSITION_SCALARS: Final = MappingProxyType(
        {
            "ST": 0.35,
            "RW": 0.35,
            "LW": 0.35,
            "CAM": 0.35,
            "CF": 0.35,
            "CM": 0.25,
            "RM": 0.25,
            "LM": 0.25,
            "RWB": 0.25,
            "LWB": 0.25,
            "RB": 0.25,
            "LB": 0.25,
            "CDM": 0.10,
            "CB": 0.10,
        }
    )

    # Crude per-shot xG estimate; shared by goal bonus and wasteful-finisher penalty.
    XG_PER_SHOT: Final[float] = 0.20
    # Minimum fraction of a goal that always counts toward the bonus,
    # preventing a high shot volume from erasing the reward for scoring.
    GOAL_FLOOR_RATE: Final[float] = 0.40

    # Multi-position hybrid parameters.
    # ALPHA_BASE scales cosine similarity into the drag coefficient alpha.
    # VERSATILITY_THRESHOLD is the minimum r_min (worst positional rating) required
    # for a versatility bonus to fire; 6.5 is the logistic midpoint + half a point,
    # meaning the player must be above average at every listed position.
    # VERSATILITY_BETA controls the magnitude of the bonus per rating point above
    # the threshold.
    ALPHA_BASE: Final[float] = 0.50
    VERSATILITY_THRESHOLD: Final[float] = 6.5
    VERSATILITY_BETA: Final[float] = 0.15

    # Lateral mirror pairs: both sides describe the same tactical role.
    # When a player is listed at both sides, only the higher-rated is kept.
    MIRROR_PAIRS: Final[tuple[frozenset, ...]] = (
        frozenset({"LB", "RB"}),
        frozenset({"LWB", "RWB"}),
        frozenset({"LM", "RM"}),
        frozenset({"LW", "RW"}),
    )

    # Ordered stat columns used to build positional similarity profiles.
    _PROFILE_COLS: Final[tuple[str, ...]] = (
        "goals_p90",
        "assists_p90",
        "non_goal_shots_p90",
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
    )

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
        self.weights: PerformanceWeightsMap = weights
        self.means_stds: PerformanceMeansStdsMap = means_stds
        self._profile_global_mean, self._profile_global_std = self._build_profile_norms(
            means_stds
        )
        logger.info(
            "MatchRatingsService configured (weights=%d, means_stds=%d).",
            len(weights),
            len(means_stds),
        )

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
        logger.debug(
            "Calculating GK rating (player_id=%s, team=%s, half_length=%s).",
            performance.get("player_id"),
            team_name,
            half_length,
        )
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
        time_scalar: float = self.H_BASE / half_length
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
        penalty_saves: float = normalized_metrics.get("penalty_saves", 0)
        penalty_goals_conceded: float = normalized_metrics.get(
            "penalty_goals_conceded", 0
        )
        shoot_out_saves: float = normalized_metrics.get("shoot_out_saves", 0)
        shoot_out_goals_conceded: float = normalized_metrics.get(
            "shoot_out_goals_conceded", 0
        )

        gk_heuristic: float = (xgp * 1.5) + (
            np.log(saves + 1) * (save_success_rate / 100.0)
        )
        gk_means_stds: dict[str, int | float] = cast(
            dict[str, float], self.means_stds.get("GK", {})
        )
        gk_mean: float = gk_means_stds.get("mean", 0.0)
        gk_std: float = gk_means_stds.get("std", 1.0)  # Avoid division by zero
        raw_score: float = (gk_heuristic - gk_mean) / gk_std if gk_std > 0 else 0

        # ---------------------------------------------------------
        # 1. Low-Volume Confidence Shrinkage
        # ---------------------------------------------------------
        raw_score: float = self._apply_gk_volume_shrinkage(
            raw_score=raw_score,
            shots_against=shots_against,
            xgp=xgp,
            gk_std=gk_std,
        )
        raw_score: float = self._apply_gk_final_floor(raw_score=raw_score)
        # ---------------------------------------------------------
        # 2. Additive Bonuses (Penalties & Reliable Shifts)
        # ---------------------------------------------------------
        raw_score: float = self._apply_gk_additive_bonuses(
            raw_score=raw_score,
            penalty_saves=penalty_saves,
            shoot_out_saves=shoot_out_saves,
            goals_conceded=goals_conceded,
            xgp=xgp,
            save_success_rate=save_success_rate,
        )
        # ---------------------------------------------------------
        # 3. Inverted Clean Sheet Bonuses (use nested conditionals)
        # ---------------------------------------------------------
        clean_sheet: bool = (
            (goals_conceded == 0)
            and (penalty_goals_conceded == 0)
            and (shoot_out_goals_conceded == 0)
        )
        if clean_sheet:
            raw_score: float = self._apply_gk_clean_sheet_bonuses(
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
        logger.debug(
            (
                "GK rating computed (player_id=%s, raw_score=%.3f, "
                "raw_rating=%.2f, supremacy=%.2f, final=%.1f)."
            ),
            performance.get("player_id"),
            raw_score,
            raw_rating,
            supremacy_scalar,
            final_rating,
        )
        return round(final_rating, 1)

    def _apply_gk_volume_shrinkage(
        self,
        raw_score: float,
        shots_against: float,
        xgp: float,
        gk_std: float,
    ) -> float:
        """Shrink the raw GK score toward the xgp-only baseline when shot volume is low.

        At low shot volume the save term is unreliable, so raw_score is blended
        toward the xgp-only signal rather than toward 0. This prevents the
        calibrated mean (which incorporates expected save contributions) from
        dragging positive-xgp performances below neutral when saves are sparse.

        At shots_against = 0 the anchor is xgp * 1.5 / std, which is non-negative
        for any positive xgp (handling the spectator case naturally). At or above
        GK_SHOTS_CONFIDENCE_K normalised shots the factor reaches 1.0 and
        raw_score passes through unchanged.

        Args:
            raw_score (float): The z-scored GK heuristic.
            shots_against (float): Normalised total shots faced (scaled to
                10-minute-half units by the caller).
            xgp (float): Expected goals prevented (xg_against - goals_conceded).
            gk_std (float): Standard deviation used to z-score the heuristic.

        Returns:
            float: The shrunk raw score, regressed toward the xgp-only baseline.
        """
        shrink: float = min(1.0, np.sqrt(shots_against / self.GK_SHOTS_CONFIDENCE_K))
        xgp_anchor: float = (xgp * 1.5) / gk_std if gk_std > 0 else 0.0
        return xgp_anchor * (1 - shrink) + raw_score * shrink

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

        This method computes a scalar that adjusts a player's rating based on the
        relative quality of the attacking performance of their own team compared to the
        opponent. It uses a logarithmic function to determine the scalar, which is then
        bounded by both a cap (dominant team deduction) and a floor (siege bonus).

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

        # Deduction capped at 0.25 (dominant team); siege bonus floored at -0.35
        return max(min(supremacy_scalar, 0.25), -0.35)

    def _apply_sigmoid_transformation(self, raw_score: float) -> float:
        """Apply an inverse sigmoid transformation to convert a Z-Score to a 0-10 scale.

        This method takes the final adjusted raw score (Z-Score) and maps it to a
        rating on a 0-10 scale using an inverse sigmoid function. The parameters of the
        sigmoid are chosen to ensure that a Z-Score of 0 corresponds to a rating of
        around 6.0, and that the curve provides a reasonable distribution of ratings
        across typical Z-Score ranges.

        Args:
            raw_score (float): The final adjusted raw score (Z-Score).

        Returns:
            float: The calculated match rating on a 0-10 scale before applying the
                   supremacy scalar.
        """
        k = 0.85 if raw_score >= 0 else 0.45
        s_0: float = np.log(2 / 3) / k  # Z-Score corresponding to a 6.0 rating
        return 10 * (1 / (1 + np.exp(-k * (raw_score - s_0))))

    def _collapse_mirror_positions(
        self,
        positions: list[str],
        ratings: list[float],
    ) -> tuple[list[str], list[float]]:
        """Deduplicate lateral mirror-pair listings, keeping the higher-rated side.

        LB/RB, LWB/RWB, LM/RM, and LW/RW describe the same tactical role on
        opposite flanks. When both sides appear, the lower-rated entry is dropped
        so that bilateral listings don't inflate the position count or distort the
        hybrid calculation.

        Args:
            positions: Position keys for each evaluated rating.
            ratings:   Corresponding positional ratings, aligned by index.

        Returns:
            Filtered (positions, ratings) with at most one side per mirror pair.
        """
        drop: set[int] = set()
        for pair in self.MIRROR_PAIRS:
            idxs: list[int] = [i for i, p in enumerate(positions) if p in pair]
            if len(idxs) < 2:
                continue
            best: int = max(idxs, key=lambda i: ratings[i])
            drop.update(i for i in idxs if i != best)
        filtered_positions: list[str] = [
            p for i, p in enumerate(positions) if i not in drop
        ]
        filtered_ratings: list[float] = [
            r for i, r in enumerate(ratings) if i not in drop
        ]
        return filtered_positions, filtered_ratings

    def _build_profile_norms(
        self, means_stds: PerformanceMeansStdsMap
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute cross-position mean and std for each stat column.

        Used to z-score each position's mean profile so that positional similarity
        reflects deviation from the positional average rather than raw stat magnitudes.
        GK is excluded because it uses a scalar structure, not a per-stat mapping.

        Returns:
            Tuple of (global_mean, global_std) arrays aligned to _PROFILE_COLS.
        """
        outfield_means = np.array(
            [
                [
                    cast(dict[str, float], pos_data.get(col, {})).get("mean", 0.0)
                    for col in self._PROFILE_COLS
                ]
                for pos, pos_data in means_stds.items()
                if pos != "GK"
            ]
        )
        global_mean = outfield_means.mean(axis=0)
        global_std = outfield_means.std(axis=0)
        global_std[global_std == 0.0] = 1.0
        return global_mean, global_std

    def _positional_cosine_similarity(self, pos_a: str, pos_b: str) -> float:
        """Compute cosine similarity between two positions' z-score mean profiles.

        Each position is represented by its mean stat values centred and scaled
        against the cross-position distribution. This captures how each role
        deviates from the positional average, which is independent of how the
        weight vectors were constructed and avoids inflated similarity for
        base/derived pairs (e.g. RB/RWB, CM/CAM).

        Negative cosine values (anti-correlated roles such as CB/ST) are clamped
        to zero: orthogonal or opposite positions produce no drag, leaving the
        hybrid rating at r_max.

        Args:
            pos_a (str): First position key (e.g. "CB").
            pos_b (str): Second position key (e.g. "ST").

        Returns:
            float: Cosine similarity in [0, 1]. Returns 1.0 if either profile
                   is unknown (conservative: maximum drag for unrecognised roles).
        """
        ms: PerformanceMeansStdsMap = self.means_stds
        if pos_a not in ms or pos_b not in ms:
            return 1.0

        def z_profile(pos: str) -> np.ndarray:
            pos_data = ms[pos]
            raw = np.array(
                [
                    cast(dict[str, float], pos_data.get(col, {})).get("mean", 0.0)
                    for col in self._PROFILE_COLS
                ]
            )
            return (raw - self._profile_global_mean) / self._profile_global_std

        z_a = z_profile(pos_a)
        z_b = z_profile(pos_b)
        norm_a, norm_b = np.linalg.norm(z_a), np.linalg.norm(z_b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        sim = float(np.dot(z_a, z_b) / (norm_a * norm_b))
        return max(0.0, sim)

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
        logger.debug(
            "Calculating outfield rating (player_id=%s, team=%s, half_length=%s).",
            performance.get("player_id"),
            team_name,
            half_length,
        )
        positions_played = performance.get("positions_played", [])
        if not positions_played:
            logger.warning(
                f"No positions played data for player {performance.get('player_id')}. "
                "Defaulting to 6.0 rating."
            )
            return 6.0
        logger.debug("Outfield positions to evaluate: %s", positions_played)
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
            logger.debug(
                (
                    "Skipping outfield rating due to low minutes "
                    "(player_id=%s, minutes=%.1f)."
                ),
                performance.get("player_id"),
                minutes_played,
            )
            return None  # Not enough data to calculate a reliable rating

        # Remove rare events from the linear scaling block
        vol_columns = [
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

        # Normalize volume to 10-minute-half units
        normalized_metrics: dict[str, float] = performance_metrics.copy()
        for col in vol_columns:
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
                pos=pos,
                pass_accuracy=performance_metrics.get("pass_accuracy", 0),
                passes_p90=p90_metrics.get("passes_p90", 0),
                distance_sprinted_p90=p90_metrics.get("distance_sprinted_p90", 0),
                distance_covered_p90=p90_metrics.get("distance_covered_p90", 0),
                possession_won_p90=p90_metrics.get("possession_won_p90", 0),
                possession_lost_p90=p90_metrics.get("possession_lost_p90", 0),
            )
            p90_metrics["xt_bonus_p90"] = xt

            col_names = [
                "goals_p90",
                "assists_p90",
                "non_goal_shots_p90",
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

            p90_metrics["non_goal_shots_p90"] = max(
                0.0,
                p90_metrics.get("shots_p90", 0.0) - p90_metrics.get("goals_p90", 0.0),
            )

            z_scores: dict[str, int | float] = self._calculate_z_scores(
                p90_metrics=p90_metrics,
                pos_means_stds=cast(
                    dict[str, dict[str, float]], self.means_stds.get(pos, {})
                ),
                normalized_metrics=normalized_metrics,
            )

            isolation_multiplier: float = self._calculate_tactical_isolation_multiplier(
                z_scores=z_scores,
            )

            processed_raw_score, event_bonus = self._apply_pos_modifiers(
                z_scores=z_scores,
                pos=pos,
                opponent_goals=opponent_goals,
                opponent_xg=opponent_xg,
                final_weights=final_weights,
                performance_metrics=normalized_metrics,
                minutes_played=minutes_played,
                isolation_multiplier=isolation_multiplier,
            )

            match_supremacy_scalar: float = self._calculate_match_supremacy_scalar(
                team_xg=team_xg,
                xg_against=opponent_xg,
            )

            effective_minutes = min(minutes_played, 90.0)
            impact_scalar = np.sqrt(effective_minutes / 90.0)
            raw_score = (processed_raw_score * impact_scalar) + event_bonus

            raw_rating: float = self._apply_sigmoid_transformation(raw_score=raw_score)
            final_rating: float = raw_rating - match_supremacy_scalar
            final_rating: float = max(0.0, min(10.0, final_rating))
            logger.debug(
                (
                    "Position rating computed "
                    "(player_id=%s, pos=%s, raw_score=%.3f, final=%.2f)."
                ),
                performance.get("player_id"),
                pos,
                raw_score,
                final_rating,
            )
            calculated_ratings.append(final_rating)

        positions_played, calculated_ratings = self._collapse_mirror_positions(
            list(positions_played), calculated_ratings
        )

        if len(calculated_ratings) == 1:
            logger.debug(
                "Outfield rating computed (player_id=%s, final=%.1f).",
                performance.get("player_id"),
                calculated_ratings[0],
            )
            return round(calculated_ratings[0], 1)

        r_max: float = max(calculated_ratings)
        r_mean: float = float(np.mean(calculated_ratings))
        r_min: float = min(calculated_ratings)

        max_idx: int = int(np.argmax(calculated_ratings))
        max_pos: str = positions_played[max_idx]
        other_positions: list[str] = [
            p for i, p in enumerate(positions_played) if i != max_idx
        ]
        mean_similarity: float = float(
            np.mean(
                [
                    self._positional_cosine_similarity(max_pos, p)
                    for p in other_positions
                ]
            )
        )
        alpha: float = self.ALPHA_BASE * mean_similarity

        drag: float = alpha * (r_max - r_mean)
        bonus: float = self.VERSATILITY_BETA * max(
            0.0, r_min - self.VERSATILITY_THRESHOLD
        )
        hybrid_rating: float = r_max - drag + bonus

        logger.debug(
            (
                "Hybrid outfield rating computed "
                "(player_id=%s, r_max=%.2f, r_mean=%.2f, r_min=%.2f, "
                "alpha=%.3f, drag=%.3f, bonus=%.3f, final=%.2f)."
            ),
            performance.get("player_id"),
            r_max,
            r_mean,
            r_min,
            alpha,
            drag,
            bonus,
            hybrid_rating,
        )

        return round(max(0.0, min(10.0, hybrid_rating)), 1)

    def _apply_bayesian_smoothing(
        self, normalized_metrics: dict[str, float], pos: str, minutes_played: float
    ) -> dict[str, float]:
        """Apply Bayesian smoothing to raw metrics to calculate stable per-90 rates.

        Mitigate small-sample volatility by blending the observed rate with a
        positional prior. The dummy anchor (d) varies by metric: 15 for
        high-frequency stats (passes, distance), 30 for medium-frequency stats
        (tackles, dribbles), and 45 for rare events (goals, assists, shots).
        Rare stats use a prior of 0, while volume stats use the historical average.

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
        p90_metrics: dict[str, float] = {}

        # 1. Rare Events (Prior = 0.0)
        rare_cols = ["goals", "assists", "shots"]
        for col in rare_cols:
            if col in normalized_metrics:
                # Fetch specific 'd' (defaults to 45.0 based on our dictionary)
                d = self.DUMMY_WEIGHTS.get(col, self.DEFAULT_DUMMY)

                p90_metrics[f"{col}_p90"] = (
                    normalized_metrics[col] / (minutes_played + d)
                ) * 90.0

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
                # Fetch specific 'd' (e.g., 15.0 for passes, 30.0 for tackles)
                d = self.DUMMY_WEIGHTS.get(col, self.DEFAULT_DUMMY)

                col_stats = self.means_stds.get(pos, {}).get(
                    f"{col}_p90", {"mean": 0.0, "std": 1.0}
                )
                if isinstance(col_stats, dict):
                    league_average_p90: float = col_stats.get("mean", 0.0)
                    # possession_won/lost, fouls_committed, and offsides are
                    # log-transformed before their means are stored (cols_to_log in
                    # the weight notebooks). The stored mean is mean(log(x+1)),
                    # not a raw p90 rate — back-convert it.
                    if col in {
                        "possession_won",
                        "possession_lost",
                        "fouls_committed",
                        "offsides",
                    }:
                        league_average_p90 = float(np.expm1(league_average_p90))
                    # The literal anchor weight dropped onto the scales
                    dummy_stat: float = league_average_p90 * (d / 90.0)

                    p90_metrics[f"{col}_p90"] = (
                        (normalized_metrics[col] + dummy_stat) / (minutes_played + d)
                    ) * 90.0

        return p90_metrics

    def _calculate_xt_bonus(
        self,
        pos: str,
        pass_accuracy: float,
        passes_p90: float,
        distance_sprinted_p90: float,
        distance_covered_p90: float,
        possession_won_p90: float,
        possession_lost_p90: float,
    ) -> float:
        """Calculate an Expected Threat (xT) proxy bonus based on dynamic actions.

        This heuristically measures a player's ability to drive the ball into
        dangerous areas. It assumes players who sprint a high percentage of their
        total distance while maintaining high passing volume/accuracy are breaking
        lines and progressing the ball.

        The baseline proxy is dynamically dampened by a possession control ratio
        to filter out false positives from defensive recovery sprinting, and scaled
        based on the player's positional responsibility for ball progression.

        Formula:
        xT_bonus = base_scalar
                   * control_ratio
                   * (sprint / total)
                   * ln((passes * acc) + 1)

        Args:
            pos (str): The player's position (e.g., "CAM", "CB", "ST").
            pass_accuracy (float): The player's pass completion percentage.
            passes_p90 (float): Total passes completed per 90 minutes.
            distance_sprinted_p90 (float): Total sprint distance covered per 90.
            distance_covered_p90 (float): Total distance covered per 90.
            possession_won_p90 (float): Total possession won per 90 minutes.
            possession_lost_p90 (float): Total possession lost per 90 minutes.

        Returns:
            float: The calculated expected threat bonus value. Returns 0.0 if
                total distance covered is zero to prevent division by zero.
        """
        if distance_covered_p90 == 0:
            return 0.0

        base_scalar: float = self.XT_POSITION_SCALARS.get(pos, 0.25)

        # Defensive Noise Filter (Laplace Smoothed & Bounded)
        # (Won + 1) / (Lost + 1) creates a safe ratio. Capped at 2.5.
        control_ratio: float = min(
            (possession_won_p90 + 1.0) / (possession_lost_p90 + 1.0), 2.5
        )
        return (
            base_scalar
            * control_ratio
            * (distance_sprinted_p90 / distance_covered_p90)
            * float(np.log((pass_accuracy * passes_p90) + 1.0))
        )

    def _calculate_z_scores(
        self,
        p90_metrics: dict[str, float],
        pos_means_stds: dict[str, dict[str, float]],
        normalized_metrics: dict[str, float],
    ) -> dict[str, float]:
        """Convert smoothed per-90 metrics into Z-scores using historical baselines.

        Applies log-transformations (np.log1p) to right-skewed stats and continuous
        logistic volume masking to efficiency percentages to prevent step-function
        discontinuities.
        """
        negative_stats = [
            "fouls_committed_p90",
            "possession_lost_p90",
            "offsides_p90",
        ]

        # The exact columns transformed in the offline PCA pipeline
        log_transformed_stats = [
            "goals_p90",
            "assists_p90",
            "non_goal_shots_p90",
            "offsides_p90",
            "fouls_committed_p90",
            "possession_won_p90",
            "possession_lost_p90",
        ]

        # Sigmoid parameters: {"z_score_col": ("volume_col", Threshold, Lambda)}
        volume_masks = {
            "pass_accuracy_z": ("passes", 3.0, 1.1),
            "dribble_success_rate_z": ("dribbles", 2.0, 1.5),
            "shot_accuracy_z": ("shots", 1.5, 2.0),
            "tackle_success_rate_z": ("tackles", 1.5, 2.0),
        }

        z_scores: dict[str, float] = {}

        for col, value in p90_metrics.items():
            col_stats: dict[str, float] = pos_means_stds.get(
                col, {"mean": 0.0, "std": 1.0}
            )
            if isinstance(col_stats, dict):
                mean: float = col_stats.get("mean", 0.0)
                std: float = col_stats.get("std", 1.0)

                # --- 1. LOG-NORMAL COMPRESSION ---
                if col in log_transformed_stats:
                    # Compress the live value to match the log-transformed baseline
                    value = float(np.log1p(value))

                # --- 2. BASE Z-SCORE CALCULATION ---
                if std == 0.0:
                    raw_z = 0.0
                elif col in negative_stats:
                    raw_z = (mean - value) / std
                else:
                    raw_z = (value - mean) / std

                # --- 3. CONTINUOUS LOGISTIC VOLUME MASKING ---
                z_key = f"{col}_z"
                if z_key in volume_masks:
                    vol_col, threshold, lam = volume_masks[z_key]

                    # Fetch the temporally normalized volume
                    x_vol = normalized_metrics.get(vol_col, 0.0)

                    # Neutralise accuracy when volume is too low to be meaningful
                    if x_vol <= 1.0:
                        z_scores[z_key] = 0.0
                        continue

                    # W_mask = 1 / (1 + e^(-λ(X - T)))
                    w_mask = 1.0 / (1.0 + np.exp(-lam * (x_vol - threshold)))

                    # Apply the confidence weight to the Z-Score
                    z_scores[z_key] = raw_z * float(w_mask)
                else:
                    z_scores[z_key] = raw_z

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
        logger.debug(
            "Opponent goals not numeric (%r); defaulting to 0.0.", opponent_goals
        )
        return 0.0

    def _calculate_tactical_isolation_multiplier(
        self, z_scores: dict[str, float]
    ) -> float:
        """Calculate a decay multiplier for attackers who isolate themselves.

        Evaluates a player's involvement in the build-up phase (passing,
        dribbling, and work rate). If their combined build-up Z-score falls
        below a critical threshold (-1.0), it generates an exponential decay
        multiplier to throttle their semantic goal/assist bonuses.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.

        Returns:
            float: A multiplier between 0.0 and 1.0. Returns 1.0 if the player
                is sufficiently involved in the match context.
        """
        build_metrics = [
            "passes_p90_z",
            "pass_accuracy_z",
            "dribbles_p90_z",
            "dribble_success_rate_z",
            "distance_covered_p90_z",
            "distance_sprinted_p90_z",
        ]

        build_z_values = [z_scores.get(m, 0.0) for m in build_metrics if m in z_scores]

        if not build_z_values:
            return 1.0

        z_build = sum(build_z_values) / len(build_z_values)

        return float(np.exp(z_build + 1.0)) if z_build < -1.0 else 1.0

    def _apply_pos_modifiers(
        self,
        z_scores: dict[str, float],
        pos: str,
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
        isolation_multiplier: float = 1.0,
    ) -> tuple[float, float]:
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
            isolation_multiplier (float): A decay multiplier for attackers who
                isolate themselves from the build-up. Defaults to 1.0 (no decay).

        Returns:
            tuple[float, float]: (base_raw_score, event_bonus) where event_bonus
                is the goal/assist contribution kept separate so the caller can
                apply the minutes impact scalar only to the base score.
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
                minutes_played=minutes_played,
            )
        elif pos == "CDM":
            return self._apply_cdm_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
                isolation_multiplier=isolation_multiplier,
            )
        elif pos == "CM":
            return self._apply_cm_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
                isolation_multiplier=isolation_multiplier,
            )
        elif pos == "CAM":
            return self._apply_cam_modifiers(
                z_scores=z_scores,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                isolation_multiplier=isolation_multiplier,
            )
        elif pos in {"RM", "LM"}:
            return self._apply_wm_modifiers(
                z_scores=z_scores,
                opponent_goals=opponent_goals,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                minutes_played=minutes_played,
                isolation_multiplier=isolation_multiplier,
            )
        elif pos in {"RW", "LW"}:
            return self._apply_winger_modifiers(
                z_scores=z_scores,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                isolation_multiplier=isolation_multiplier,
            )
        elif pos == "ST":
            return self._apply_st_modifiers(
                z_scores=z_scores,
                final_weights=final_weights,
                performance_metrics=performance_metrics,
                isolation_multiplier=isolation_multiplier,
            )
        else:
            logger.warning(
                "Unknown position '%s' for modifiers; returning 0.0 raw score.", pos
            )
            return 0.0, 0.0

    def _apply_z_score_floors(
        self, z_scores: dict[str, float], floors: dict[str, float]
    ) -> None:
        """Apply minimum thresholds to specified Z-score metrics in-place.

        Args:
            z_scores (dict[str, float]): The Z-score dictionary to modify.
            floors (dict[str, float]): Mapping of Z-score key to its floor value.
        """
        for key, floor in floors.items():
            if key in z_scores:
                z_scores[key] = max(z_scores[key], floor)

    def _apply_mastery_bonus(
        self,
        raw_score: float,
        z_scores: dict,
        key_a: str,
        key_b: str,
        threshold: float,
        weight: float,
    ) -> float:
        """Apply a dual-skill mastery bonus.

        Rewards a player who exceeds a threshold on BOTH of two complementary skills
        simultaneously - the min() ensures genuine dual excellence rather than
        just excelling at one dimension. Used across all nine position modifiers.
        """
        mastery = min(z_scores.get(key_a, 0.0), z_scores.get(key_b, 0.0))
        if mastery > threshold:
            raw_score += (mastery - threshold) * weight
        return raw_score

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
            "non_goal_shots_p90",
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

    def _effective_goal_bonus(self, goals: float, shots: float, coeff: float) -> float:
        """Calculate a goal bonus scaled by finishing efficiency.

        Uses above-expected goals (goals minus estimated xG) so a player who
        scores the same number of goals from fewer shots is rewarded more. A
        per-goal floor ensures scoring always contributes positively regardless
        of shot volume.

        Args:
            goals (float): Goals scored in the match.
            shots (float): Total shots taken (including goals).
            coeff (float): Position-specific goal bonus coefficient.

        Returns:
            float: The goal bonus contribution to the raw score.
        """
        above_expected = max(
            goals - shots * self.XG_PER_SHOT,
            goals * self.GOAL_FLOOR_RATE,
        )
        return above_expected * coeff

    def _apply_cb_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> tuple[float, float]:  # sourcery skip: class-extract-method
        """Apply Center Back (CB) specific scoring logic and situational bonuses.

        Philosophy:
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
            tuple[float, float]: (base_raw_score, event_bonus) where event_bonus is
                the goal/assist contribution, returned separately so the caller can
                apply the minutes impact scalar only to the base score.
        """
        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=0.75,
            )
            + performance_metrics.get("assists", 0) * 0.55
        )

        # Dominant Stopper
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="tackles_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.5,
            weight=0.25,
        )

        # Ball Playing Defender
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.0,
            weight=0.20,
        )

        raw_score = self._apply_defender_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            opponent_xg=opponent_xg,
            minutes_played=minutes_played,
        )
        if opponent_goals >= 3 and minutes_played >= 60:
            raw_score -= 0.3

        return raw_score, event_bonus

    def _apply_defender_clean_sheet_bonus(
        self,
        raw_score: float,
        opponent_goals: int | float,
        opponent_xg: float,
        minutes_played: float,
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
        - If they have played less than 60 minutes, the bonus is scaled down using
          a square root function to reflect the reduced impact of their contribution.

        Args:
            raw_score (float): The current, pre-bonus match rating for the defender.
            opponent_goals (int | float): Total goals scored by the opposing team.
            opponent_xg (float): Expected goals (xG) generated by the opponent.

        Returns:
            float: The adjusted match rating including the contextual clean sheet bonus.
        """
        if opponent_goals == 0:
            minutes_confidence = np.sqrt(min(minutes_played, 60.0) / 60.0)
            if opponent_xg <= 1.0:
                bonus = 0.5
            elif opponent_xg >= 2.0:
                bonus = 0.15
            else:
                bonus = 0.35
            return raw_score + (bonus * minutes_confidence)
        return raw_score

    def _apply_fb_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> tuple[float, float]:
        """Apply Fullback (FB/LB/RB) specific scoring logic and situational bonuses.

        Philosophy:
        - Implements a "Tactical Instruction" floor: prevents severe penalties for
          low dribbling volume and Expected Threat (xT). This protects players who
          are tactically instructed to "Stay Back While Attacking" from being
          statistically punished for following managerial orders. The floor is lifted
          when the fullback is acting as a third CB (high tackles + possession won).
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
            tuple[float, float]: (base_raw_score, event_bonus) where event_bonus
                is the goal/assist contribution kept separate so the caller can
                apply the minutes impact scalar only to the base score.
        """
        third_cb_active = (
            min(
                z_scores.get("tackles_p90_z", 0.0),
                z_scores.get("possession_won_p90_z", 0.0),
            )
            > 1.0
        )
        attacking_floor = 0.0 if third_cb_active else -0.5
        self._apply_z_score_floors(
            z_scores,
            {"dribbles_p90_z": attacking_floor, "xt_bonus_p90_z": attacking_floor},
        )

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=0.5,
            )
            + performance_metrics.get("assists", 0) * 0.4
        )

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
            minutes_played=minutes_played,
        )
        if opponent_goals >= 3 and minutes_played >= 60:
            raw_score -= 0.3

        return raw_score, event_bonus

    def _apply_defensive_fb_bonuses(
        self, raw_score: float, z_scores: dict[str, float]
    ) -> float:
        """Apply situational defensive bonuses for Fullbacks.

        Philosophy:
        - Rewards the "Third CB" archetype.
        - Uses 'Bottleneck Synergy' to scalably reward mastery of the role.
        - The bonus only scales if the player simultaneously increases BOTH
          tackling and possession recovery.
        """
        return self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="tackles_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.0,
            weight=0.25,
        )

    def _apply_attacking_fb_bonuses(
        self, raw_score: float, z_scores: dict[str, float]
    ) -> float:
        """Apply situational attacking and progression bonuses for Fullbacks.

        Philosophy:
        - Rewards the "Express Train" archetype
        - Uses 'Bottleneck Synergy' to scalably reward mastery of the role.
        - Rewards the "Wide Playmaker" archetype, acknowledging that some fullbacks
          excel not through raw physicality but by being elite distributors and
          dribblers in wide areas, effectively acting as auxiliary playmakers.
        """
        # Reward Path B: The "Express Train"
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="distance_sprinted_p90_z",
            key_b="xt_bonus_p90_z",
            threshold=1.0,
            weight=0.20,
        )

        # Reward Path C: The "Wide Playmaker"
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="dribbles_p90_z",
            threshold=1.0,
            weight=0.15,
        )

        return raw_score

    def _apply_wb_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        opponent_xg: float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
    ) -> tuple[float, float]:
        """Apply Wingback (WB/LWB/RWB) specific scoring logic and situational bonuses.

        Philosophy:
        - Heavily rewards direct goal contributions, valuing assists (0.8) higher
          than goals (0.6) to reflect their primary role as wide playmakers.
        - Applies a scaling bonus for elite physical exertion (distance sprinted)
          combined with ball progression (Expected Threat) — the "Relentless Engine".
        - Applies a scaling synergy bonus for elite two-way play: high output in
          both tackles and possession won simultaneously.
        - Contextually rewards clean sheets based on opponent xG.

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            opponent_goals (int | float): Total goals scored by the opposing team.
            opponent_xg (float): Expected goals (xG) generated by the opponent.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists).

        Returns:
            tuple[float, float]: (base_raw_score, event_bonus) where event_bonus
                is the goal/assist contribution kept separate so the caller can
                apply the minutes impact scalar only to the base score.
        """
        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=0.75,
            )
            + performance_metrics.get("assists", 0) * 0.55
        )

        # Relentless Engine
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="distance_sprinted_p90_z",
            key_b="xt_bonus_p90_z",
            threshold=1.5,
            weight=0.20,
        )

        # Two-way Flank
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="tackles_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.0,
            weight=0.25,
        )

        raw_score = self._apply_defender_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            opponent_xg=opponent_xg,
            minutes_played=minutes_played,
        )
        return raw_score, event_bonus

    def _apply_cdm_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
        isolation_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        """Apply Central Defensive Midfielder (CDM) specific scoring logic and bonuses.

        Philosophy:
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
            isolation_multiplier (float): A decay multiplier for attackers who
                isolate themselves from the build-up. Defaults to 1.0 (no decay).

        Returns:
            tuple[float, float]: (base_raw_score, event_bonus) where event_bonus
                is the goal/assist contribution kept separate so the caller can
                apply the minutes impact scalar only to the base score.
        """
        self._apply_z_score_floors(z_scores, {"fouls_committed_p90_z": -1.0})

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=0.6,
            )
            + performance_metrics.get("assists", 0) * 0.45
        ) * isolation_multiplier

        # The Destroyer
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="tackles_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.5,
            weight=0.25,
        )

        # The Deep-Lying Playmaker
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="dribbles_p90_z",
            threshold=1.5,
            weight=0.25,
        )

        if minutes_played >= 60.0:
            # The Reliable Pivot (Tiered Synergy)
            poss_lost = performance_metrics.get("possession_lost", 0.0)
            pass_acc = performance_metrics.get("pass_accuracy", 0.0)
            passes_z = z_scores.get("passes_p90_z", 0.0)

            if pass_acc >= 92.0 and passes_z > 1.0:
                if poss_lost == 0.0:
                    # The "Perfect Metronome": Flawless retention at elite volume
                    raw_score += 0.35
                elif poss_lost <= 1.0:
                    # The "Reliable Shift": Elite retention at elite volume
                    raw_score += 0.20

            # Defensive Shielding
            if opponent_goals == 0:
                raw_score += 0.20

        return raw_score, event_bonus

    def _apply_cm_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
        isolation_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        """Apply Central Midfielder (CM) specific scoring logic and situational bonuses.

        Philosophy:
        - Values goals (0.8) slightly higher than assists (0.6)
          for flat performance rewards.
        - Rewards the "Complete Midfielder" (Box-to-Box) with scaling bonuses for
          registering elite volume (> 1.5 Z-score) across various disciplines.
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
            isolation_multiplier (float): A decay multiplier for attackers who
                isolate themselves from the build-up. Defaults to 1.0 (no decay).

        Returns:
            tuple[float, float]: (base_raw_score, event_bonus) where event_bonus
                is the goal/assist contribution kept separate so the caller can
                apply the minutes impact scalar only to the base score.
        """
        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=1.0,
            )
            + performance_metrics.get("assists", 0) * 0.75
        ) * isolation_multiplier

        # The Enforcer
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="tackles_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.5,
            weight=0.25,
        )

        # The Progression Engine
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="dribbles_p90_z",
            threshold=1.2,
            weight=0.25,
        )

        raw_score = self._apply_cm_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            minutes_played=minutes_played,
        )
        return raw_score, event_bonus

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
        isolation_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        """Apply Central Attacking Midfielder (CAM) specific scoring logic and bonuses.

        Philosophy:
        - Applies a robust suite of floors (defensive, efficiency, detriment, and
          passenger) to account for the unique, often polarizing nature of a pure
          playmaker, forgiving them for a lack of defensive output provided they
          are actively involved in the attack.
        - Values assists (0.9) higher than goals (0.7) for flat performance metrics,
          cementing their role as the primary creative hub.
        - "Maestro Bonus": Rewards high passing volume combined with elite expected
          threat (xT) generation.
        - "Shadow Striker Bonus": Provides a scaling reward for high shot volume
          combined with high xT.
        - "Modern 10 Bonus": Scaling reward for advanced playmakers who successfully
          contribute to a high press (tackles and possession won above 1.0 Z-score).

        Args:
            z_scores (dict[str, float]): Dictionary of standardized per-90 metrics.
            final_weights (np.ndarray): The base positional weights for dot product.
            performance_metrics (dict[str, float]): Raw, unstandardized performance
                metrics (e.g., total goals, assists).
            isolation_multiplier (float): A decay multiplier for attackers who
                isolate themselves from the build-up. Defaults to 1.0 (no decay).

        Returns:
            tuple[float, float]: (base_raw_score, event_bonus) where event_bonus
                is the goal/assist contribution kept separate so the caller can
                apply the minutes impact scalar only to the base score.
        """
        self._apply_z_score_floors(
            z_scores,
            {
                # Defensive floor: CAMs are not expected to win tackles or duels
                "tackles_p90_z": -0.5,
                "tackle_success_rate_z": -0.5,
                "possession_won_p90_z": -0.5,
                # Passenger floor: prevents infinite freefall when team defends deep
                "passes_p90_z": -1.0,
                "dribbles_p90_z": -1.0,
                "non_goal_shots_p90_z": -1.0,
                "distance_covered_p90_z": -1.0,
                "distance_sprinted_p90_z": -1.0,
                "xt_bonus_p90_z": -1.0,
                # Detriment floor: playmakers attempt high-risk passes and run in behind
                "fouls_committed_p90_z": -1.5,
                "possession_lost_p90_z": -1.5,
                "offsides_p90_z": -1.5,
            },
        )

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=0.9,
            )
            + performance_metrics.get("assists", 0) * 0.75
        ) * isolation_multiplier

        # The Maestro
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="xt_bonus_p90_z",
            threshold=1.5,
            weight=0.25,
        )

        # The Shadow Striker
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="non_goal_shots_p90_z",
            key_b="xt_bonus_p90_z",
            threshold=1.5,
            weight=0.20,
        )

        # The Modern 10
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="tackles_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.0,
            weight=0.25,
        )

        return raw_score, event_bonus

    def _apply_wm_modifiers(
        self,
        z_scores: dict[str, float],
        opponent_goals: int | float,
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        minutes_played: float,
        isolation_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        """Apply Wide Midfielder (RM/LM) specific scoring logic and bonuses.

        Philosophy:
        - Wide Midfielders are the engines of the flanks, expected to contribute
          in both phases of play.
        - Caps penalties for fouls, possession lost, and offsides at -1.5 Z-score,
          accounting for the aggressive wide role.
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
            isolation_multiplier (float): A decay multiplier for attackers who
                isolate themselves from the build-up. Defaults to 1.0 (no decay).

        Returns:
            float: The calculated raw match rating score for the wide midfielder.
        """
        self._apply_z_score_floors(
            z_scores,
            {
                "fouls_committed_p90_z": -1.5,
                "possession_lost_p90_z": -1.5,
                "offsides_p90_z": -1.5,
            },
        )

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=0.75,
            )
            + performance_metrics.get("assists", 0) * 0.55
        ) * isolation_multiplier

        # Two-Way Engine
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="tackles_p90_z",
            threshold=1.0,
            weight=0.25,
        )

        # Wide Progressor
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="xt_bonus_p90_z",
            key_b="dribbles_p90_z",
            threshold=1.0,
            weight=0.20,
        )

        raw_score = self._apply_cm_clean_sheet_bonus(
            raw_score=raw_score,
            opponent_goals=opponent_goals,
            minutes_played=minutes_played,
        )
        return raw_score, event_bonus

    def _apply_winger_modifiers(
        self,
        z_scores: dict[str, float],
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        isolation_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        """Apply Winger (LW/RW) specific scoring logic, bonuses, and penalties.

        Philosophy:
        - Evaluates the player as a modern inside-forward or direct attacking threat,
          emphasizing direct goalscoring (1.3 multiplier) with assists close behind
          (1.0).
        - Grants tactical forgiveness for offsides (capped at -2.0 standard deviations),
          recognizing that playing on the shoulder of the defense and making runs in
          behind is a core positional requirement.
        - "Elite Outlier Bonuses": Grants scaling rewards for statistically
          extraordinary performances (> 1.5 Z-score): dribbling combined with xT
          (Direct Threat) and passing combined with xT (Wide Playmaker).
        - "High Press Bonus": Rewards wingers who win the ball back high up the
          pitch (tackles and possession won both above 1.0 Z-score).
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
            isolation_multiplier (float): A decay multiplier for attackers who
                    isolate themselves from the build-up. Defaults to 1.0 (no decay).

        Returns:
            float: The final calculated raw match rating score for the winger.
        """
        self._apply_z_score_floors(
            z_scores,
            {
                # Defensive floor: wingers are primarily offensive players
                "tackles_p90_z": -0.5,
                "tackle_success_rate_z": -0.5,
                "possession_won_p90_z": -0.5,
                # Detriment floor: wingers attempt high-risk dribbles and run in behind
                "fouls_committed_p90_z": -1.5,
                "possession_lost_p90_z": -1.5,
                # Looser offsides floor — running in behind
                # is a core positional requirement
                "offsides_p90_z": -2.0,
            },
        )

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )
        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=1.3,
            )
            + performance_metrics.get("assists", 0) * 1.0
        ) * isolation_multiplier

        # The Direct Threat
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="dribbles_p90_z",
            key_b="xt_bonus_p90_z",
            threshold=1.5,
            weight=0.25,
        )

        # The Wide Playmaker
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="xt_bonus_p90_z",
            threshold=1.5,
            weight=0.20,
        )

        # The Pressing Forward
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="tackles_p90_z",
            key_b="possession_won_p90_z",
            threshold=1.0,
            weight=0.15,
        )

        # Wastefulness Penalty
        shots = performance_metrics.get("shots", 0)
        goals = performance_metrics.get("goals", 0)

        if (shots >= 3) and (goals == 0):
            raw_score -= (shots - 2) * 0.10

        return raw_score, event_bonus

    def _apply_st_modifiers(
        self,
        z_scores: dict[str, float],
        final_weights: np.ndarray,
        performance_metrics: dict[str, float],
        isolation_multiplier: float = 1.0,
    ) -> tuple[float, float]:
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
          dribbling (> 1.5 Z-score) to highlight elite deep-lying
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
            isolation_multiplier (float): A decay multiplier for attackers who
                isolate themselves from the build-up. Defaults to 1.0 (no decay).

        Returns:
            float: The calculated raw match rating score for the striker.
        """
        self._apply_z_score_floors(
            z_scores,
            {
                # Defensive floor: strikers are not expected to win duels or press hard
                "tackles_p90_z": -0.5,
                "tackle_success_rate_z": -0.5,
                "possession_won_p90_z": -0.5,
                # Ghosting forgiveness: strikers depend on service;
                # zero-chance games happen
                "goals_p90_z": -2.0,
                "assists_p90_z": -2.0,
                "non_goal_shots_p90_z": -2.0,
                # Offside forgiveness: playing on the last defender's
                # shoulder is the job
                "offsides_p90_z": -1.5,
            },
        )

        raw_score: float = self._calculate_dot_product(
            z_scores=z_scores,
            weights=final_weights,
        )

        event_bonus: float = (
            self._effective_goal_bonus(
                goals=performance_metrics.get("goals", 0),
                shots=performance_metrics.get("shots", 0),
                coeff=1.5,
            )
            + performance_metrics.get("assists", 0) * 1.1
        ) * isolation_multiplier

        # The Complete Forward
        raw_score = self._apply_mastery_bonus(
            raw_score=raw_score,
            z_scores=z_scores,
            key_a="passes_p90_z",
            key_b="dribbles_p90_z",
            threshold=1.5,
            weight=0.25,
        )

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

        return raw_score, event_bonus

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
        estimated_xg = performance_metrics.get("shots", 0) * self.XG_PER_SHOT
        finishing_deficit = estimated_xg - performance_metrics.get("goals", 0)
        if (performance_metrics.get("shots", 0) > 3) and (finishing_deficit > 0.75):
            wasteful_penalty = finishing_deficit * 0.25
            # cap the wasteful finisher penalty at 0.8
            wasteful_penalty = min(wasteful_penalty, 0.8)
            raw_score -= wasteful_penalty

        return raw_score
