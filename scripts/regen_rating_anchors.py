"""Create or refresh the golden rating anchors used by the data tests.

Overview
--------
``tests/fixtures/golden/rating_anchors.json`` pins the rating that the *current*
algorithm gives to a small set of real performances, referenced as
``(career, match_id, player_id)`` so the data itself stays in ``datasets/``.
``tests/data/test_rating_anchors.py`` fails when any of them changes, which is the
prompt to ask "was that intended?". When it was, run this script to accept the new
values, review the printed changes, and commit the updated file together with the
algorithm change.

Ratings are rounded to one decimal place, so the default tolerance of 0.05 means
an anchor must match exactly.

Quick Start
-----------
Refresh the expected rating of every existing anchor and print what changed:

        uv run python scripts/regen_rating_anchors.py

Add automatically chosen anchors that are not in the file yet (existing ones, and
any you added by hand, are kept):

        uv run python scripts/regen_rating_anchors.py --select

Report differences without writing (exit code 1 if any):

        uv run python scripts/regen_rating_anchors.py --check

Adding your own anchor
----------------------
Append an entry with ``career``, ``match_id``, ``player_id`` and a ``label`` (leave
``expected`` as ``null``), then run the script without flags to fill it in. Good
candidates are performances whose attribution you have already reviewed.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.analytics.match_ratings_service import (  # noqa: E402
    MatchRatingsService,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.contracts.backend import MatchOverviewPayload, PlayerPerformancePayload

ANCHORS_PATH = PROJECT_ROOT / "tests" / "fixtures" / "golden" / "rating_anchors.json"
DEFAULT_TOLERANCE = 0.05
FULL_MATCH_MINUTES = 80
STARTER_MINUTES = 60
PIVOT_MINUTES = 45


@dataclass(frozen=True)
class Candidate:
    """One real performance with its current rating and match context."""

    career: str
    club: str
    match_id: int
    player_id: int
    data: dict[str, Any]
    perf: dict[str, Any]
    rating: float | None

    @property
    def is_gk(self) -> bool:
        """Whether this is a goalkeeper performance."""
        return self.perf["performance_type"] == "GK"

    @property
    def positions(self) -> list[str]:
        """Positions played (empty for goalkeepers)."""
        return self.perf.get("positions_played", [])

    @property
    def minutes(self) -> float:
        """Minutes played on the 90-minute scale (0 for goalkeepers)."""
        return self.perf.get("minutes_played", 0)

    @property
    def conceded(self) -> int:
        """Goals conceded by the user's club in this match."""
        home = self.data["home_team_name"] == self.club
        return self.data["away_score"] if home else self.data["home_score"]

    def single(self, *positions: str) -> bool:
        """Whether the player played exactly one position, among ``positions``."""
        return len(self.positions) == 1 and self.positions[0] in positions


@dataclass(frozen=True)
class Rule:
    """How to pick one anchor: filter candidates, then take the best by ``key``."""

    label: str
    per_career: bool
    keep: Callable[[Candidate], bool]
    key: Callable[[Candidate], float]


FULLBACKS = ("LB", "RB", "LWB", "RWB")
RULES = [
    Rule("gk-best", False, lambda c: c.is_gk, lambda c: c.rating or 0),
    Rule("gk-worst", False, lambda c: c.is_gk, lambda c: -(c.rating or 0)),
    Rule(
        "st-multi-goal",
        True,
        lambda c: (
            c.single("ST", "CF")
            and c.perf["goals"] >= 2
            and c.minutes >= STARTER_MINUTES
        ),
        lambda c: c.perf["goals"],
    ),
    Rule(
        "st-wasteful",
        True,
        lambda c: (
            c.single("ST", "CF")
            and c.perf["goals"] == 0
            and c.perf["shots"] >= 5
            and c.minutes >= STARTER_MINUTES
        ),
        lambda c: c.perf["shots"],
    ),
    Rule(
        "winger-assists",
        True,
        lambda c: c.single("LW", "RW") and c.perf["assists"] >= 2,
        lambda c: c.perf["assists"],
    ),
    Rule(
        "cm-top",
        True,
        lambda c: c.single("CM") and c.minutes >= STARTER_MINUTES,
        lambda c: c.rating or 0,
    ),
    Rule(
        "cm-cdm-blend",
        False,
        lambda c: set(c.positions) == {"CM", "CDM"} and c.minutes >= PIVOT_MINUTES,
        lambda c: c.minutes,
    ),
    Rule(
        "cdm-pivot-gate",
        True,
        lambda c: (
            c.single("CDM")
            and c.minutes >= PIVOT_MINUTES
            and c.perf["pass_accuracy"] >= 88
            and c.perf["passes"] >= 15
        ),
        lambda c: c.perf["passes"],
    ),
    Rule(
        "cb-clean-sheet",
        True,
        lambda c: (
            c.single("CB") and c.minutes >= FULL_MATCH_MINUTES and c.conceded == 0
        ),
        lambda c: c.rating or 0,
    ),
    Rule(
        "cb-collapse",
        False,
        lambda c: c.single("CB") and c.minutes >= STARTER_MINUTES and c.conceded >= 3,
        lambda c: c.conceded,
    ),
    Rule(
        "fb-attacking",
        False,
        lambda c: c.single(*FULLBACKS) and c.perf["goals"] + c.perf["assists"] >= 1,
        lambda c: c.perf["goals"] + c.perf["assists"],
    ),
    Rule(
        "wide-mid",
        False,
        lambda c: c.single("LM", "RM") and c.minutes >= STARTER_MINUTES,
        lambda c: c.rating or 0,
    ),
    Rule(
        "cam",
        False,
        lambda c: c.single("CAM") and c.minutes >= STARTER_MINUTES,
        lambda c: c.rating or 0,
    ),
    Rule(
        "short-cameo",
        False,
        lambda c: not c.is_gk and 10 <= c.minutes <= 20,
        lambda c: c.minutes,
    ),
    Rule(
        "outfield-max",
        False,
        lambda c: not c.is_gk and c.rating is not None,
        lambda c: c.rating or 0,
    ),
    Rule(
        "outfield-min",
        False,
        lambda c: not c.is_gk and c.rating is not None,
        lambda c: -(c.rating or 0),
    ),
]


def build_rater() -> Callable[[str, dict[str, Any], dict[str, Any]], float | None]:
    """Return ``rate(club, match_data, performance)`` using the live ``config/``.

    Returns:
        Callable[[str, dict[str, Any], dict[str, Any]], float | None]: The rater.
    """
    config = PROJECT_ROOT / "config"
    weights = json.loads((config / "performance_weights.json").read_text("utf-8"))
    means_stds = json.loads((config / "performance_means_stds.json").read_text("utf-8"))
    service = MatchRatingsService(weights, means_stds)

    def rate(
        club: str, match_data: dict[str, Any], performance: dict[str, Any]
    ) -> float | None:
        perf = cast(
            "PlayerPerformancePayload",
            {k: v for k, v in performance.items() if k != "match_rating"},
        )
        overview = cast("MatchOverviewPayload", match_data)
        half = match_data["half_length"]
        if performance["performance_type"] == "GK":
            rating = service.calculate_gk_rating(perf, overview, half, club)
        else:
            rating = service.calculate_outfield_rating(perf, overview, half, club)
        return None if rating is None else round(float(rating), 1)

    return rate


def load_candidates(
    rate: Callable[[str, dict[str, Any], dict[str, Any]], float | None],
) -> list[Candidate]:
    """Load and rate every performance in every registered career.

    Args:
        rate (Callable): Rating function from ``build_rater``.

    Returns:
        list[Candidate]: Every performance, in manifest then match order.
    """
    datasets = PROJECT_ROOT / "datasets"
    with (datasets / "careers.toml").open("rb") as f:
        manifest = tomllib.load(f)
    candidates: list[Candidate] = []
    for name, entry in manifest.items():
        path = datasets / "careers" / name / "matches.json"
        for match in json.loads(path.read_text("utf-8")):
            for perf in match["player_performances"]:
                candidates.append(
                    Candidate(
                        career=name,
                        club=entry["club"],
                        match_id=match["id"],
                        player_id=perf["player_id"],
                        data=match["data"],
                        perf=perf,
                        rating=rate(entry["club"], match["data"], perf),
                    )
                )
    return candidates


def select_anchors(candidates: list[Candidate]) -> list[dict[str, Any]]:
    """Pick one anchor per rule (or per career for per-career rules).

    Args:
        candidates (list[Candidate]): Every rated performance.

    Returns:
        list[dict[str, Any]]: Anchor entries with ``expected`` already filled in.
    """
    chosen: list[dict[str, Any]] = []
    for rule in RULES:
        groups: dict[str, list[Candidate]] = {}
        for c in candidates:
            if rule.keep(c):
                groups.setdefault(c.career if rule.per_career else "", []).append(c)
        for career, group in groups.items():
            best = max(group, key=rule.key)
            label = f"{rule.label}@{career}" if rule.per_career else rule.label
            chosen.append(
                {
                    "label": label,
                    "career": best.career,
                    "match_id": best.match_id,
                    "player_id": best.player_id,
                    "expected": best.rating,
                }
            )
    return chosen


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv (list[str] | None): Argument list, or None to use ``sys.argv``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument(
        "--select", action="store_true", help="Add auto-picked anchors."
    )
    parser.add_argument("--check", action="store_true", help="Report only; no write.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Refresh (and optionally extend) the golden rating anchors.

    Args:
        argv (list[str] | None): Argument list, or None to use ``sys.argv``.

    Returns:
        int: 0 on success; with ``--check``, 1 if any expected value differs.
    """
    args = parse_args(argv)
    candidates = load_candidates(build_rater())
    by_key = {(c.career, c.match_id, c.player_id): c for c in candidates}

    document: dict[str, Any] = {"tolerance": DEFAULT_TOLERANCE, "anchors": []}
    if ANCHORS_PATH.exists():
        document = json.loads(ANCHORS_PATH.read_text("utf-8"))
    anchors: list[dict[str, Any]] = document["anchors"]

    if args.select:
        present = {(a["career"], a["match_id"], a["player_id"]) for a in anchors}
        for new in select_anchors(candidates):
            if (new["career"], new["match_id"], new["player_id"]) not in present:
                anchors.append(new)
                present.add((new["career"], new["match_id"], new["player_id"]))
                print(f"  + {new['label']}: {new['expected']}")

    changed = 0
    for anchor in anchors:
        key = (anchor["career"], anchor["match_id"], anchor["player_id"])
        if key not in by_key:
            print(f"ERROR: anchor {anchor['label']} {key} not found in datasets.")
            return 1
        current = by_key[key].rating
        if anchor.get("expected") != current:
            changed += 1
            print(f"  ~ {anchor['label']}: {anchor.get('expected')} -> {current}")
            anchor["expected"] = current

    print(f"{len(anchors)} anchors, {changed} changed.")
    if args.check:
        return 1 if changed else 0
    ANCHORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANCHORS_PATH.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
