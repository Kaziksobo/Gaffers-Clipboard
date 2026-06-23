"""Tests for domain schema validators and business rules in schemas.py."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from src.schemas import (
    CareerMetadata,
    FinancialSnapshot,
    GKAttributeSnapshot,
    GoalkeeperPerformance,
    InjuryRecord,
    MatchData,
    MatchStats,
    OutfieldPlayerPerformance,
    Player,
)

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _gk_snapshot_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid GKAttributeSnapshot payload dict."""
    return {
        "position_type": "GK",
        "datetime": dt.datetime(2024, 8, 1),
        "in_game_date": "01/08/24",
        "diving": 75,
        "handling": 72,
        "kicking": 68,
        "reflexes": 80,
        "positioning": 73,
        **overrides,
    }


def _gk_snapshot(**overrides: object) -> GKAttributeSnapshot:
    """Return a valid GKAttributeSnapshot instance with optional overrides."""
    return GKAttributeSnapshot.model_validate(_gk_snapshot_payload(**overrides))


def _match_stats_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid MatchStats payload dict."""
    return {
        "possession": 55,
        "ball_recovery": 20,
        "shots": 10,
        "xg": 1.5,
        "passes": 300,
        "tackles": 15,
        "tackles_won": 10,
        "interceptions": 5,
        "saves": 3,
        "fouls_committed": 4,
        "offsides": 2,
        "corners": 3,
        "free_kicks": 5,
        "penalty_kicks": 0,
        "yellow_cards": 1,
        **overrides,
    }


def _gk_perf_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid GoalkeeperPerformance payload dict."""
    return {
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
        "player_id": 1,
        **overrides,
    }


def _outfield_perf_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid OutfieldPlayerPerformance payload dict."""
    return {
        "positions_played": ["CM"],
        "goals": 0,
        "assists": 1,
        "shots": 2,
        "shot_accuracy": 50,
        "passes": 40,
        "pass_accuracy": 85,
        "dribbles": 3,
        "dribble_success_rate": 67,
        "tackles": 2,
        "tackle_success_rate": 50,
        "offsides": 0,
        "fouls_committed": 1,
        "possession_won": 2,
        "possession_lost": 3,
        "minutes_played": 90,
        "distance_covered": 10.0,
        "distance_sprinted": 2.5,
        "player_id": 1,
        **overrides,
    }


def _player_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid Player payload dict."""
    return {
        "id": 1,
        "name": "Test Player",
        "nationality": "Spain",
        "age": 25,
        "height": "6'0\"",
        "weight": 175,
        "positions": ["CM"],
        "attribute_history": [],
        "financial_history": [],
        "injury_history": [],
        "sold": False,
        "date_sold": None,
        "loaned": False,
        **overrides,
    }


def _financial_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid FinancialSnapshot payload dict."""
    return {
        "datetime": dt.datetime(2024, 8, 1),
        "in_game_date": "01/08/24",
        "wage": 50000,
        "market_value": 5000000,
        "contract_length": 3,
        "release_clause": 0,
        "sell_on_clause": 0,
        **overrides,
    }


def _career_meta_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid CareerMetadata payload dict."""
    return {
        "career_id": 1,
        "club_name": "Valencia CF",
        "folder_name": "valencia_cf_1",
        "manager_name": "Ruben Baraja",
        "created_at": dt.datetime(2024, 7, 1),
        "starting_season": "24/25",
        "half_length": 6,
        "difficulty": "Professional",
        "league": "la liga",
        "competitions": [],
        **overrides,
    }


# ---------------------------------------------------------------------------
# Date parsing (tested via GKAttributeSnapshot.in_game_date)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("date_string", "expected_year", "expected_month", "expected_day"),
    [
        ("01/08/24", 2024, 8, 1),
        ("01/08/2024", 2024, 8, 1),
        ("2024-08-01T00:00:00", 2024, 8, 1),
    ],
)
def test_in_game_date_accepts_valid_formats(
    date_string: str,
    expected_year: int,
    expected_month: int,
    expected_day: int,
) -> None:
    """Valid date strings in dd/mm/yy, dd/mm/yyyy, and ISO format parse correctly."""
    snapshot = _gk_snapshot(in_game_date=date_string)

    assert snapshot.in_game_date.year == expected_year
    assert snapshot.in_game_date.month == expected_month
    assert snapshot.in_game_date.day == expected_day


def test_in_game_date_rejects_invalid_format() -> None:
    """An unrecognised date string raises a ValidationError."""
    with pytest.raises(ValidationError):
        GKAttributeSnapshot.model_validate(
            _gk_snapshot_payload(in_game_date="not-a-date")
        )


def test_in_game_date_rejects_non_string_type() -> None:
    """A non-string, non-datetime value for a date field raises ValidationError."""
    with pytest.raises(ValidationError):
        GKAttributeSnapshot.model_validate(
            _gk_snapshot_payload(in_game_date=20240801)
        )


# ---------------------------------------------------------------------------
# MatchStats
# ---------------------------------------------------------------------------


def test_match_stats_rejects_tackles_won_exceeding_tackles() -> None:
    """tackles_won greater than tackles raises a ValidationError."""
    with pytest.raises(ValidationError):
        MatchStats.model_validate(_match_stats_payload(tackles=10, tackles_won=11))


def test_match_stats_accepts_tackles_won_equal_to_tackles() -> None:
    """tackles_won equal to tackles is valid — every tackle was won."""
    stats = MatchStats.model_validate(_match_stats_payload(tackles=10, tackles_won=10))

    assert stats.tackles_won == stats.tackles


# ---------------------------------------------------------------------------
# GoalkeeperPerformance
# ---------------------------------------------------------------------------


def test_gk_performance_rejects_shots_on_target_exceeding_shots_against() -> None:
    """shots_on_target greater than shots_against raises a ValidationError."""
    with pytest.raises(ValidationError):
        GoalkeeperPerformance.model_validate(
            _gk_perf_payload(shots_against=5, shots_on_target=6)
        )


def test_gk_performance_rejects_saves_exceeding_shots_on_target() -> None:
    """Saves greater than shots_on_target raises a ValidationError."""
    with pytest.raises(ValidationError):
        GoalkeeperPerformance.model_validate(
            _gk_perf_payload(shots_on_target=3, saves=4)
        )


def test_gk_performance_accepts_saves_equal_to_shots_on_target() -> None:
    """Saves equal to shots_on_target is valid — every on-target shot was saved."""
    perf = GoalkeeperPerformance.model_validate(
        _gk_perf_payload(shots_on_target=3, saves=3)
    )

    assert perf.saves == perf.shots_on_target


def test_gk_performance_accepts_shots_on_target_equal_to_shots_against() -> None:
    """shots_on_target equal to shots_against is valid — all shots were on target."""
    perf = GoalkeeperPerformance.model_validate(
        _gk_perf_payload(shots_against=4, shots_on_target=4, saves=4)
    )

    assert perf.shots_on_target == perf.shots_against


# ---------------------------------------------------------------------------
# OutfieldPlayerPerformance
# ---------------------------------------------------------------------------


def test_outfield_rejects_distance_sprinted_exceeding_covered() -> None:
    """distance_sprinted greater than distance_covered raises a ValidationError."""
    with pytest.raises(ValidationError):
        OutfieldPlayerPerformance.model_validate(
            _outfield_perf_payload(distance_covered=5.0, distance_sprinted=5.1)
        )


def test_outfield_accepts_distance_sprinted_equal_to_covered() -> None:
    """distance_sprinted equal to distance_covered is valid."""
    perf = OutfieldPlayerPerformance.model_validate(
        _outfield_perf_payload(distance_covered=5.0, distance_sprinted=5.0)
    )

    assert perf.distance_sprinted == perf.distance_covered


# ---------------------------------------------------------------------------
# Player — sold/date_sold consistency
# ---------------------------------------------------------------------------


def test_player_rejects_sold_without_date_sold() -> None:
    """A player flagged as sold with no date_sold raises a ValidationError."""
    with pytest.raises(ValidationError):
        Player.model_validate(_player_payload(sold=True, date_sold=None))


def test_player_accepts_sold_with_date_sold() -> None:
    """A player flagged as sold with a valid date_sold is accepted."""
    player = Player.model_validate(
        _player_payload(sold=True, date_sold="15/08/24")
    )

    assert player.sold is True
    assert player.date_sold is not None


def test_player_accepts_not_sold_without_date_sold() -> None:
    """A player not yet sold with no date_sold is valid."""
    player = Player.model_validate(_player_payload(sold=False, date_sold=None))

    assert player.sold is False


# ---------------------------------------------------------------------------
# Player — is_goalkeeper property
# ---------------------------------------------------------------------------


def test_player_is_goalkeeper_returns_true_when_gk_in_positions() -> None:
    """is_goalkeeper is True when GK appears in the positions list."""
    player = Player.model_validate(_player_payload(positions=["GK"]))

    assert player.is_goalkeeper is True


def test_player_is_goalkeeper_returns_false_when_no_gk_in_positions() -> None:
    """is_goalkeeper is False when GK does not appear in the positions list."""
    player = Player.model_validate(_player_payload(positions=["CB", "CDM"]))

    assert player.is_goalkeeper is False


# ---------------------------------------------------------------------------
# Player — current_attributes property
# ---------------------------------------------------------------------------


def test_player_current_attributes_returns_most_recent_snapshot() -> None:
    """current_attributes returns the snapshot with the most recent datetime."""
    early = _gk_snapshot(
        datetime=dt.datetime(2024, 1, 1), in_game_date="01/01/24"
    )
    late = _gk_snapshot(
        datetime=dt.datetime(2024, 8, 1), in_game_date="01/08/24"
    )
    player = Player.model_validate(
        _player_payload(positions=["GK"], attribute_history=[early, late])
    )

    assert player.current_attributes == late


def test_player_current_attributes_returns_none_when_history_is_empty() -> None:
    """current_attributes is None when no attribute snapshots have been recorded."""
    player = Player.model_validate(_player_payload(attribute_history=[]))

    assert player.current_attributes is None


# ---------------------------------------------------------------------------
# Player — height pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valid_height",
    [
        "5'8\"",
        "6'0\"",
        "6'11\"",
        "5'11\"",
    ],
)
def test_player_accepts_valid_height_format(valid_height: str) -> None:
    r"""Valid height strings in X'Y" format are accepted without error."""
    player = Player.model_validate(_player_payload(height=valid_height))

    assert player.height == valid_height


@pytest.mark.parametrize(
    "invalid_height",
    [
        "6ft 2in",
        "180cm",
        "6'2",
        "6 2\"",
        "",
    ],
)
def test_player_rejects_invalid_height_format(invalid_height: str) -> None:
    r"""Height strings that do not match X'Y" format raise a ValidationError."""
    with pytest.raises(ValidationError):
        Player.model_validate(_player_payload(height=invalid_height))


# ---------------------------------------------------------------------------
# FinancialSnapshot — comma-formatted string parsing
# ---------------------------------------------------------------------------


def test_financial_snapshot_parses_comma_formatted_wage() -> None:
    """A comma-formatted wage string like '50,000' is parsed to the integer 50000."""
    snapshot = FinancialSnapshot.model_validate(_financial_payload(wage="50,000"))

    assert snapshot.wage == 50000


def test_financial_snapshot_parses_comma_formatted_market_value() -> None:
    """A comma-formatted market_value string like '1,500,000' parses to 1500000."""
    snapshot = FinancialSnapshot.model_validate(
        _financial_payload(market_value="1,500,000")
    )

    assert snapshot.market_value == 1500000


def test_financial_snapshot_rejects_empty_required_field() -> None:
    """An empty string for a required financial field raises a ValidationError."""
    with pytest.raises(ValidationError):
        FinancialSnapshot.model_validate(_financial_payload(wage=""))


def test_financial_snapshot_defaults_empty_optional_field_to_zero() -> None:
    """An empty string for an optional field like release_clause defaults to 0."""
    snapshot = FinancialSnapshot.model_validate(
        _financial_payload(release_clause="")
    )

    assert snapshot.release_clause == 0


# ---------------------------------------------------------------------------
# CareerMetadata — league and competition normalisation
# ---------------------------------------------------------------------------


def test_career_metadata_title_cases_league() -> None:
    """The league field is title-cased regardless of the original input casing."""
    meta = CareerMetadata.model_validate(_career_meta_payload(league="la liga"))

    assert meta.league == "La Liga"


def test_career_metadata_title_cases_competitions() -> None:
    """Each entry in the competitions list is title-cased."""
    meta = CareerMetadata.model_validate(
        _career_meta_payload(
            competitions=["la liga", "uefa champions league"]
        )
    )

    assert "La Liga" in meta.competitions
    assert "UEFA Champions League" in meta.competitions


def test_career_metadata_rejects_empty_league() -> None:
    """A whitespace-only league value raises a ValidationError."""
    with pytest.raises(ValidationError):
        CareerMetadata.model_validate(_career_meta_payload(league="   "))


def test_career_metadata_rejects_invalid_starting_season_format() -> None:
    """A starting_season value that does not match yy/yy raises a ValidationError."""
    with pytest.raises(ValidationError):
        CareerMetadata.model_validate(
            _career_meta_payload(starting_season="2024/2025")
        )


def test_career_metadata_accepts_valid_starting_season() -> None:
    """A valid starting_season in yy/yy format is accepted without error."""
    meta = CareerMetadata.model_validate(_career_meta_payload(starting_season="24/25"))

    assert meta.starting_season == "24/25"


# ---------------------------------------------------------------------------
# CareerMetadata — edge-case validators
# ---------------------------------------------------------------------------


def test_career_metadata_raises_when_league_is_not_a_string() -> None:
    """A non-string league value raises a ValidationError."""
    with pytest.raises(ValidationError):
        CareerMetadata.model_validate(_career_meta_payload(league=42))


def test_career_metadata_normalises_none_competitions_to_empty_list() -> None:
    """A None competitions value is coerced to an empty list."""
    meta = CareerMetadata.model_validate(_career_meta_payload(competitions=None))

    assert meta.competitions == []


def test_career_metadata_raises_when_competitions_is_not_a_list() -> None:
    """A non-list competitions value raises a ValidationError."""
    with pytest.raises(ValidationError):
        CareerMetadata.model_validate(_career_meta_payload(competitions="La Liga"))


def test_career_metadata_raises_when_a_competition_item_is_not_a_string() -> None:
    """A non-string item inside the competitions list raises a ValidationError."""
    with pytest.raises(ValidationError):
        CareerMetadata.model_validate(_career_meta_payload(competitions=[42]))


# ---------------------------------------------------------------------------
# parse_in_game_date — datetime pass-through (FinancialSnapshot, InjuryRecord,
# MatchData, GKAttributeSnapshot)
# ---------------------------------------------------------------------------


def test_financial_snapshot_accepts_datetime_in_game_date() -> None:
    """FinancialSnapshot.in_game_date accepts a datetime object directly."""
    date = dt.datetime(2024, 8, 1)
    snapshot = FinancialSnapshot.model_validate(
        _financial_payload(in_game_date=date)
    )

    assert snapshot.in_game_date == date


def test_financial_snapshot_rejects_invalid_in_game_date_string() -> None:
    """FinancialSnapshot.in_game_date raises ValidationError for an unparseable string."""
    with pytest.raises(ValidationError):
        FinancialSnapshot.model_validate(_financial_payload(in_game_date="not-a-date"))


def test_financial_snapshot_rejects_non_numeric_money_string() -> None:
    """FinancialSnapshot raises ValidationError for a non-numeric wage string."""
    with pytest.raises(ValidationError):
        FinancialSnapshot.model_validate(_financial_payload(wage="twenty-thousand"))


def _injury_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid InjuryRecord payload dict."""
    return {
        "datetime": dt.datetime(2024, 8, 1),
        "in_game_date": "01/08/24",
        "injury_detail": "Hamstring strain",
        "time_out": 2,
        "time_out_unit": "Weeks",
        **overrides,
    }


def test_injury_record_accepts_datetime_in_game_date() -> None:
    """InjuryRecord.in_game_date accepts a datetime object directly."""
    date = dt.datetime(2024, 9, 10)
    record = InjuryRecord.model_validate(_injury_payload(in_game_date=date))

    assert record.in_game_date == date


def test_injury_record_rejects_invalid_in_game_date_string() -> None:
    """InjuryRecord.in_game_date raises ValidationError for an unparseable string."""
    with pytest.raises(ValidationError):
        InjuryRecord.model_validate(_injury_payload(in_game_date="bad-date"))


def _match_data_payload(**overrides: object) -> dict[str, object]:
    """Return a minimal valid MatchData payload dict."""
    return {
        "in_game_date": "20/08/24",
        "half_length": 6,
        "competition": "La Liga",
        "home_team_name": "Valencia CF",
        "away_team_name": "Sevilla",
        "home_score": 2,
        "away_score": 1,
        "home_stats": _match_stats_payload(),
        "away_stats": _match_stats_payload(),
        **overrides,
    }


def test_match_data_accepts_datetime_in_game_date() -> None:
    """MatchData.in_game_date accepts a datetime object directly."""
    date = dt.datetime(2024, 8, 20)
    match = MatchData.model_validate(_match_data_payload(in_game_date=date))

    assert match.in_game_date == date


def test_match_data_rejects_invalid_in_game_date_string() -> None:
    """MatchData.in_game_date raises ValidationError for an unparseable string."""
    with pytest.raises(ValidationError):
        MatchData.model_validate(_match_data_payload(in_game_date="not-a-date"))


def test_gk_snapshot_accepts_datetime_in_game_date() -> None:
    """GKAttributeSnapshot.in_game_date accepts a datetime object directly."""
    date = dt.datetime(2024, 8, 1)
    snapshot = GKAttributeSnapshot.model_validate(
        _gk_snapshot_payload(in_game_date=date)
    )

    assert snapshot.in_game_date == date


# ---------------------------------------------------------------------------
# Player.parse_sold_date — datetime pass-through and invalid string
# ---------------------------------------------------------------------------


def test_player_parse_sold_date_accepts_datetime_directly() -> None:
    """Player.date_sold accepts a datetime object directly without re-parsing."""
    date = dt.datetime(2024, 8, 15)
    player = Player.model_validate(_player_payload(sold=True, date_sold=date))

    assert player.date_sold == date


def test_player_parse_sold_date_rejects_invalid_string() -> None:
    """Player.date_sold raises ValidationError for an unparseable date string."""
    with pytest.raises(ValidationError):
        Player.model_validate(_player_payload(sold=True, date_sold="not-a-date"))
