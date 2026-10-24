"""Run the analytics engine over histories built from real career data."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, cast

from src.analytics_engine import AnalyticsEngine

if TYPE_CHECKING:
    from pathlib import Path

    from tests.data.conftest import CareerRecords, ProjectBuilder, RatedPerformance

    from src.contracts.backend import MatchOverviewPayload, PlayerPerformancePayload

_HISTORY_MATCHES = 40


def test_form_and_reliable_ratings_on_real_histories(
    career_name: str,
    careers: dict[str, CareerRecords],
    build_career_project: ProjectBuilder,
    project_root: Path,
) -> None:
    """Form scores and reliable ratings are well formed for a real, rated career."""
    manager = build_career_project(career_name, matches=_HISTORY_MATCHES, rated=True)
    assert manager.load_career(careers[career_name].club) is True
    histories = manager.get_player_rating_histories()
    engine = AnalyticsEngine(project_root)

    forms = engine.calculate_form_scores(histories)
    assert len(forms) == len(histories)
    for form, history in zip(forms, histories, strict=True):
        assert form["player_id"] == history["player_id"]
        assert form["rated_count"] == len(history["appearances"])
        if form["form_score"] is not None:
            assert -1.0 <= form["form_score"] <= 1.0

    reliable = engine.calculate_reliable_ratings(histories)
    expected_counts = {
        h["player_id"]: len(h["appearances"]) for h in histories if h["appearances"]
    }
    assert reliable, "no player ended up with a reliable rating"
    assert {pid: r["n"] for pid, r in reliable.items()} == expected_counts
    for rating in reliable.values():
        assert math.isfinite(rating["rating"])
        assert 0.0 <= rating["rating"] <= 10.0
        assert rating["std_error"] > 0.0


def test_engine_routes_performances_like_the_service(
    rated_performances: list[RatedPerformance], project_root: Path
) -> None:
    """The engine's GK/outfield routing and config loading match the service."""
    engine = AnalyticsEngine(project_root)
    mismatches = []
    for r in rated_performances[::50]:
        perf = cast(
            "PlayerPerformancePayload",
            {k: v for k, v in r.performance.items() if k != "match_rating"},
        )
        overview = cast("MatchOverviewPayload", r.match_data)
        got = engine.calculate_match_rating(
            perf, overview, r.match_data["half_length"], r.club
        )
        if got != r.rating:
            mismatches.append(f"{r.career} match {r.match_id} player {r.player_id}")
    assert not mismatches, mismatches[:5]
