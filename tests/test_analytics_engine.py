"""Tests for the AnalyticsEngine orchestration and routing layer."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.analytics_engine import AnalyticsEngine
from src.contracts.analytics import (
    PlayerRatingHistory,
    RatedAppearance,
    ReliableRating,
)
from src.services.analytics.reliable_rating_service import ReliableRatingService

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


def _form_history(
    player_id: int, ratings: list[float], missed: int = 0
) -> PlayerRatingHistory:
    """Return a rating history with chronological appearances for the ratings."""
    return PlayerRatingHistory(
        player_id=player_id,
        player_name=f"Player {player_id}",
        appearances=[
            RatedAppearance(
                match_id=i + 1,
                in_game_date=dt.datetime(2031, 8, 1) + dt.timedelta(days=7 * i),
                rating=rating,
            )
            for i, rating in enumerate(ratings)
        ],
        matches_since_last_rated=missed,
    )


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
    """Each config file is loaded once; a second call reuses the cached service."""
    loaded_files: list[str] = []
    original_load = AnalyticsEngine._load_config

    def counting_load(self: AnalyticsEngine, filename: str) -> object:
        """Delegate to the original loader while recording requested files."""
        loaded_files.append(filename)
        return original_load(self, filename)

    monkeypatch.setattr(AnalyticsEngine, "_load_config", counting_load)

    engine = AnalyticsEngine(_PROJECT_ROOT)
    engine.calculate_match_rating(
        _gk_performance(), _match_overview(), 6, "Valencia CF"
    )
    first_service = engine._match_ratings_service
    engine.calculate_match_rating(
        _gk_performance(), _match_overview(), 6, "Valencia CF"
    )

    assert sorted(loaded_files) == [
        "performance_means_stds.json",
        "performance_weights.json",
    ]
    assert first_service is not None
    assert engine._match_ratings_service is first_service


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


def test_calculate_form_scores_returns_one_form_per_history_in_order(
    tmp_path: Path,
) -> None:
    """Each history yields one PlayerForm, in the order the histories were given."""
    engine = AnalyticsEngine(tmp_path)
    histories = [
        _form_history(3, [6.0, 6.5, 7.0]),
        _form_history(1, [7.0, 7.5, 8.0]),
        _form_history(2, [5.0, 5.5, 6.0]),
    ]

    result = engine.calculate_form_scores(histories)

    assert [form["player_id"] for form in result] == [3, 1, 2]
    assert [form["player_name"] for form in result] == [
        "Player 3",
        "Player 1",
        "Player 2",
    ]


def test_calculate_form_scores_returns_empty_list_for_no_histories(
    tmp_path: Path,
) -> None:
    """An empty history list gives an empty result."""
    engine = AnalyticsEngine(tmp_path)

    result = engine.calculate_form_scores([])

    assert result == []


def test_calculate_form_scores_needs_no_config_directory(tmp_path: Path) -> None:
    """Form scoring works with no config directory, unlike match ratings."""
    engine = AnalyticsEngine(tmp_path)

    result = engine.calculate_form_scores([_form_history(1, [7.0, 7.5, 8.0])])

    assert result[0]["rated_count"] == 3
    assert result[0]["current"] is not None


def test_calculate_form_scores_delegates_each_history_to_form_service() -> None:
    """Every history is passed to the form service and its results are returned."""
    engine = AnalyticsEngine(_PROJECT_ROOT)
    form_a, form_b = MagicMock(), MagicMock()
    mock_svc = MagicMock()
    mock_svc.calculate_player_form.side_effect = [form_a, form_b]
    engine._form_scores_service = mock_svc
    histories = [_form_history(1, [6.0] * 3), _form_history(2, [7.0] * 3)]

    result = engine.calculate_form_scores(histories)

    assert result == [form_a, form_b]
    called_with = [c.args[0] for c in mock_svc.calculate_player_form.call_args_list]
    assert called_with == histories


def test_calculate_form_scores_caches_service_after_first_call(
    tmp_path: Path,
) -> None:
    """The form service is created lazily once and reused on later calls."""
    engine = AnalyticsEngine(tmp_path)
    assert engine._form_scores_service is None

    engine.calculate_form_scores([_form_history(1, [6.0] * 3)])
    first_service = engine._form_scores_service
    engine.calculate_form_scores([_form_history(1, [6.0] * 3)])

    assert first_service is not None
    assert engine._form_scores_service is first_service


def test_calculate_reliable_ratings_returns_ratings_keyed_by_player_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each rated player gets an entry keyed by id, with values from the service."""
    monkeypatch.setattr(ReliableRatingService, "PRIOR_VARIANCE", 0.25)
    monkeypatch.setattr(ReliableRatingService, "OBSERVATION_VARIANCE", 0.58)
    monkeypatch.setattr(ReliableRatingService, "SEASON_DRIFT_VARIANCE", 0.0)
    engine = AnalyticsEngine(tmp_path)
    histories = [_form_history(3, [8.0]), _form_history(1, [8.0, 8.0])]

    result = engine.calculate_reliable_ratings(histories)

    assert set(result) == {1, 3}
    assert result[3]["player_id"] == 3
    assert result[3]["n"] == 1
    assert result[3]["rating"] == pytest.approx(6.60241, abs=1e-5)
    assert result[1]["n"] == 2
    assert result[1]["rating"] == pytest.approx(6.92593, abs=1e-5)


def test_calculate_reliable_ratings_omits_players_with_no_rated_appearances(
    tmp_path: Path,
) -> None:
    """Players without rated appearances are left out rather than given the prior."""
    engine = AnalyticsEngine(tmp_path)
    histories = [_form_history(1, [7.0, 7.5]), _form_history(2, [])]

    result = engine.calculate_reliable_ratings(histories)

    assert set(result) == {1}
    assert result.get(2) is None


def test_calculate_reliable_ratings_returns_empty_dict_for_no_histories(
    tmp_path: Path,
) -> None:
    """An empty history list gives an empty result."""
    engine = AnalyticsEngine(tmp_path)

    result = engine.calculate_reliable_ratings([])

    assert result == {}


def test_calculate_reliable_ratings_needs_no_config_directory(tmp_path: Path) -> None:
    """Reliable ratings work with no config directory, unlike match ratings."""
    engine = AnalyticsEngine(tmp_path)

    result = engine.calculate_reliable_ratings([_form_history(1, [7.0, 7.5, 8.0])])

    assert result[1]["n"] == 3


def test_calculate_reliable_ratings_delegates_each_history_and_drops_none() -> None:
    """Every history goes to the service and None results are dropped."""
    engine = AnalyticsEngine(_PROJECT_ROOT)
    rating_a = ReliableRating(player_id=1, rating=6.5, n=3, std_error=0.3)
    rating_c = ReliableRating(player_id=3, rating=7.0, n=5, std_error=0.2)
    mock_svc = MagicMock()
    mock_svc.calculate_player_rating.side_effect = [rating_a, None, rating_c]
    engine._reliable_rating_service = mock_svc
    histories = [
        _form_history(1, [6.0] * 3),
        _form_history(2, []),
        _form_history(3, [7.0] * 5),
    ]

    result = engine.calculate_reliable_ratings(histories)

    assert result == {1: rating_a, 3: rating_c}
    called_with = [c.args[0] for c in mock_svc.calculate_player_rating.call_args_list]
    assert called_with == histories


def test_calculate_reliable_ratings_caches_service_after_first_call(
    tmp_path: Path,
) -> None:
    """The reliable rating service is created lazily once and reused."""
    engine = AnalyticsEngine(tmp_path)
    assert engine._reliable_rating_service is None

    engine.calculate_reliable_ratings([_form_history(1, [6.0] * 3)])
    first_service = engine._reliable_rating_service
    engine.calculate_reliable_ratings([_form_history(1, [6.0] * 3)])

    assert first_service is not None
    assert engine._reliable_rating_service is first_service
