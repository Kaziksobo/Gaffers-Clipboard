"""Golden anchors: pinned ratings for a small set of real performances.

The anchors live in ``tests/fixtures/golden/rating_anchors.json`` and reference
performances by ``(career, match_id, player_id)``; the data itself stays in
``datasets/``. A failure means the algorithm's output for that performance changed.
If that was intended, run ``uv run python scripts/regen_rating_anchors.py`` and
commit the refreshed file with the change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.data.conftest import CareerRecords, RateFn

_GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
_DOCUMENT = json.loads((_GOLDEN_DIR / "rating_anchors.json").read_text("utf-8"))
_ANCHORS: list[dict[str, Any]] = _DOCUMENT["anchors"]
_TOLERANCE: float = _DOCUMENT["tolerance"]


def _anchor_id(anchor: dict[str, Any]) -> str:
    """Return a readable test id for an anchor."""
    return f"{anchor['label']}-m{anchor['match_id']}-p{anchor['player_id']}"


@pytest.mark.parametrize("anchor", _ANCHORS, ids=_anchor_id)
def test_rating_anchor(
    anchor: dict[str, Any], careers: dict[str, CareerRecords], rate: RateFn
) -> None:
    """The service still gives this real performance its pinned rating."""
    career = careers[anchor["career"]]
    match = next(m for m in career.matches if m["id"] == anchor["match_id"])
    perf = next(
        p for p in match["player_performances"] if p["player_id"] == anchor["player_id"]
    )

    actual = rate(career.club, match["data"], perf)

    expected = anchor["expected"]
    message = (
        f"{anchor['label']}: expected {expected}, got {actual}. If this change is "
        "intended, run scripts/regen_rating_anchors.py and commit the result."
    )
    if expected is None:
        assert actual is None, message
    else:
        assert actual == pytest.approx(expected, abs=_TOLERANCE), message


def test_anchors_cover_every_career_and_both_pipelines(
    manifest: dict[str, dict[str, Any]], careers: dict[str, CareerRecords]
) -> None:
    """Anchors exist for every career, and include goalkeepers and outfield players."""
    covered = {a["career"] for a in _ANCHORS}
    assert covered == set(manifest)

    gk_anchors = 0
    for anchor in _ANCHORS:
        match = next(
            m
            for m in careers[anchor["career"]].matches
            if m["id"] == anchor["match_id"]
        )
        perf = next(
            p
            for p in match["player_performances"]
            if p["player_id"] == anchor["player_id"]
        )
        gk_anchors += perf["performance_type"] == "GK"
    assert 0 < gk_anchors < len(_ANCHORS)
