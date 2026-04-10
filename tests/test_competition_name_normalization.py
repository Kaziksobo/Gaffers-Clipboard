"""Regression coverage for competition-name normalization."""

from src.utils import capitalize_competition_name


def test_capitalize_competition_name_preserves_known_acronyms() -> None:
    """Known football acronyms should remain fully uppercased."""
    assert capitalize_competition_name("uefa europa league") == "UEFA Europa League"
    assert capitalize_competition_name("efl cup") == "EFL Cup"
    assert capitalize_competition_name("fa cup") == "FA Cup"


def test_capitalize_competition_name_handles_apostrophes() -> None:
    """Apostrophe words should not be converted to Women'S style output."""
    assert capitalize_competition_name("women's super league") == "Women's Super League"
    assert capitalize_competition_name("uefa women's cup") == "UEFA Women's Cup"


def test_capitalize_competition_name_handles_hyphen_and_parentheses() -> None:
    """Hyphen tokens should survive and parentheses should be stripped."""
    assert capitalize_competition_name("u-21 efl cup") == "U-21 EFL Cup"
    assert capitalize_competition_name("(uefa) cup") == "UEFA Cup"
