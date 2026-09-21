"""Shared attribution logic for tracing the outfield match-ratings algorithm.

Both rating_attribution.ipynb (interactive, one-position-at-a-time walkthrough)
and scripts/full_attribution_report.py (full per-position report for every
position listed on a performance) import this module so the two never drift
apart.

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

# Positions whose modifier method actually applies COLLAPSE_PENALTY
# (_apply_cb_modifiers, _apply_fb_modifiers, _apply_wb_modifiers only - CDM/CM/
# CAM/WM/Winger/ST never call it, even though some of them have a non-zero
# CS_RATIOS entry for the clean sheet bonus).
COLLAPSE_ELIGIBLE_POS = {"CB", "RB", "LB", "RWB", "LWB"}

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

MASTERY_NAMES = {
    ("tackles_p90_z", "possession_won_p90_z"): (
        "Destroyer / Dominant Stopper / Enforcer / Third CB / Two-Way Flank"
    ),
    ("passes_p90_z", "dribbles_p90_z"): (
        "Deep-Lying PM / Ball Playing Def / Progression Eng / Wide Playmaker / Complete Fwd"
    ),
    ("distance_sprinted_p90_z", "xt_bonus_p90_z"): "Express Train / Relentless Engine",
    ("dribbles_p90_z", "xt_bonus_p90_z"): "Direct Threat",
    ("passes_p90_z", "xt_bonus_p90_z"): "Wide Playmaker (Winger/CAM)",
    ("non_goal_shots_p90_z", "xt_bonus_p90_z"): "Shadow Striker",
    ("passes_p90_z", "tackles_p90_z"): "Two-Way Engine (WM)",
    ("xt_bonus_p90_z", "dribbles_p90_z"): "Wide Progressor (WM)",
}


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

    def _apply_mastery_bonus(
        self,
        z_scores: dict,
        key_a: str,
        key_b: str,
        threshold: float,
        impact_scalar: float,
    ) -> float:
        za = z_scores.get(key_a, 0.0)
        zb = z_scores.get(key_b, 0.0)
        mn = min(za, zb)
        excess = mn - threshold
        fired = excess > 0
        bonus = 0.0
        if fired:
            bonus = min(excess, self.MASTERY_EXCESS_CAP) * self.MASTERY_WEIGHT * impact_scalar
        self.attr.setdefault("mastery_log", []).append(
            {
                "key_a": key_a,
                "val_a": round(za, 4),
                "key_b": key_b,
                "val_b": round(zb, 4),
                "threshold": threshold,
                "min_z": round(mn, 4),
                "excess": round(max(0.0, excess), 4),
                "fired": fired,
                "bonus": round(bonus, 4),
            }
        )
        return bonus

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
            "impact_scalar": round(impact_scalar, 4),
            "isolation_multiplier": round(isolation_multiplier, 4),
            "goals": performance_metrics.get("goals", 0),
            "assists": performance_metrics.get("assists", 0),
            "shots": performance_metrics.get("shots", 0),
            "passes": performance_metrics.get("passes", 0),
            "pass_accuracy": performance_metrics.get("pass_accuracy", 0),
            "possession_lost": performance_metrics.get("possession_lost", 0),
        }
        self.attr["mastery_log"] = []
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
    blend = compute_hybrid_blend(svc, positions_played) if positions_played else {}
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

    Mirrors every step shown interactively in rating_attribution.ipynb (steps
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
    dribbles_z_pre = pre_floor.get("dribbles_p90_z", 0.0)
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
        post = z_scores_floored.get(z_key, pre) if fbwb_gate_open else pre
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
    add("  (Fl: F = a floor from the section above changed this z-score before the dot product)")
    add("")
    impact = pm["impact_scalar"]
    dot_str = "POSITIVE -> impact NOT applied" if dot >= 0 else "NEGATIVE -> impact applied"
    adjusted = dot if dot >= 0 else dot * impact
    add(f"  Impact scalar: sqrt(min({minutes},90)/90) = {impact:.4f}  [{dot_str}]")
    add(f"  Adjusted dot:  {adjusted:.5f}")
    add(f"  BASE RATING:   sigmoid({adjusted:.5f}) = {pm['base_rating']:.4f}")
    add("")

    add("BONUSES")
    goals = pm["goals"]
    assists = pm["assists"]
    iso = pm["isolation_multiplier"]
    alpha_goal = svc.GOAL_ALPHA.get(pos, 0.0)
    if goals >= 1:
        t_goals = goals**1.5
        raw_goal_bonus = alpha_goal * t_goals * iso
        gb = min(raw_goal_bonus, svc.GOAL_BONUS_CAP)
        cap_note = (
            f"  [capped at {svc.GOAL_BONUS_CAP}]"
            if raw_goal_bonus > svc.GOAL_BONUS_CAP
            else ""
        )
        add(
            f"  Goal bonus         FIRED          {gb:>+8.4f}  "
            f"(alpha={alpha_goal} x {goals:.0f}^1.5={t_goals:.4f} x iso={iso:.3f} "
            f"= {raw_goal_bonus:.4f}{cap_note})"
        )
    else:
        add(f"  Goal bonus         did not fire   {0.0:>+8.4f}  (goals=0)")
    gamma_assist = svc.ASSIST_GAMMA.get(pos, 0.0)
    if assists >= 1:
        t_assists = assists**1.5
        raw_assist_bonus = gamma_assist * t_assists * iso
        ab = min(raw_assist_bonus, svc.ASSIST_BONUS_CAP)
        cap_note = (
            f"  [capped at {svc.ASSIST_BONUS_CAP}]"
            if raw_assist_bonus > svc.ASSIST_BONUS_CAP
            else ""
        )
        add(
            f"  Assist bonus       FIRED          {ab:>+8.4f}  "
            f"(gamma={gamma_assist} x {assists:.0f}^1.5={t_assists:.4f} x iso={iso:.3f} "
            f"= {raw_assist_bonus:.4f}{cap_note})"
        )
    else:
        add(f"  Assist bonus       did not fire   {0.0:>+8.4f}  (assists=0)")

    add("")
    add("  Mastery conditions (bonus fires when both z-scores exceed the threshold):")
    for m in snapshot.get("mastery_log", []):
        key = (m["key_a"], m["key_b"])
        name = MASTERY_NAMES.get(key, f"{m['key_a']} + {m['key_b']}")
        status = "FIRED" if m["fired"] else "did not fire"
        add(f"    {name}")
        add(
            f"      {m['key_a']}={m['val_a']:.3f}  {m['key_b']}={m['val_b']:.3f}  "
            f"min={m['min_z']:.3f}  threshold={m['threshold']}  "
            f"-> {status} ({m['bonus']:>+.4f})"
        )

    if pos == "CM":
        # Progression Engine is computed inline in _apply_cm_modifiers (a flat
        # base-excess tier, not routed through _apply_mastery_bonus), so it's
        # never captured by mastery_log above - shown here directly instead,
        # from the same z_scores_floored/CM_PROGRESSION_BASE_EXCESS the service uses.
        passes_z = z_scores_floored.get("passes_p90_z", 0.0)
        dribbles_z = z_scores_floored.get("dribbles_p90_z", 0.0)
        progression_min = min(passes_z, dribbles_z)
        add("    Progression Engine (CM)")
        if progression_min > 1.2:
            excess = (progression_min - 1.2) + svc.CM_PROGRESSION_BASE_EXCESS
            capped_excess = min(excess, svc.MASTERY_EXCESS_CAP)
            prog_bonus = capped_excess * svc.MASTERY_WEIGHT * impact
            cap_note = (
                f"  [excess capped at {svc.MASTERY_EXCESS_CAP}]"
                if excess > svc.MASTERY_EXCESS_CAP
                else ""
            )
            add(
                f"      passes_p90_z={passes_z:.3f}  dribbles_p90_z={dribbles_z:.3f}  "
                f"min={progression_min:.3f}  threshold=1.2  "
                f"base_excess={svc.CM_PROGRESSION_BASE_EXCESS}  "
                f"-> FIRED ({prog_bonus:>+.4f}{cap_note})"
            )
        else:
            add(
                f"      passes_p90_z={passes_z:.3f}  dribbles_p90_z={dribbles_z:.3f}  "
                f"min={progression_min:.3f}  threshold=1.2  -> did not fire (+0.0000)"
            )

    opponent_goals = pm["opponent_goals"]
    if pos in COLLAPSE_ELIGIBLE_POS and opponent_goals >= 3 and minutes >= 60:
        add(
            f"  Collapse penalty   FIRED          {-svc.COLLAPSE_PENALTY:>+8.4f}  "
            f"(opp_goals={int(opponent_goals)}, mins={minutes}>=60)"
        )

    if pos == "CDM":
        poss_lost = pm["possession_lost"]
        pass_acc = pm["pass_accuracy"]
        raw_passes = snapshot["normalized_metrics"].get("passes", 0.0)
        gate = (
            minutes >= svc.CDM_PIVOT_MIN_MINUTES
            and pass_acc >= svc.CDM_PIVOT_MIN_PASS_ACC
            and raw_passes >= svc.CDM_PIVOT_MIN_PASSES_RAW
        )
        add("")
        add(
            f"  CDM Reliable Pivot gate: {'OPEN' if gate else 'CLOSED'} "
            f"(mins>={svc.CDM_PIVOT_MIN_MINUTES}: {minutes}, "
            f"pass_acc>={svc.CDM_PIVOT_MIN_PASS_ACC}: {pass_acc}, "
            f"passes_raw>={svc.CDM_PIVOT_MIN_PASSES_RAW}: {raw_passes:.2f})"
        )
        if gate:
            if poss_lost == 0:
                add(f"    Perfect Metronome: poss_lost==0 -> +{svc.CDM_PIVOT_PERFECT_METRONOME}")
            elif poss_lost <= 2:
                add(
                    f"    Reliable Shift: poss_lost={poss_lost}<=2 -> "
                    f"+{svc.CDM_PIVOT_RELIABLE_SHIFT}"
                )
            else:
                add(f"    poss_lost={poss_lost} > 2 - neither tier fires")

    opp_xg_val = pm["opponent_xg"]
    cs_ratio = svc.CS_RATIOS.get(pos, 0.0)
    add("")
    if opponent_goals == 0 and cs_ratio > 0:
        ramp = min(minutes, 60.0) / 60.0
        if opp_xg_val <= 1.0:
            tier_val, tier_name = svc.CS_CB_LOW_XG, "low xG (<=1.0)"
        elif opp_xg_val < 2.0:
            tier_val, tier_name = svc.CS_CB_MID_XG, "mid xG (1.0-2.0)"
        else:
            tier_val, tier_name = svc.CS_CB_HIGH_XG, "high xG (>=2.0)"
        cs_bonus = tier_val * cs_ratio * ramp
        add(
            f"  Clean sheet ({tier_name}, xG={opp_xg_val}): "
            f"{tier_val} x ratio={cs_ratio} x ramp={ramp:.3f} = {cs_bonus:+.4f}"
        )
    elif opponent_goals == 0:
        add(f"  Clean sheet: {pos} has CS ratio=0 - no bonus")
    else:
        add(f"  Clean sheet: opponent scored {int(opponent_goals)} - no bonus")

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
