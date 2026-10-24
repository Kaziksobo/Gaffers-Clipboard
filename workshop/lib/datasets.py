"""Load career datasets for workshop notebooks and scripts.

Careers live in ``datasets/careers/<folder_name>/`` exactly as the app writes them
(``matches.json``, ``players.json``, ``metadata.json``). ``datasets/careers.toml``
tags each career with its role(s):

- ``calibration``: fits weights, means/stds and anchors (Valencia).
- ``ood``: out-of-distribution validation only (Arsenal, Ipswich).
- ``pool``: eligible for pooled analyses, e.g. possession-adjusted distance stats.

Match and player ids restart at 1 in every career, so every frame carries a
``career`` column and anything joined across careers must key on
``(career, match_id)`` / ``(career, player_id)``.

The stored ``match_rating`` field is deliberately never exposed: it holds the app's
own output from whichever algorithm version was live when the match was saved.
Recompute ratings with ``MatchRatingsService`` instead.

Example:
    >>> from workshop.lib.datasets import performances
    >>> calibration = performances("calibration")
    >>> ood = performances("ood")
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = PROJECT_ROOT / "datasets"
CAREERS_DIR = DATASETS_DIR / "careers"
MANIFEST_PATH = DATASETS_DIR / "careers.toml"

_DROPPED_PERFORMANCE_FIELDS = frozenset({"match_rating"})


@dataclass(frozen=True)
class Career:
    """One career save as stored on disk, plus its manifest entry."""

    name: str
    club: str
    tags: tuple[str, ...]
    metadata: dict[str, Any]
    matches: list[dict[str, Any]]
    players: list[dict[str, Any]]


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, dict[str, Any]]:
    """Return the career manifest keyed by folder name."""
    with path.open("rb") as f:
        return tomllib.load(f)


def career_names(tag: str | None = None) -> list[str]:
    """Return career folder names, optionally only those carrying ``tag``."""
    manifest = load_manifest()
    return [n for n, e in manifest.items() if tag is None or tag in e["tags"]]


def load_career(name: str) -> Career:
    """Load one career's raw records.

    Raises:
        KeyError: If the career is not in the manifest.
    """
    entry = load_manifest()[name]
    folder = CAREERS_DIR / name

    def read(filename: str) -> Any:  # noqa: ANN401
        return json.loads((folder / filename).read_text(encoding="utf-8"))

    return Career(
        name=name,
        club=entry["club"],
        tags=tuple(entry["tags"]),
        metadata=read("metadata.json"),
        matches=read("matches.json"),
        players=read("players.json"),
    )


def load_careers(
    tag: str | None = None, names: list[str] | None = None
) -> list[Career]:
    """Load every career carrying ``tag``, or the explicitly named ones."""
    selected = names if names is not None else career_names(tag)
    return [load_career(n) for n in selected]


def _sides(career: Career, data: dict[str, Any]) -> tuple[str, str]:
    """Return ``(team_side, opponent_side)`` for the user's club in a match."""
    if data["home_team_name"] == career.club:
        return "home", "away"
    if data["away_team_name"] == career.club:
        return "away", "home"
    raise ValueError(
        f"{career.name}: club {career.club!r} is in neither side of match "
        f"{data['home_team_name']} v {data['away_team_name']}"
    )


def _match_context(career: Career, match: dict[str, Any]) -> dict[str, Any]:
    """Flatten one match into team/opponent-relative columns."""
    data = match["data"]
    team, opp = _sides(career, data)
    context: dict[str, Any] = {
        "career": career.name,
        "match_id": match["id"],
        "in_game_date": data["in_game_date"],
        "competition": data["competition"],
        "half_length": data.get("half_length", career.metadata.get("half_length")),
        "team": data[f"{team}_team_name"],
        "opponent": data[f"{opp}_team_name"],
        "is_home": team == "home",
        "team_score": data[f"{team}_score"],
        "opp_score": data[f"{opp}_score"],
    }
    context.update({f"team_{k}": v for k, v in data[f"{team}_stats"].items()})
    context.update({f"opp_{k}": v for k, v in data[f"{opp}_stats"].items()})
    return context


def matches(tag: str | None = None, names: list[str] | None = None) -> pd.DataFrame:
    """Return one row per match, from the user's club's point of view."""
    rows = [
        _match_context(c, m)
        for c in load_careers(tag, names)
        for m in c.matches
    ]
    frame = pd.DataFrame(rows)
    frame["in_game_date"] = pd.to_datetime(frame["in_game_date"])
    return frame


def performances(
    tag: str | None = None, names: list[str] | None = None
) -> pd.DataFrame:
    """Return one row per player performance with its match context attached.

    Match-level columns are prefixed ``team_`` (the user's club) and ``opp_``.
    ``primary_position`` is the first entry of ``positions_played`` (``GK`` for
    goalkeepers) and ``n_positions`` the number of positions played. The stored
    ``match_rating`` is excluded.
    """
    rows: list[dict[str, Any]] = []
    for career in load_careers(tag, names):
        for match in career.matches:
            context = _match_context(career, match)
            for perf in match["player_performances"]:
                row = dict(context)
                row.update(
                    {
                        k: v
                        for k, v in perf.items()
                        if k not in _DROPPED_PERFORMANCE_FIELDS
                    }
                )
                positions = perf.get("positions_played") or []
                is_gk = perf["performance_type"] == "GK"
                row["primary_position"] = "GK" if is_gk else positions[0]
                row["n_positions"] = len(positions)
                rows.append(row)
    frame = pd.DataFrame(rows)
    frame["in_game_date"] = pd.to_datetime(frame["in_game_date"])
    return frame


def players(tag: str | None = None, names: list[str] | None = None) -> pd.DataFrame:
    """Return one row per player (latest snapshot fields only)."""
    rows = [
        {
            "career": c.name,
            "player_id": p["id"],
            "name": p["name"],
            "nationality": p["nationality"],
            "age": p["age"],
            "positions": p["positions"],
            "sold": p["sold"],
            "loaned": p["loaned"],
        }
        for c in load_careers(tag, names)
        for p in c.players
    ]
    return pd.DataFrame(rows)
