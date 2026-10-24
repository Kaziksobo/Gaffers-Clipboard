"""Check the workshop rating helpers agree with the service as the tests call it."""

from __future__ import annotations

import copy
import shutil
from typing import TYPE_CHECKING

import pytest
from workshop.lib import rating as workshop_rating

if TYPE_CHECKING:
    from pathlib import Path

    from tests.data.conftest import CareerRecords, RatedPerformance


def test_rated_performances_match_the_service(
    rated_performances: list[RatedPerformance],
) -> None:
    """The pooled workshop frame carries exactly the ratings the service produces."""
    frame = workshop_rating.rated_performances("pool")
    assert len(frame) == len(rated_performances)

    expected = {
        (r.career, r.match_id, r.player_id): r.rating for r in rated_performances
    }
    mismatches = []
    for row in frame.itertuples():
        want = expected[(row.career, row.match_id, row.player_id)]
        got = None if row.rating != row.rating else row.rating  # NaN -> None
        if got != want:
            mismatches.append((row.career, row.match_id, row.player_id, want, got))
    assert not mismatches, mismatches[:5]


def test_stamp_current_ratings_fills_nulled_ratings(
    careers: dict[str, CareerRecords], rated_performances: list[RatedPerformance]
) -> None:
    """Stamping a stripped career in place reproduces the service's ratings."""
    career = careers["arsenal_2"]
    matches = copy.deepcopy(career.matches[:5])
    assert all(
        p["match_rating"] is None for m in matches for p in m["player_performances"]
    )

    workshop_rating.stamp_current_ratings(matches, career.club)

    expected = {
        (r.match_id, r.player_id): r.rating
        for r in rated_performances
        if r.career == "arsenal_2"
    }
    for match in matches:
        for perf in match["player_performances"]:
            assert perf["match_rating"] == expected[(match["id"], perf["player_id"])]


def test_candidate_config_directory(tmp_path: Path) -> None:
    """A config directory is used as given, and an incomplete one is an error."""
    live = workshop_rating.LIVE_CONFIG_DIR
    with pytest.raises(FileNotFoundError):
        workshop_rating.load_service(tmp_path)

    for name in ("performance_weights.json", "performance_means_stds.json"):
        shutil.copy(live / name, tmp_path / name)
    live_frame = workshop_rating.rated_performances(names=["arsenal_2"])
    candidate_frame = workshop_rating.rated_performances(
        names=["arsenal_2"], config_dir=tmp_path
    )
    assert live_frame["rating"].equals(candidate_frame["rating"])
