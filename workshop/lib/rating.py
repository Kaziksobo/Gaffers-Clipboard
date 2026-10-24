"""Recompute match ratings with the live (or a candidate) rating configuration.

Stored ``match_rating`` values in career files are outputs of whichever algorithm
version was live when the match was saved, and they are nulled in ``datasets/``.
Everything in the workshop should recompute ratings with the service instead.

A full pass over every career takes well under a second, so nothing is cached.

Example:
    >>> from workshop.lib.rating import rated_performances
    >>> live = rated_performances("pool")  # config/ as shipped
    >>> candidate = rated_performances("pool", config_dir=CANDIDATES_DIR)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd

from src.services.analytics.match_ratings_service import MatchRatingsService
from workshop.lib import datasets

LIVE_CONFIG_DIR = datasets.PROJECT_ROOT / "config"
_WEIGHTS_FILE = "performance_weights.json"
_MEANS_STDS_FILE = "performance_means_stds.json"
_KEYS = ["career", "match_id", "player_id"]


def load_service(config_dir: Path | None = None) -> MatchRatingsService:
    """Build a MatchRatingsService from a config directory.

    Args:
        config_dir: Folder holding ``performance_weights.json`` and
            ``performance_means_stds.json``. Defaults to the live ``config/``.

    Raises:
        FileNotFoundError: If either file is missing from ``config_dir``.
    """
    folder = config_dir or LIVE_CONFIG_DIR
    weights = json.loads((folder / _WEIGHTS_FILE).read_text(encoding="utf-8"))
    means_stds = json.loads((folder / _MEANS_STDS_FILE).read_text(encoding="utf-8"))
    return MatchRatingsService(weights, means_stds)


def rate_performance(
    service: MatchRatingsService,
    club: str,
    match_data: dict[str, Any],
    performance: dict[str, Any],
    half_length: int | None = None,
) -> float | None:
    """Rate one performance, ignoring any stored ``match_rating``.

    Args:
        service: Service to rate with.
        club: The user's club (decides home/away context).
        match_data: The match's ``data`` section.
        performance: One entry of ``player_performances``.
        half_length: Override the match's half length (defaults to the match's own).

    Returns:
        The 0-10 rating, or None for an outfield player under 10 minutes.
    """
    perf = {k: v for k, v in performance.items() if k != "match_rating"}
    half = half_length if half_length is not None else match_data["half_length"]
    if performance["performance_type"] == "GK":
        rating = service.calculate_gk_rating(
            cast("Any", perf), cast("Any", match_data), half, club
        )
    else:
        rating = service.calculate_outfield_rating(
            cast("Any", perf), cast("Any", match_data), half, club
        )
    return None if rating is None else float(rating)


def stamp_current_ratings(
    matches: list[dict[str, Any]],
    club: str,
    service: MatchRatingsService | None = None,
) -> None:
    """Overwrite ``match_rating`` on every performance, in place, with current ratings.

    For notebooks that read a career's ``matches.json`` directly: call this right
    after loading so ``match_rating`` holds today's rating rather than a stale (or
    null) stored value.

    Args:
        matches: Match records as loaded from ``matches.json``.
        club: The user's club name.
        service: Service to rate with (defaults to the live config).
    """
    service = service or load_service()
    for match in matches:
        for perf in match["player_performances"]:
            perf["match_rating"] = rate_performance(
                service, club, match["data"], perf
            )


def ratings(
    careers: list[datasets.Career], service: MatchRatingsService
) -> pd.DataFrame:
    """Rate every performance in ``careers``.

    Returns:
        One row per performance with ``career``, ``match_id``, ``player_id`` and
        ``rating`` (None where the player was too short to rate).
    """
    rows = [
        {
            "career": c.name,
            "match_id": match["id"],
            "player_id": perf["player_id"],
            "rating": rate_performance(service, c.club, match["data"], perf),
        }
        for c in careers
        for match in c.matches
        for perf in match["player_performances"]
    ]
    return pd.DataFrame(rows)


def rated_performances(
    tag: str | None = None,
    names: list[str] | None = None,
    service: MatchRatingsService | None = None,
    config_dir: Path | None = None,
    column: str = "rating",
) -> pd.DataFrame:
    """Return ``datasets.performances`` with a freshly computed rating column.

    Args:
        tag: Manifest tag selecting the careers (e.g. ``"pool"``).
        names: Explicit career names instead of a tag.
        service: Service to rate with. Overrides ``config_dir``.
        config_dir: Rate with a candidate config instead of the live ``config/``.
        column: Name of the rating column.
    """
    service = service or load_service(config_dir)
    frame = datasets.performances(tag, names)
    scored = ratings(datasets.load_careers(tag, names), service)
    scored = scored.rename(columns={"rating": column})
    return frame.merge(scored, on=_KEYS, how="left", validate="one_to_one")
