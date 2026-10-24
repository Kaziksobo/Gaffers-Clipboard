"""One-step refit of the rating config from every career in ``datasets/``.

Typical use after collecting more matches (see ``scripts/refit_config.py``)::

    uv run python scripts/refit_config.py --import C:/path/to/ipswich_3            # preview
    uv run python scripts/refit_config.py --import C:/path/to/ipswich_3 --promote  # apply

This module holds the pieces: fit every career with the rare-event policy, check the
result, report how far it moved from the live config and what that does to ratings, and
promote it (with a backup) into ``config/``.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from workshop.lib import datasets, fit, rating

CALIBRATION_DIR = datasets.PROJECT_ROOT / "workshop" / "calibration"
CANDIDATES_DIR = CALIBRATION_DIR / "candidates"
RECORDS_DIR = CALIBRATION_DIR / "records"
LIVE_DIR = fit.LIVE_CONFIG_DIR
DEFAULT_POLICY = fit.RareEventPolicy()
DEFAULT_DIRECT_POLICY = fit.DirectFitPolicy()
_GROUPS = {
    "ST": "ST", "CF": "ST", "LW": "Winger", "RW": "Winger", "LM": "WM", "RM": "WM",
    "CAM": "CAM", "CM": "CM", "CDM": "CDM", "CB": "CB", "LB": "Fullback", "RB": "Fullback",
    "GK": "GK",
}  # fmt: skip


def fit_all(
    careers: list[str] | None = None,
    policy: fit.RareEventPolicy | None = DEFAULT_POLICY,
) -> fit.FitResult:
    """Fit every position (and derive the rest) on all matches of the given careers.

    Args:
        careers: Career names; defaults to every career tagged ``pool`` in the manifest.
        policy: Rare-event policy (``None`` disables it).
    """
    names = careers or datasets.career_names("pool")
    sources = fit.load_sources({name: None for name in names})
    return fit.fit_positions(
        sources,
        rare_event_policy=policy,
        derive_unknown=True,
        include_gk=True,
        direct_fit_policy=DEFAULT_DIRECT_POLICY,
    )


def validate_config(config_dir: Path) -> list[str]:
    """Return problems found in a config directory (empty when it is sound)."""
    problems: list[str] = []
    weights = json.loads((config_dir / fit.WEIGHTS_FILE).read_text("utf-8"))
    means_stds = json.loads((config_dir / fit.MEANS_STDS_FILE).read_text("utf-8"))
    for section, stats in weights.items():
        if list(stats) != fit.STAT_COLUMNS:
            problems.append(f"weights[{section}] has the wrong stats or order")
            continue
        if not all(math.isfinite(w) for w in stats.values()):
            problems.append(f"weights[{section}] has non-finite values")
        elif abs(sum(stats.values()) - 1.0) > 1e-9:
            problems.append(f"weights[{section}] sums to {sum(stats.values()):.6f}, not 1")
    gk = means_stds.get("GK")
    if gk is not None and not (
        math.isfinite(gk["mean"]) and math.isfinite(gk["std"]) and gk["std"] > 0
    ):
        problems.append(f"means_stds[GK] is invalid: {gk}")
    for section, stats in means_stds.items():
        if section == "GK":
            continue
        if set(stats) != set(fit.STAT_COLUMNS):
            problems.append(f"means_stds[{section}] has the wrong stats")
            continue
        for stat, ms in stats.items():
            if not (math.isfinite(ms["mean"]) and math.isfinite(ms["std"]) and ms["std"] >= 0):
                problems.append(f"means_stds[{section}][{stat}] is invalid: {ms}")
    missing = set(weights) - set(means_stds)
    if missing:
        problems.append(f"sections with weights but no means/stds: {sorted(missing)}")
    return problems


def movement(live_dir: Path, candidate_dir: Path) -> pd.DataFrame:
    """Per section: how far weights, means and stds moved from the live config.

    Mean shifts are in units of the live std; std ratios are candidate / live where the
    live std is non-zero. ``std_switches`` counts stats whose std goes between zero
    and non-zero (which switches the service between z = 0 and a live z-score).
    """
    lw = json.loads((live_dir / fit.WEIGHTS_FILE).read_text("utf-8"))
    cw = json.loads((candidate_dir / fit.WEIGHTS_FILE).read_text("utf-8"))
    lm = json.loads((live_dir / fit.MEANS_STDS_FILE).read_text("utf-8"))
    cm = json.loads((candidate_dir / fit.MEANS_STDS_FILE).read_text("utf-8"))
    rows = []
    for section in sorted(cw):
        dw = {k: abs(cw[section][k] - lw[section][k]) for k in cw[section]}
        shifts, ratios, switches = [], [], 0
        for stat, live_stats in lm[section].items():
            cand_stats = cm[section][stat]
            if live_stats["std"] > 0:
                shifts.append(abs(cand_stats["mean"] - live_stats["mean"]) / live_stats["std"])
                ratios.append(cand_stats["std"] / live_stats["std"])
            switches += (live_stats["std"] == 0) != (cand_stats["std"] == 0)
        rows.append(
            {
                "section": section,
                "max_weight_change": max(dw.values()),
                "stat_max_weight_change": max(dw, key=dw.get),
                "max_mean_shift_in_stds": max(shifts, default=0.0),
                "std_ratio_min": min(ratios, default=1.0),
                "std_ratio_max": max(ratios, default=1.0),
                "std_switches": switches,
            }
        )
    if "GK" in cm and "GK" in lm:
        live_gk, cand_gk = lm["GK"], cm["GK"]
        ratio = cand_gk["std"] / live_gk["std"]
        rows.append(
            {
                "section": "GK (means/stds only)",
                "max_weight_change": 0.0,
                "stat_max_weight_change": "-",
                "max_mean_shift_in_stds": abs(cand_gk["mean"] - live_gk["mean"]) / live_gk["std"],
                "std_ratio_min": ratio,
                "std_ratio_max": ratio,
                "std_switches": 0,
            }
        )
    return pd.DataFrame(rows).set_index("section")


def rating_effect(
    live_dir: Path, candidate_dir: Path, careers: list[str] | None = None
) -> pd.DataFrame:
    """How the candidate changes outfield ratings against the live config, by position."""
    names = careers or datasets.career_names()
    live = rating.rated_performances(names=names, config_dir=live_dir, column="live")
    cand = rating.rated_performances(names=names, config_dir=candidate_dir, column="cand")
    frame = live.merge(
        cand[["career", "match_id", "player_id", "cand"]],
        on=["career", "match_id", "player_id"],
        validate="one_to_one",
    )
    frame = frame[frame["live"].notna()]
    frame = frame.assign(
        group=frame["primary_position"].map(_GROUPS), change=frame["cand"] - frame["live"]
    )

    def summarise(part: pd.DataFrame) -> pd.Series:
        change = part["change"]
        return pd.Series(
            {
                "rows": len(change),
                "mean_change": change.mean(),
                "mean_abs_change": change.abs().mean(),
                "share_changed": (change.abs() > 0).mean(),
                "share_moved_0_5": (change.abs() >= 0.5 - 1e-9).mean(),
                "max_abs_change": change.abs().max(),
            }
        )

    overall = frame.groupby("career").apply(summarise, include_groups=False)
    by_group = frame.dropna(subset=["group"]).groupby("group").apply(
        summarise, include_groups=False
    )
    by_group.index = [f"position: {g}" for g in by_group.index]
    overall.index = [f"career: {c}" for c in overall.index]
    return pd.concat([overall, by_group])


def _display_path(path: Path) -> str:
    """Return ``path`` relative to the project root when inside it, else as given."""
    try:
        return path.resolve().relative_to(datasets.PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def promote(
    candidate_dir: Path,
    config_dir: Path = LIVE_DIR,
    backup_root: Path = CANDIDATES_DIR,
) -> dict[str, Any]:
    """Copy a validated candidate into ``config_dir``, keeping a backup of what it replaces.

    Raises:
        ValueError: If the candidate fails ``validate_config`` or its manifest hash does
            not match its files.
    """
    problems = validate_config(candidate_dir)
    if problems:
        raise ValueError("candidate is not sound: " + "; ".join(problems))
    manifest = json.loads((candidate_dir / fit.MANIFEST_FILE).read_text("utf-8"))
    if manifest["config_hash"] != fit.config_hash(candidate_dir):
        raise ValueError("candidate manifest hash does not match its files")

    old_hash = fit.config_hash(config_dir)
    backup = backup_root / f"previous_{old_hash[:8]}"
    backup.mkdir(parents=True, exist_ok=True)
    for name in (fit.WEIGHTS_FILE, fit.MEANS_STDS_FILE, fit.MANIFEST_FILE):
        if (config_dir / name).exists():
            shutil.copy2(config_dir / name, backup / name)
    for name in (fit.WEIGHTS_FILE, fit.MEANS_STDS_FILE, fit.MANIFEST_FILE):
        shutil.copy2(candidate_dir / name, config_dir / name)
    return {
        "previous_hash": old_hash,
        "new_hash": fit.config_hash(config_dir),
        "backup": _display_path(backup),
    }


def write_record(info: dict[str, Any], result: fit.FitResult, directory: Path = RECORDS_DIR) -> Path:
    """Write a small JSON record of a promotion (hashes, sources, policy, rows)."""
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        **info,
        "sources": result.sources,
        "rare_event_policy": result.policy,
        "rows_per_position": result.rows,
    }
    path = directory / f"refit_{info['new_hash'][:8]}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", "utf-8")
    return path


def float_summary(value: Any) -> str:  # noqa: ANN401
    """Format a number compactly for console reports."""
    return f"{value:.4f}" if isinstance(value, (float, np.floating)) else str(value)
