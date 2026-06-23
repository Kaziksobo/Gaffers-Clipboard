"""Tests for the AnalyticsEngine orchestration and routing layer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.analytics_engine import AnalyticsEngine

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _gk_performance() -> dict[str, object]:
    """Return a minimal valid GK performance payload."""
    return {
        "performance_type": "GK",
        "player_id": 1,
        "shots_against": 5,
        "shots_on_target": 3,
        "saves": 3,
        "goals_conceded": 0,
        "save_success_rate": 100,
        "punch_saves": 0,
        "rush_saves": 0,
        "penalty_saves": 0,
        "penalty_goals_conceded": 0,
        "shoot_out_saves": 0,
        "shoot_out_goals_conceded": 0,
    }


def _outfield_performance(**overrides: object) -> dict[str, object]:
    """Return a minimal valid outfield performance payload with optional overrides."""
    base: dict[str, object] = {
        "performance_type": "Outfield",
        "player_id": 2,
        "positions_played": ["CM"],
        "goals": 0,
        "assists": 1,
        "shots": 2,
        "shot_accuracy": 50,
        "passes": 45,
        "pass_accuracy": 88,
        "dribbles": 5,
        "dribble_success_rate": 80,
        "tackles": 3,
        "tackle_success_rate": 67,
        "offsides": 0,
        "fouls_committed": 1,
        "possession_won": 3,
        "possession_lost": 5,
        "minutes_played": 90,
        "distance_covered": 10.2,
        "distance_sprinted": 2.1,
    }
    return base | overrides


def _match_overview() -> dict[str, object]:
    """Return a minimal valid match overview payload."""
    return {
        "home_team_name": "Valencia CF",
        "away_team_name": "Sevilla",
        "home_score": 1,
        "away_score": 0,
        "home_stats": {"xg": 1.5, "saves": 2, "tackles": 12, "tackles_won": 8},
        "away_stats": {"xg": 0.8, "saves": 4, "tackles": 8, "tackles_won": 5},
    }


def test_calculate_match_rating_raises_when_config_missing(tmp_path: Path) -> None:
    """FileNotFoundError is raised when no config directory exists at project root."""
    engine = AnalyticsEngine(tmp_path)

    with pytest.raises(FileNotFoundError):
        engine.calculate_match_rating(
            _gk_performance(), _match_overview(), 6, "Valencia CF"
        )


def test_calculate_match_rating_raises_for_invalid_json(tmp_path: Path) -> None:
    """JSONDecodeError is raised when a config file contains malformed JSON."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "performance_weights.json").write_text("not valid json")
    (config_dir / "performance_means_stds.json").write_text("{}")

    engine = AnalyticsEngine(tmp_path)

    with pytest.raises(json.JSONDecodeError):
        engine.calculate_match_rating(
            _gk_performance(), _match_overview(), 6, "Valencia CF"
        )


def test_calculate_match_rating_routes_gk_to_gk_pipeline() -> None:
    """GK performance type is routed to calculate_gk_rating, not the outfield path."""
    engine = AnalyticsEngine(_PROJECT_ROOT)
    mock_svc = MagicMock()
    mock_svc.calculate_gk_rating.return_value = 7.5
    engine._match_ratings_service = mock_svc

    result = engine.calculate_match_rating(
        _gk_performance(), _match_overview(), 6, "Valencia CF"
    )

    assert result == 7.5
    mock_svc.calculate_gk_rating.assert_called_once()
    mock_svc.calculate_outfield_rating.assert_not_called()


def test_calculate_match_rating_routes_outfield_to_outfield_pipeline() -> None:
    """Non-GK performance type is routed to calculate_outfield_rating."""
    engine = AnalyticsEngine(_PROJECT_ROOT)
    mock_svc = MagicMock()
    mock_svc.calculate_outfield_rating.return_value = 6.8
    engine._match_ratings_service = mock_svc

    result = engine.calculate_match_rating(
        _outfield_performance(), _match_overview(), 6, "Valencia CF"
    )

    assert result == 6.8
    mock_svc.calculate_outfield_rating.assert_called_once()
    mock_svc.calculate_gk_rating.assert_not_called()


def test_calculate_match_rating_caches_service_after_first_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config is loaded exactly once; a second call reuses the cached service."""
    load_calls: list[int] = []
    original_load = AnalyticsEngine._load_configuration

    def counting_load(self: AnalyticsEngine) -> None:
        """Delegate to the original loader while counting invocations."""
        load_calls.append(1)
        original_load(self)

    monkeypatch.setattr(AnalyticsEngine, "_load_configuration", counting_load)

    engine = AnalyticsEngine(_PROJECT_ROOT)
    engine.calculate_match_rating(
        _gk_performance(), _match_overview(), 6, "Valencia CF"
    )
    engine.calculate_match_rating(
        _gk_performance(), _match_overview(), 6, "Valencia CF"
    )

    assert len(load_calls) == 1


def test_calculate_match_rating_gk_returns_float_in_valid_range() -> None:
    """A GK rating produced from real config is a float within [0.0, 10.0]."""
    engine = AnalyticsEngine(_PROJECT_ROOT)

    result = engine.calculate_match_rating(
        _gk_performance(), _match_overview(), 6, "Valencia CF"
    )

    assert isinstance(result, float)
    assert 0.0 <= result <= 10.0


def test_calculate_match_rating_outfield_returns_float_in_valid_range() -> None:
    """An outfield rating produced from real config is a float within [0.0, 10.0]."""
    engine = AnalyticsEngine(_PROJECT_ROOT)

    result = engine.calculate_match_rating(
        _outfield_performance(), _match_overview(), 6, "Valencia CF"
    )

    assert isinstance(result, float)
    assert 0.0 <= result <= 10.0


def test_calculate_match_rating_outfield_returns_none_for_low_minutes() -> None:
    """Outfield players with fewer than 10 minutes played receive no rating (None)."""
    engine = AnalyticsEngine(_PROJECT_ROOT)

    result = engine.calculate_match_rating(
        _outfield_performance(minutes_played=5), _match_overview(), 6, "Valencia CF"
    )

    assert result is None
