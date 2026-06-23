"""Integration tests for non-OCR career, player, and match persistence flows."""

from pathlib import Path

from src.data_manager import DataManager
from src.services.app.match_service import MatchService


def test_non_ocr_player_lifecycle_persists_across_reload(
    loaded_data_manager: DataManager, tmp_path: Path
) -> None:
    """Create a career and run player mutations without OCR dependencies."""
    loaded_data_manager.add_or_update_player(
        player_ui_data={
            "name": "Giorgi Mamardashvili",
            "age": 23,
            "height": "6'6\"",
            "weight": 197,
            "country": "Georgia",
            "in_game_date": "01/08/24",
            "diving": 80,
            "handling": 79,
            "kicking": 78,
            "reflexes": 82,
            "positioning": 77,
        },
        position="GK",
        in_game_date="01/08/24",
        is_gk=True,
    )

    loaded_data_manager.add_financial_data(
        player_name="Giorgi Mamardashvili",
        financial_data={
            "wage": "50,000",
            "market_value": "25,000,000",
            "contract_length": 4,
            "release_clause": "0",
            "sell_on_clause": 0,
        },
        in_game_date="05/08/24",
    )
    loaded_data_manager.add_injury_record(
        player_name="Giorgi Mamardashvili",
        injury_data={
            "in_game_date": "10/08/24",
            "injury_detail": "Sprained ankle",
            "time_out": 2,
            "time_out_unit": "Weeks",
        },
    )

    loaded_data_manager.loan_out_player("Giorgi Mamardashvili")
    loaded_data_manager.return_loan_player("Giorgi Mamardashvili")
    loaded_data_manager.sell_player("Giorgi Mamardashvili", "15/08/24")

    reloaded = DataManager(project_root=tmp_path)
    assert reloaded.load_career("Valencia CF") is True
    player = reloaded.find_player_by_name("Giorgi Mamardashvili")

    assert player is not None
    assert player.is_goalkeeper is True
    assert len(player.attribute_history) == 1
    assert len(player.financial_history) == 1
    assert len(player.injury_history) == 1
    assert player.sold is True
    assert player.loaned is False
    assert player.date_sold is not None


def test_selling_player_clears_loaned_flag(loaded_data_manager: DataManager) -> None:
    """Selling a loaned player should always clear the loaned status."""
    loaded_data_manager.add_or_update_player(
        player_ui_data={
            "name": "Giorgi Mamardashvili",
            "age": 23,
            "height": "6'6\"",
            "weight": 197,
            "country": "Georgia",
            "in_game_date": "01/08/24",
            "diving": 80,
            "handling": 79,
            "kicking": 78,
            "reflexes": 82,
            "positioning": 77,
        },
        position="GK",
        in_game_date="01/08/24",
        is_gk=True,
    )

    loaded_data_manager.loan_out_player("Giorgi Mamardashvili")
    player = loaded_data_manager.find_player_by_name("Giorgi Mamardashvili")
    assert player is not None
    assert player.loaned is True

    loaded_data_manager.sell_player("Giorgi Mamardashvili", "15/08/24")
    player = loaded_data_manager.find_player_by_name("Giorgi Mamardashvili")
    assert player is not None
    assert player.sold is True
    assert player.loaned is False


def test_match_service_saves_match_without_ocr(
    loaded_data_manager: DataManager,
    minimal_team_stats: dict[str, int | float],
) -> None:
    """Match persistence should work from structured payloads only (no OCR)."""
    match_service = MatchService(loaded_data_manager)
    match_service.save_match(
        match_overview={
            "in_game_date": "20/08/24",
            "competition": "La Liga",
            "home_team_name": "Valencia CF",
            "away_team_name": "Sevilla",
            "home_score": 2,
            "away_score": 1,
            "home_stats": minimal_team_stats,
            "away_stats": minimal_team_stats,
        },
        player_performances=[],
    )

    assert len(loaded_data_manager.matches) == 1
    latest = match_service.get_latest_match_in_game_date()
    assert latest is not None
    assert latest.strftime("%d/%m/%y") == "20/08/24"

    reloaded = DataManager(project_root=loaded_data_manager.project_root)
    assert reloaded.load_career("Valencia CF") is True
    assert len(reloaded.matches) == 1
