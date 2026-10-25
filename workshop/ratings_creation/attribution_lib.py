"""Shared attribution logic for tracing the outfield match-ratings algorithm.

Both rating_attribution.ipynb (retired, in git history; interactive,
one-position-at-a-time walkthrough)
and scripts/full_attribution_report.py (full per-position report for every
position listed on a performance) import this module so the two never drift
apart.

Every bonus and penalty is captured from the service itself: the service builds each
one in a named helper (goal and assist bonus, mastery, defensive quality, fullback and
centre-midfielder style, clean sheet, collapse, wasted shots, CDM pivot, striker hold-up,
black hole and wasteful finisher) and AttributionService wraps those helpers to log the
value they return, so the itemised bonuses always sum to the service's total. The report
prints that sum next to the service total and flags any difference as UNATTRIBUTED;
tests/data/test_attribution_reconciles.py enforces it on every real performance.

Not wired up for goalkeeper performances — calculate_gk_rating() uses its own
internal methods, none of which are hooked here.
"""

from __future__ import annotations

import copy
import datetime
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.services.analytics.match_ratings_service import MatchRatingsService

NEG_STATS = {"fouls_committed_p90", "possession_lost_p90", "offsides_p90"}
LOG_STATS = {
    "goals_p90",
    "assists_p90",
    "non_goal_shots_p90",
    "offsides_p90",
    "fouls_committed_p90",
    "possession_won_p90",
    "possession_lost_p90",
}
LOG_PRIOR = {"possession_won", "possession_lost", "fouls_committed", "offsides"}

# Half-length normalisation column classes (match_ratings_service.py ~line 850-869).
# Volume stats get scaled by H_BASE/half_length; rare and rate stats pass through raw.
VOL_COLS = {
    "passes",
    "dribbles",
    "tackles",
    "possession_won",
    "possession_lost",
    "fouls_committed",
    "offsides",
    "distance_covered",
    "distance_sprinted",
}
RATE_COLS = {"shot_accuracy", "pass_accuracy", "dribble_success_rate", "tackle_success_rate"}
RARE_COLS = {"goals", "assists", "shots"}

# FB/WB dribble-forgiveness gate (match_ratings_service.py ~line 953-961):
# for RB/LB/RWB/LWB, a high dribble output floors possession_lost_p90_z so
# bombing forward isn't penalised for the possession losses that come with it.
FBWB_POS = {"RB", "LB", "RWB", "LWB"}
FBWB_DRIBBLE_THRESHOLD = 1.0
FBWB_POSS_LOST_FLOOR = -1.0

# The service's fixed 17-element stat profile, in dot-product order
# (match_ratings_service.py: calculate_outfield_rating / _calculate_dot_product).
# There is no svc._PROFILE_COLS attribute on the service - this list must be
# kept in sync with the col_names list defined in both of those places.
STAT_COLS = (
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

# Mastery archetype names by position group and the two z-scores it gates on
# (order as passed to _apply_mastery_bonus). Groups: LB/RB share FB, LWB/RWB WB,
# LM/RM WM, LW/RW Winger.
MASTERY_LABELS = {
    ("CB", "passes_p90_z", "dribbles_p90_z"): "Ball Playing Defender",
    ("CDM", "passes_p90_z", "dribbles_p90_z"): "Deep-Lying Playmaker",
    ("WB", "distance_sprinted_p90_z", "xt_bonus_p90_z"): "Relentless Engine",
    ("WB", "tackles_p90_z", "possession_won_p90_z"): "Two-Way Flank",
    ("CAM", "passes_p90_z", "xt_bonus_p90_z"): "The Maestro",
    ("CAM", "non_goal_shots_p90_z", "xt_bonus_p90_z"): "The Shadow Striker",
    ("CAM", "tackles_p90_z", "possession_won_p90_z"): "The Modern 10",
    ("WM", "passes_p90_z", "tackles_p90_z"): "Two-Way Engine",
    ("WM", "xt_bonus_p90_z", "dribbles_p90_z"): "Wide Progressor",
    ("Winger", "dribbles_p90_z", "xt_bonus_p90_z"): "The Direct Threat",
    ("Winger", "passes_p90_z", "xt_bonus_p90_z"): "The Wide Playmaker",
    ("Winger", "tackles_p90_z", "possession_won_p90_z"): "The Pressing Forward",
    ("ST", "passes_p90_z", "dribbles_p90_z"): "The Complete Forward",
}
POS_GROUP = {
    "LB": "FB", "RB": "FB", "LWB": "WB", "RWB": "WB", "LM": "WM", "RM": "WM",
    "LW": "Winger", "RW": "Winger",
}


def mastery_label(pos: str, key_a: str, key_b: str) -> str:
    """Return the archetype name for a mastery, falling back to its two z-scores."""
    group = POS_GROUP.get(pos, pos)
    return MASTERY_LABELS.get((group, key_a, key_b), f"{key_a} + {key_b}")


def load_config(project_root: Path) -> tuple[dict, dict]:
    """Load the weight vectors and positional means/stds used at inference time."""
    with open(project_root / "config" / "performance_weights.json", encoding="utf-8") as f:
        weights = json.load(f)
    with open(project_root / "config" / "performance_means_stds.json", encoding="utf-8") as f:
        means_stds = json.load(f)
    return weights, means_stds


class AttributionService(MatchRatingsService):
    """Subclass that captures every intermediate value during rating calculation.

    calculate_outfield_rating() loops once per entry in positions_played,
    reusing the same instance state each iteration. _calculate_match_supremacy_scalar
    is the last hook that fires within a given position's iteration (mirror-pair
    collapse and hybrid blending happen afterwards, across all positions, with no
    hook of their own — see compute_hybrid_blend()), so that's where each
    position's full working state is snapshotted into position_snapshots.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.attr: dict[str, Any] = {}
        self.position_snapshots: dict[str, dict[str, Any]] = {}
        self.position_order: list[str] = []

    def _apply_bayesian_smoothing(
        self, normalized_metrics: dict, pos: str, minutes_played: float
    ) -> dict:
        self.attr["normalized_metrics"] = dict(normalized_metrics)
        return super()._apply_bayesian_smoothing(normalized_metrics, pos, minutes_played)

    def _calculate_z_scores(
        self, p90_metrics: dict, pos_means_stds: dict, normalized_metrics: dict
    ) -> dict:
        # By this point the caller has already merged in the raw accuracy columns,
        # non_goal_shots_p90, and xt_bonus_p90, so this is the complete per-90
        # profile — no need to reconstruct xt_bonus_p90 from its z-score.
        self.attr["p90_metrics"] = dict(p90_metrics)
        self.attr["pos_means_stds"] = dict(pos_means_stds)
        result = super()._calculate_z_scores(p90_metrics, pos_means_stds, normalized_metrics)
        self.attr["z_scores"] = dict(result)
        return result

    def _calculate_dot_product(self, z_scores: dict, weights: np.ndarray) -> float:
        result = super()._calculate_dot_product(z_scores, weights)
        self.attr["dot_product"] = result
        self.attr["z_scores_at_dot"] = dict(z_scores)
        self.attr["weights_at_dot"] = list(weights)
        return result

    # -- bonus component capture -------------------------------------------------------
    # Each helper below wraps the service method of the same name, returns exactly what
    # the service computes, and logs it in self.attr["components"] (in call order).

    def _log_component(self, label: str, value: float, text: str) -> None:
        self.attr.setdefault("components", []).append(
            {"label": label, "value": float(value), "text": text}
        )

    def _current_pos(self) -> str:
        return self.attr.get("pre_modifier", {}).get("pos", "")

    def _calculate_goal_bonus(
        self, goals: float, pos: str, isolation_multiplier: float = 1.0
    ) -> float:
        value = super()._calculate_goal_bonus(goals, pos, isolation_multiplier)
        if goals < 1:
            text = "goals=0"
        else:
            alpha = self.GOAL_ALPHA.get(pos, 0.0)
            raw_bonus = alpha * goals**1.5 * isolation_multiplier
            cap = f"  [capped at {self.GOAL_BONUS_CAP}]" if raw_bonus > self.GOAL_BONUS_CAP else ""
            text = (
                f"alpha={alpha} x {goals:.0f}^1.5={goals**1.5:.4f} x "
                f"iso={isolation_multiplier:.3f} = {raw_bonus:.4f}{cap}"
            )
        self._log_component("Goal bonus", value, text)
        return value

    def _calculate_assist_bonus(
        self, assists: float, pos: str, isolation_multiplier: float = 1.0
    ) -> float:
        value = super()._calculate_assist_bonus(assists, pos, isolation_multiplier)
        if assists < 1:
            text = "assists=0"
        else:
            gamma = self.ASSIST_GAMMA.get(pos, 0.0)
            raw_bonus = gamma * assists**1.5 * isolation_multiplier
            cap = f"  [capped at {self.ASSIST_BONUS_CAP}]" if raw_bonus > self.ASSIST_BONUS_CAP else ""
            text = (
                f"gamma={gamma} x {assists:.0f}^1.5={assists**1.5:.4f} x "
                f"iso={isolation_multiplier:.3f} = {raw_bonus:.4f}{cap}"
            )
        self._log_component("Assist bonus", value, text)
        return value

    def _apply_mastery_bonus(
        self,
        z_scores: dict,
        key_a: str,
        key_b: str,
        threshold: float,
        impact_scalar: float,
    ) -> float:
        value = super()._apply_mastery_bonus(z_scores, key_a, key_b, threshold, impact_scalar)
        za, zb = z_scores.get(key_a, 0.0), z_scores.get(key_b, 0.0)
        mn = min(za, zb)
        excess = mn - threshold
        label = f"Mastery: {mastery_label(self._current_pos(), key_a, key_b)}"
        text = f"{key_a}={za:.3f}  {key_b}={zb:.3f}  min={mn:.3f}  threshold={threshold}"
        if excess > 0:
            cap = f" [excess capped at {self.MASTERY_EXCESS_CAP}]" if excess > self.MASTERY_EXCESS_CAP else ""
            text += (
                f"  excess={excess:.3f}{cap} x weight {self.MASTERY_WEIGHT} "
                f"x impact {impact_scalar:.3f}"
            )
        self._log_component(label, value, text)
        return value

    def _apply_defensive_quality_bonus(
        self,
        pos: str,
        z_scores: dict,
        opponent_goals: float,
        minutes_played: float,
        impact_scalar: float,
    ) -> float:
        value = super()._apply_defensive_quality_bonus(
            pos, z_scores, opponent_goals, minutes_played, impact_scalar
        )
        quality = self._defensive_quality(pos, z_scores, minutes_played)
        retention = self._defensive_retention(opponent_goals)
        weights = self.weights.get(pos, {})
        keys = self._DEF_QUALITY_STATS[pos]
        total = sum(weights.get(k.removesuffix("_z"), 0.0) for k in keys)
        avg = sum(weights.get(k.removesuffix("_z"), 0.0) * z_scores.get(k, 0.0) for k in keys) / total if total else 0.0
        text = (
            f"avg z={avg:.3f} mapped {self.DEF_QUALITY_LOW[pos]}->{self.DEF_QUALITY_HIGH[pos]} "
            f"-> Q={quality:.3f}  x impact {impact_scalar:.3f} x weight {self.DEF_QUALITY_WEIGHT} "
            f"x retention {retention:.2f} (conceded {int(opponent_goals)})"
        )
        self._log_component(f"Defensive quality bonus ({pos})", value, text)
        return value

    def _style_text(self, parts: list[tuple[str, float, float, float]], paid: str, impact: float) -> str:
        shown = "  |  ".join(
            f"{name}: Q={q:.3f} x w={w} x retention {r:.2f}" for name, q, w, r in parts
        )
        return f"{shown}  -> better style paid: {paid} (impact {impact:.3f})"

    def _apply_fb_style_bonus(
        self,
        z_scores: dict,
        opponent_goals: float,
        minutes_played: float,
        impact_scalar: float,
    ) -> float:
        value = super()._apply_fb_style_bonus(
            z_scores, opponent_goals, minutes_played, impact_scalar
        )
        parts = []
        for style, table in (
            ("Stopper", self.FB_STOPPER_RETENTION),
            ("Attacking", self.FB_ATTACKING_RETENTION),
        ):
            q = self._fb_style_quality(style, z_scores, minutes_played)
            r = self._defensive_retention(opponent_goals, table)
            parts.append((style, q, self.FB_STYLE_WEIGHT[style], r))
        paid = max(parts, key=lambda x: x[1] * x[2] * x[3])[0] if value > 0 else "none"
        self._log_component("Fullback style bonus", value, self._style_text(parts, paid, impact_scalar))
        return value

    def _apply_cm_style_bonus(
        self,
        z_scores: dict,
        opponent_goals: float,
        minutes_played: float,
        impact_scalar: float,
    ) -> float:
        value = super()._apply_cm_style_bonus(
            z_scores, opponent_goals, minutes_played, impact_scalar
        )
        parts = []
        for style, table in (
            ("BallWinner", self.CM_BALLWINNER_RETENTION),
            ("Creative", self.CM_CREATIVE_RETENTION),
        ):
            q = self._cm_style_quality(style, z_scores, minutes_played)
            r = self._defensive_retention(opponent_goals, table)
            parts.append((style, q, self.CM_STYLE_WEIGHT[style], r))
        paid = max(parts, key=lambda x: x[1] * x[2] * x[3])[0] if value > 0 else "none"
        self._log_component("CM style bonus", value, self._style_text(parts, paid, impact_scalar))
        return value

    def _clean_sheet_bonus(
        self, ratio_key: str, opponent_goals: float, opponent_xg: float, minutes_played: float
    ) -> float:
        value = super()._clean_sheet_bonus(ratio_key, opponent_goals, opponent_xg, minutes_played)
        if opponent_goals != 0:
            text = f"opponent scored {int(opponent_goals)} - no bonus"
        else:
            ramp = min(minutes_played, 60.0) / 60.0
            ratio = self.CS_RATIOS[ratio_key]
            if opponent_xg <= 1.0:
                tier_val, tier = self.CS_CB_LOW_XG, "low xG (<=1.0)"
            elif opponent_xg < 2.0:
                tier_val, tier = self.CS_CB_MID_XG, "mid xG (1.0-2.0)"
            else:
                tier_val, tier = self.CS_CB_HIGH_XG, "high xG (>=2.0)"
            text = (
                f"{tier}, xG={opponent_xg:.2f}: tier {tier_val} x ratio({ratio_key})={ratio} "
                f"x ramp={ramp:.3f}"
            )
        self._log_component("Clean sheet", value, text)
        return value

    def _collapse_penalty(
        self, opponent_goals: float, minutes_played: float, magnitude: float
    ) -> float:
        value = super()._collapse_penalty(opponent_goals, minutes_played, magnitude)
        if value:
            text = f"opp_goals={int(opponent_goals)}>=3, mins={minutes_played}>=60 -> -{magnitude}"
        else:
            text = f"needs 3+ conceded and 60+ minutes (conceded {int(opponent_goals)}, mins {minutes_played})"
        self._log_component("Collapse penalty", value, text)
        return value

    def _wasted_shots_penalty(self, performance_metrics: dict, per_shot: float) -> float:
        value = super()._wasted_shots_penalty(performance_metrics, per_shot)
        goals = performance_metrics.get("goals", 0)
        assists = performance_metrics.get("assists", 0)
        wasted = performance_metrics.get("shots", 0) - goals
        if value:
            text = f"wasted shots={wasted:.0f} (>=3) with no goal or assist: -({wasted:.0f}-2) x {per_shot}"
        else:
            text = f"needs 3+ wasted shots and no goal or assist (wasted={wasted:.0f}, goals+assists={goals + assists:.0f})"
        self._log_component("Wasted-shots penalty", value, text)
        return value

    def _cdm_pivot_bonus(self, performance_metrics: dict, minutes_played: float) -> float:
        value = super()._cdm_pivot_bonus(performance_metrics, minutes_played)
        poss_lost = performance_metrics.get("possession_lost", 0.0)
        pass_acc = performance_metrics.get("pass_accuracy", 0.0)
        raw_passes = performance_metrics.get("passes", 0.0)
        gate = (
            minutes_played >= self.CDM_PIVOT_MIN_MINUTES
            and pass_acc >= self.CDM_PIVOT_MIN_PASS_ACC
            and raw_passes >= self.CDM_PIVOT_MIN_PASSES_RAW
        )
        tier = (
            "Perfect Metronome (poss_lost==0)"
            if gate and poss_lost == 0
            else "Reliable Shift (poss_lost<=2)" if gate and poss_lost <= 2 else "no tier"
        )
        text = (
            f"gate {'OPEN' if gate else 'CLOSED'}: mins>={self.CDM_PIVOT_MIN_MINUTES} ({minutes_played}), "
            f"pass_acc>={self.CDM_PIVOT_MIN_PASS_ACC} ({pass_acc}), "
            f"passes>={self.CDM_PIVOT_MIN_PASSES_RAW} ({raw_passes:.2f}); poss_lost={poss_lost:.0f} -> {tier}"
        )
        self._log_component("CDM Reliable Pivot", value, text)
        return value

    def _st_holdup_bonus(self, performance_metrics: dict) -> float:
        value = super()._st_holdup_bonus(performance_metrics)
        inv = sum(performance_metrics.get(k, 0) for k in ("passes", "dribbles", "shots"))
        lost = performance_metrics.get("possession_lost", 0)
        ratio = inv / max(lost, 1.0)
        text = (
            f"involvement={inv:.1f} (>= {self.ST_HOLDUP_MIN_INV}), involvement/lost={ratio:.2f} "
            f"(> {self.ST_HOLDUP_MIN_RATIO}); lost={lost:.0f}"
        )
        if value:
            text += f" -> min(excess x {self.ST_HOLDUP_SCALE}, cap {self.ST_HOLDUP_CAP})"
        self._log_component("ST Hold-Up bonus", value, text)
        return value

    def _st_blackhole_penalty(self, performance_metrics: dict) -> float:
        value = super()._st_blackhole_penalty(performance_metrics)
        inv = sum(performance_metrics.get(k, 0) for k in ("passes", "dribbles", "shots"))
        lost = performance_metrics.get("possession_lost", 0)
        text = (
            f"lost={lost:.0f} (> {self.ST_BLACKHOLE_MIN_POSS_LOST}), lost/involvement="
            f"{lost / max(inv, 1.0):.2f} (> {self.ST_BLACKHOLE_MIN_RATIO})"
        )
        if value:
            text += f" -> -min(excess x {self.ST_BLACKHOLE_SCALE}, cap {self.ST_BLACKHOLE_CAP})"
        self._log_component("ST Black Hole penalty", value, text)
        return value

    def _st_wasteful_penalty(self, performance_metrics: dict, goals: float) -> float:
        value = super()._st_wasteful_penalty(performance_metrics, goals)
        shots = performance_metrics.get("shots", 0)
        est_xg = shots * self.XG_PER_SHOT
        deficit = est_xg - goals
        text = (
            f"shots={shots:.0f} (> {self.ST_WASTEFUL_MIN_SHOTS}), est xG={est_xg:.2f}, "
            f"goals={goals:.0f}, deficit={deficit:.2f} (> {self.ST_WASTEFUL_MIN_DEFICIT})"
        )
        if value:
            text += f" -> -min(deficit x {self.ST_WASTEFUL_SCALE}, cap {self.ST_WASTEFUL_CAP})"
        self._log_component("ST Wasteful Finisher penalty", value, text)
        return value

    def _apply_pos_modifiers(
        self,
        base_rating: float,
        z_scores: dict,
        pos: str,
        opponent_goals: float,
        opponent_xg: float,
        performance_metrics: dict,
        minutes_played: float,
        impact_scalar: float,
        isolation_multiplier: float = 1.0,
    ) -> float:
        self.attr["pre_modifier"] = {
            "base_rating": base_rating,
            "pos": pos,
            "opponent_goals": opponent_goals,
            "opponent_xg": round(opponent_xg, 3),
            "minutes_played": minutes_played,
            "impact_scalar": impact_scalar,
            "isolation_multiplier": round(isolation_multiplier, 4),
            "goals": performance_metrics.get("goals", 0),
            "assists": performance_metrics.get("assists", 0),
            "shots": performance_metrics.get("shots", 0),
            "passes": performance_metrics.get("passes", 0),
            "pass_accuracy": performance_metrics.get("pass_accuracy", 0),
            "possession_lost": performance_metrics.get("possession_lost", 0),
        }
        self.attr["components"] = []
        bonus = super()._apply_pos_modifiers(
            base_rating=base_rating,
            z_scores=z_scores,
            pos=pos,
            opponent_goals=opponent_goals,
            opponent_xg=opponent_xg,
            performance_metrics=performance_metrics,
            minutes_played=minutes_played,
            impact_scalar=impact_scalar,
            isolation_multiplier=isolation_multiplier,
        )
        self.attr["total_bonus"] = bonus
        return bonus

    def _calculate_tactical_isolation_multiplier(self, z_scores: dict) -> float:
        result = super()._calculate_tactical_isolation_multiplier(z_scores)
        self.attr["isolation_multiplier"] = round(result, 4)
        return result

    def _calculate_match_supremacy_scalar(self, team_xg: float, xg_against: float) -> float:
        result = super()._calculate_match_supremacy_scalar(team_xg, xg_against)
        self.attr["supremacy_scalar"] = result
        self.attr["team_xg"] = team_xg
        self.attr["xg_against"] = xg_against

        dot = self.attr.get("dot_product", 0.0)
        # Capped at 1.0 so a negative dot_product can't push the quality factor
        # above 1 and amplify the supremacy deduction past its uncapped value.
        quality_factor = max(0.0, min(1.0, 1.0 - dot / 1.5))
        pos = self.attr["pre_modifier"]["pos"]
        # CB supremacy deductions are halved: a mid CB performance in a
        # dominant match usually reflects a quiet game, not being carried.
        pos_supremacy_scalar = self.CB_SUPREMACY_SCALAR if pos == "CB" else 1.0
        adjusted_supremacy = result * quality_factor * pos_supremacy_scalar
        base_rating = self.attr["pre_modifier"]["base_rating"]
        bonus = self.attr.get("total_bonus", 0.0)
        raw_final = base_rating + bonus - adjusted_supremacy
        self.attr["quality_factor"] = quality_factor
        self.attr["pos_supremacy_scalar"] = pos_supremacy_scalar
        self.attr["adjusted_supremacy"] = adjusted_supremacy
        self.attr["raw_final_rating"] = raw_final
        self.attr["position_final_rating"] = max(0.0, min(10.0, raw_final))

        self.position_snapshots[pos] = copy.deepcopy(self.attr)
        self.position_order.append(pos)
        return result


def compute_hybrid_blend(svc: AttributionService, positions_played: list[str]) -> dict[str, Any]:
    """Replicate the service's post-loop mirror-collapse + MAZ-weighted blend.

    Mirrors match_ratings_service.MatchRatingsService._multi_position_blend.
    Reuses the service's own constants/methods (MIRROR_PAIRS via
    _collapse_mirror_positions, _mean_absolute_z, VERSATILITY_THRESHOLD,
    VERSATILITY_BETA) so the weighting scheme can't drift — only the blend
    *shape* below is duplicated and must be kept in sync if that block changes.

    Positions whose calibration best fits the player's actual stat profile
    (lowest mean-absolute-z) get the most weight, replacing the old
    cosine-similarity + drag scheme that anchored on r_max.
    """
    position_ratings = {
        p: svc.position_snapshots[p]["position_final_rating"] for p in positions_played
    }
    # z_scores_at_dot is captured post-floor (see _calculate_dot_product
    # override above), matching what the service itself feeds into
    # _multi_position_blend — position_z_scores[pos] there is the same dict
    # object, mutated in place by every floor before the dot product runs.
    position_z_scores = {
        p: svc.position_snapshots[p]["z_scores_at_dot"] for p in positions_played
    }

    collapsed_positions = svc._collapse_mirror_positions(position_ratings)

    result: dict[str, Any] = {
        "positions_played": list(positions_played),
        "ratings": [position_ratings[p] for p in positions_played],
        "collapsed_positions": collapsed_positions,
        "dropped_by_mirror": [p for p in positions_played if p not in collapsed_positions],
    }

    if len(collapsed_positions) <= 1:
        single = position_ratings[collapsed_positions[0]] if collapsed_positions else 0.0
        result.update(hybrid=False, final_rating=round(max(0.0, min(10.0, single)), 1))
        return result

    maz = {p: svc._mean_absolute_z(position_z_scores[p]) for p in collapsed_positions}
    raw_weights = {p: 1.0 / max(maz[p], 0.01) for p in collapsed_positions}
    total_w = sum(raw_weights.values())
    norm_weights = {p: raw_weights[p] / total_w for p in collapsed_positions}

    hybrid_base = sum(norm_weights[p] * position_ratings[p] for p in collapsed_positions)

    r_min = min(position_ratings[p] for p in collapsed_positions)
    versatility_bonus = svc.VERSATILITY_BETA * max(0.0, r_min - svc.VERSATILITY_THRESHOLD)
    hybrid_rating = hybrid_base + versatility_bonus

    result.update(
        hybrid=True,
        maz=maz,
        raw_weights=raw_weights,
        norm_weights=norm_weights,
        position_ratings={p: position_ratings[p] for p in collapsed_positions},
        hybrid_base=hybrid_base,
        r_min=r_min,
        versatility_bonus=versatility_bonus,
        hybrid_rating=hybrid_rating,
        final_rating=round(max(0.0, min(10.0, hybrid_rating)), 1),
    )
    return result


def run_attribution(
    weights: dict,
    means_stds: dict,
    match_data: dict,
    performance: dict,
    team_name: str,
    half_length: int,
) -> tuple[AttributionService, float | None, dict[str, Any]]:
    """Run the rating calculation once, capturing full per-position attribution.

    Returns (service, final_rating, hybrid_blend). blend is {} for GK
    performances, which this library does not trace.
    """
    svc = AttributionService(weights, means_stds)

    if performance.get("performance_type") == "GK":
        final_rating = svc.calculate_gk_rating(
            performance=performance,
            match_overview=match_data,
            half_length=half_length,
            team_name=team_name,
        )
        return svc, final_rating, {}

    final_rating = svc.calculate_outfield_rating(
        performance=performance,
        match_overview=match_data,
        half_length=half_length,
        team_name=team_name,
    )
    positions_played = performance.get("positions_played", [])
    # final_rating is None when calculate_outfield_rating bails out before the
    # per-position loop (e.g. minutes_played < 10) - no snapshots were ever
    # recorded in that case, so there's nothing to blend.
    blend = (
        compute_hybrid_blend(svc, positions_played)
        if positions_played and final_rating is not None
        else {}
    )
    return svc, final_rating, blend


def build_match_context_lines(
    match_data: dict, team_name: str, performance: dict, half_length: int
) -> list[str]:
    """Build the report header shared by every position section."""
    is_home = match_data["home_team_name"] == team_name
    team_stats = match_data["home_stats"] if is_home else match_data["away_stats"]
    opp_stats = match_data["away_stats"] if is_home else match_data["home_stats"]
    opp_goals = match_data["away_score"] if is_home else match_data["home_score"]

    lines: list[str] = []
    add = lines.append
    add("=" * 70)
    add("RATING ATTRIBUTION REPORT")
    add(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    add("=" * 70)
    add("")
    add("MATCH CONTEXT")
    add(
        f"  Match:       {match_data['home_team_name']} vs {match_data['away_team_name']}"
        f" ({match_data['home_score']}-{match_data['away_score']})"
    )
    add(f"  Competition: {match_data.get('competition', 'N/A')}")
    add(
        f"  Player:      {performance.get('player_id')}  |  "
        f"Positions: {performance.get('positions_played')}  |  "
        f"Minutes: {performance.get('minutes_played')}"
    )
    add(
        f"  Team xG:     {team_stats['xg']}   Opponent xG: {opp_stats['xg']}   "
        f"Opponent goals: {opp_goals}"
    )
    add(f"  Half length: {half_length} min")
    add("")
    return lines


def build_position_report(
    svc: AttributionService,
    snapshot: dict[str, Any],
    pos: str,
    performance: dict,
    half_length: int,
) -> list[str]:
    """Build the full step-by-step attribution report for one position.

    Mirrors every step shown interactively in the archived rating_attribution.ipynb (steps
    1-4): half-length normalisation, Bayesian smoothing (with a worked
    example), the full z-score derivation (raw z, log transform, low-volume
    masking), floors, and the dot-product contributions with a bar chart —
    not just the summarised figures.
    """
    lines: list[str] = []
    add = lines.append

    pm = snapshot["pre_modifier"]
    minutes = pm["minutes_played"]
    pos_ms = snapshot["pos_means_stds"]
    pos_weights = svc.weights.get(pos, {})
    stat_cols = list(STAT_COLS)
    p90 = snapshot["p90_metrics"]
    normalized_metrics = snapshot["normalized_metrics"]
    pre_floor = snapshot["z_scores"]
    z_scores_floored = snapshot.get("z_scores_at_dot", pre_floor)

    add("=" * 70)
    add(f"POSITION: {pos}")
    add("=" * 70)
    add("")
    add(
        f"  Minutes: {minutes}   Impact scalar: {pm['impact_scalar']:.4f}   "
        f"Isolation multiplier: {pm['isolation_multiplier']:.4f}"
    )
    add("")

    add("STEP 1: HALF-LENGTH NORMALISATION")
    time_scalar = svc.H_BASE / half_length
    add(f"  Scalar: H_BASE({svc.H_BASE}) / half_length({half_length}) = {time_scalar:.4f}")
    add("  (Goals, assists, shots: passed through raw - not half-length scaled)")
    add("  (Rate stats: passed through raw - not scaled; no possession adjustment at inference)")
    add("")
    add(f"  {'Stat':<28} {'Raw':>8} {'Type':>12} {'Normalized':>12}")
    add(f"  {'-' * 63}")
    for stat in sorted(VOL_COLS | RARE_COLS | RATE_COLS):
        raw = performance.get(stat, 0.0)
        if stat in VOL_COLS:
            stat_type = "vol x time"
        elif stat in RARE_COLS:
            stat_type = "rare (raw)"
        else:
            stat_type = "rate (raw)"
        normalized = normalized_metrics.get(stat, raw)
        add(f"  {stat:<28} {raw:>8.3f} {stat_type:>12} {normalized:>12.3f}")
    add("")

    add("STEP 2: BAYESIAN SMOOTHING -> PER-90 RATES")
    add(f"  {'Stat':<28} {'Smoothed p90':>13}")
    add(f"  {'-' * 42}")
    for stat in stat_cols:
        add(f"  {stat:<28} {p90.get(stat, 0.0):>13.4f}")
    add("")
    add("  Formula (volume stats): smoothed_p90 = (raw_count + league_avg x (d/90))")
    add("                                          / (minutes + d) x 90")
    add("  Worked examples:")
    for stat_name, raw_key in [
        ("passes_p90", "passes"),
        ("tackles_p90", "tackles"),
        ("possession_won_p90", "possession_won"),
        ("goals_p90", "goals"),
    ]:
        d = svc.DUMMY_WEIGHTS.get(raw_key, svc.DEFAULT_DUMMY)
        stored_mean = pos_ms.get(stat_name, {}).get("mean", 0.0)
        league_avg = math.expm1(stored_mean) if raw_key in LOG_PRIOR else stored_mean
        raw_count = normalized_metrics.get(raw_key, 0.0)
        smoothed = (raw_count + league_avg * (d / 90.0)) / (minutes + d) * 90.0
        add(
            f"    {stat_name:<24} raw={raw_count:.3f}  d={d}  league_avg={league_avg:.3f}  "
            f"-> {smoothed:.4f} (svc: {p90.get(stat_name, float('nan')):.4f})"
        )
    add("")

    add("STEP 3: Z-SCORES")
    add(
        f"  {'Stat':<26} {'p90 value':>10} {'log?':>5} {'mean':>8} {'std':>7} "
        f"{'raw_z':>8} {'neg?':>5} {'vol_mask':>11} {'z (pre-floor)':>14}"
    )
    add(f"  {'-' * 105}")
    for col in stat_cols:
        z_key = f"{col}_z"
        final_z = pre_floor.get(z_key, 0.0)
        p90_val = p90.get(col, 0.0)
        ms = pos_ms.get(col, {})
        mean = ms.get("mean", 0.0)
        std = ms.get("std", 1.0)
        log_flag = "y" if col in LOG_STATS else ""
        log_val = math.log1p(max(p90_val, 0)) if col in LOG_STATS else p90_val
        raw_z = (
            ((mean - log_val) / std if col in NEG_STATS else (log_val - mean) / std)
            if std > 0
            else 0.0
        )
        neg_flag = "neg" if col in NEG_STATS else ""
        mask_applied = abs(final_z - raw_z) > 0.001
        if mask_applied and abs(raw_z) > 0.001:
            mask_str = f"{final_z / raw_z:.3f}x"
        elif mask_applied:
            mask_str = "0(low vol)"
        else:
            mask_str = ""
        add(
            f"  {col:<26} {p90_val:>10.4f} {log_flag:>5} {mean:>8.4f} {std:>7.4f} "
            f"{raw_z:>8.4f} {neg_flag:>5} {mask_str:>11} {final_z:>14.4f}"
        )
    add("  (vol_mask: internal masking the service applies inside _calculate_z_scores,")
    add("   e.g. shrinking low-volume stats towards 0 - shown as a multiplier on raw_z,")
    add("   or '0(low vol)' when raw_z was suppressed entirely. Separate from the")
    add("   explicit position floors below, which are applied afterwards.)")
    add("")

    add("Z-SCORE FLOORS")
    goals_raw = performance.get("goals", 0)
    non_goal_shots_smoothed = p90.get("non_goal_shots_p90", 0.0)
    perf_eff_eligible = goals_raw >= 1 and non_goal_shots_smoothed == 0.0
    pos_floors = dict(svc.Z_SCORE_FLOORS.get(pos, {}))
    fbwb_eligible = pos in FBWB_POS
    # The service tests the dribble gate after the position floors, so read the
    # dribble z that actually reached the dot product.
    dribbles_z_pre = z_scores_floored.get("dribbles_p90_z", pre_floor.get("dribbles_p90_z", 0.0))
    fbwb_gate_open = fbwb_eligible and dribbles_z_pre > FBWB_DRIBBLE_THRESHOLD

    # Every floor the service can apply - perfect-efficiency fix, static
    # per-position floors, and the FB/WB dribble-forgiveness gate - collected
    # into one table so a reader can scan [HIT] vs [ - ] instead of having to
    # notice each row's wording differs.
    floor_rows: list[tuple[str, float, float, float, str]] = []

    if perf_eff_eligible:
        z_key = "non_goal_shots_p90_z"
        pre = pre_floor.get(z_key, 0.0)
        post = z_scores_floored.get(z_key, pre)
        floor_rows.append((z_key, 0.0, pre, post, "perfect efficiency (goals>=1, non_goal_shots==0)"))

    for stat_z, floor_val in sorted(pos_floors.items()):
        pre = pre_floor.get(stat_z, 0.0)
        post = z_scores_floored.get(stat_z, pre)
        floor_rows.append((stat_z, floor_val, pre, post, f"{pos} position floor"))

    if fbwb_eligible:
        z_key = "possession_lost_p90_z"
        pre = pre_floor.get(z_key, 0.0)
        post = z_scores_floored.get(z_key, pre)  # what the service actually used
        comparator = ">" if fbwb_gate_open else "<="
        reason = (
            f"FB/WB dribble-forgiveness gate: dribbles_p90_z={dribbles_z_pre:.4f} "
            f"{comparator} {FBWB_DRIBBLE_THRESHOLD:.2f}"
        )
        floor_rows.append((z_key, FBWB_POSS_LOST_FLOOR, pre, post, reason))

    if not floor_rows:
        add(f"  No floors defined for position '{pos}'.")
    else:
        add(f"  {'':5} {'Stat':<26} {'Floor':>7}  {'Pre':>8}  {'Post':>8}  Why")
        add(f"  {'-' * 100}")
        for z_key, floor_val, pre, post, reason in floor_rows:
            hit = post > pre + 0.0001
            tag = "[HIT]" if hit else "[ - ]"
            add(f"  {tag} {z_key:<26} {floor_val:>7.2f}  {pre:>8.4f}  {post:>8.4f}  {reason}")
        add("  ([HIT] = this floor changed the z-score; [ - ] = checked but no change needed)")
    add("")

    add("STEP 4: DOT PRODUCT CONTRIBUTIONS (sorted by absolute contribution)")
    add(f"  {'Stat':<26} {'Weight':>9} {'Z (floored)':>12} {'Fl':>3} {'Contribution':>14}  Bar")
    add(f"  {'-' * 90}")
    contribs = []
    for col in stat_cols:
        w = pos_weights.get(col, 0.0)
        z = z_scores_floored.get(f"{col}_z", 0.0)
        contribs.append((col, w, z, w * z))
    dot = snapshot["dot_product"]
    contribs.sort(key=lambda x: abs(x[3]), reverse=True)
    bar_half = 18
    max_abs = max(abs(c) for _, _, _, c in contribs) or 1.0
    for col, w, z, c in contribs:
        sign = "+" if c >= 0 else "-"
        units = int(abs(c) / max_abs * bar_half)
        pre_z = pre_floor.get(f"{col}_z", z)
        floor_marker = "F" if abs(z - pre_z) > 0.0001 else " "
        if c >= 0:
            bar = f"{'':>{bar_half}}|{'#' * units:<{bar_half}}"
        else:
            bar = f"{'#' * units:>{bar_half}}|{'':>{bar_half}}"
        add(
            f"  {col:<26} {w:>9.5f} {z:>12.4f} {floor_marker:>3} "
            f"{sign}{abs(c):>13.5f}  {bar}"
        )
    add(f"  {'-' * 90}")
    add(f"  {'DOT PRODUCT':<26} {'':>9} {'':>12} {'':>3} {dot:>+14.5f}")
    contrib_sum = sum(c for _, _, _, c in contribs)
    check = "OK" if abs(contrib_sum - dot) < 1e-9 else f"MISMATCH (itemised {contrib_sum:+.5f})"
    add(f"  Check: sum of the contributions above vs the service's dot product: {check}")
    add("  (Fl: F = a floor from the section above changed this z-score before the dot product)")
    add("")
    impact = pm["impact_scalar"]
    dot_str = "POSITIVE -> impact NOT applied" if dot >= 0 else "NEGATIVE -> impact applied"
    adjusted = dot if dot >= 0 else dot * impact
    add(f"  Impact scalar: sqrt(min({minutes},90)/90) = {impact:.4f}  [{dot_str}]")
    add(f"  Adjusted dot:  {adjusted:.5f}")
    sig = svc._apply_sigmoid_transformation(raw_score=adjusted)
    sig_check = "OK" if abs(sig - pm["base_rating"]) < 1e-9 else f"MISMATCH (recomputed {sig:.4f})"
    add(f"  BASE RATING:   sigmoid({adjusted:.5f}) = {pm['base_rating']:.4f}  [{sig_check}]")
    add("")

    add("BONUSES AND PENALTIES (every component the service applied, in order)")
    components = snapshot.get("components", [])
    add(f"  {'Component':<36} {'Status':<13} {'Value':>9}  Detail")
    add(f"  {'-' * 100}")
    for comp in components:
        value = comp["value"]
        status = "did not fire" if abs(value) < 1e-12 else ("PENALTY" if value < 0 else "FIRED")
        add(f"  {comp['label']:<36} {status:<13} {value:>+9.4f}  {comp['text']}")
    if not components:
        add(f"  No bonus components were logged for position '{pos}'.")
    itemised = sum(c["value"] for c in components)
    service_total = snapshot["total_bonus"]
    add(f"  {'-' * 100}")
    add(f"  {'Sum of the components above':<36} {'':<13} {itemised:>+9.4f}")
    add(f"  {'Service total bonus':<36} {'':<13} {service_total:>+9.4f}")
    if abs(itemised - service_total) > 1e-9:
        add(
            f"  {'UNATTRIBUTED':<36} {'':<13} {service_total - itemised:>+9.4f}"
            "  <-- part of the service's bonus this report does not itemise"
        )
    add("")
    total_bonus = snapshot["total_bonus"]
    add(f"  TOTAL BONUS: {total_bonus:+.4f}")
    add("")

    add("SUPREMACY & FINAL")
    add(
        f"  Raw scalar:      {snapshot['supremacy_scalar']:+.4f}  "
        f"(team_xg={snapshot['team_xg']}, opp_xg={snapshot['xg_against']})"
    )
    add(
        f"  Quality factor:  max(0, min(1, 1 - {dot:.3f}/1.5)) = "
        f"{snapshot['quality_factor']:.4f}"
    )
    pos_scalar = snapshot.get("pos_supremacy_scalar", 1.0)
    if pos_scalar != 1.0:
        add(f"  Position scalar: {pos} supremacy reduced to x{pos_scalar}")
        add(
            f"  Adjusted:        {snapshot['supremacy_scalar']:.4f} x "
            f"{snapshot['quality_factor']:.4f} x {pos_scalar} = "
            f"{snapshot['adjusted_supremacy']:+.4f}"
        )
    else:
        add(
            f"  Adjusted:        {snapshot['supremacy_scalar']:.4f} x "
            f"{snapshot['quality_factor']:.4f} = {snapshot['adjusted_supremacy']:+.4f}"
        )
    add("")
    add(f"  base_rating              {pm['base_rating']:>+10.4f}")
    add(f"  total_bonus              {total_bonus:>+10.4f}")
    add(f"  supremacy (adjusted)     {-snapshot['adjusted_supremacy']:>+10.4f}")
    add(f"  {'-' * 36}")
    add(f"  raw_final                {snapshot['raw_final_rating']:>+10.4f}")
    add(f"  POSITION RATING (clamped){snapshot['position_final_rating']:>10.4f}")
    add("")

    return lines


def build_hybrid_report(blend: dict[str, Any]) -> list[str]:
    """Build the multi-position mirror-collapse + MAZ-weighted blend section."""
    lines: list[str] = []
    add = lines.append
    add("=" * 70)
    add("MULTI-POSITION HYBRID BLEND")
    add("=" * 70)
    add("")
    add(f"  Positions played: {blend['positions_played']}")
    add(
        "  Per-position ratings: "
        + ", ".join(
            f"{p}={r:.2f}" for p, r in zip(blend["positions_played"], blend["ratings"])
        )
    )
    if blend["dropped_by_mirror"]:
        add(
            f"  Mirror-pair collapse dropped: {blend['dropped_by_mirror']} "
            f"(kept the higher-rated side of each lateral pair)"
        )
    add(f"  Positions after collapse: {blend['collapsed_positions']}")
    add("")

    if not blend["hybrid"]:
        add("  Only one position remains after collapse - no blending applied.")
        add(f"  FINAL RATING: {blend['final_rating']:.1f}")
        return lines

    add("  MAZ (mean absolute z-score) fit per position - lower MAZ means the")
    add("  position's calibration fits this performance better, so it gets more")
    add("  weight in the blend:")
    add(
        f"  {'Position':<10} {'MAZ':>8} {'1/MAZ':>10} {'Norm weight':>13} {'Rating':>8}"
    )
    add(f"  {'-' * 55}")
    for p in blend["collapsed_positions"]:
        add(
            f"  {p:<10} {blend['maz'][p]:>8.4f} {blend['raw_weights'][p]:>10.4f} "
            f"{blend['norm_weights'][p]:>13.4f} {blend['position_ratings'][p]:>8.2f}"
        )
    add("")
    add(
        "  hybrid_base = sum(norm_weight[pos] x rating[pos]) = "
        f"{blend['hybrid_base']:.4f}"
    )
    add("")
    add(f"  r_min (worst positional rating): {blend['r_min']:.4f}")
    add(
        f"  versatility_bonus = VERSATILITY_BETA({MatchRatingsService.VERSATILITY_BETA}) x "
        f"max(0, r_min - {MatchRatingsService.VERSATILITY_THRESHOLD}) "
        f"= {blend['versatility_bonus']:.4f}"
    )
    add("")
    add("  hybrid_rating = hybrid_base + versatility_bonus")
    add(
        f"                = {blend['hybrid_base']:.4f} + "
        f"{blend['versatility_bonus']:.4f} = {blend['hybrid_rating']:.4f}"
    )
    add("")
    add(f"  FINAL RATING (clamped, rounded): {blend['final_rating']:.1f}")
    return lines


def build_full_report(
    svc: AttributionService,
    match_data: dict,
    team_name: str,
    performance: dict,
    half_length: int,
    final_rating: float | None,
    blend: dict[str, Any],
) -> str:
    """Build the complete report: match context, every position, hybrid blend."""
    lines = build_match_context_lines(match_data, team_name, performance, half_length)
    for pos in svc.position_order:
        lines.extend(
            build_position_report(
                svc, svc.position_snapshots[pos], pos, performance, half_length
            )
        )
        lines.append("")
    if blend:
        lines.extend(build_hybrid_report(blend))
        lines.append("")
    lines.append("=" * 70)
    lines.append(f"SERVICE FINAL RATING: {final_rating}")
    lines.append("=" * 70)
    return "\n".join(lines)
