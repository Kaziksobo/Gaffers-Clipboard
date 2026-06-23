"""Tests for shared utility helpers in src/utils.py."""

from __future__ import annotations

import pytest

from src.utils import (
    capitalize_competition_name,
    derive_season,
    normalize_team_name,
    safe_float_conversion,
    safe_int_conversion,
    safe_normalize_name,
    scale_coordinates,
)

# ---------------------------------------------------------------------------
# safe_int_conversion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("abc", None),
        ("42", 42),
        ("  7 ", 7),
        (5, 5),
        (3.9, 3),
        (0, 0),
    ],
)
def test_safe_int_conversion(value: object, expected: int | None) -> None:
    """safe_int_conversion returns the expected int or None for each input type."""
    assert safe_int_conversion(value) == expected  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# safe_float_conversion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("abc", None),
        ("3.14", 3.14),
        ("  2.0  ", 2.0),
        (5, 5.0),
        (1.5, 1.5),
        (0, 0.0),
    ],
)
def test_safe_float_conversion(value: object, expected: float | None) -> None:
    """safe_float_conversion returns the expected float or None for each input type."""
    assert safe_float_conversion(value) == expected  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# derive_season
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("date_str", "expected_season"),
    [
        ("01/07/24", "24/25"),
        ("31/08/24", "24/25"),
        ("01/06/24", "23/24"),
        ("15/01/25", "24/25"),
        ("30/06/25", "24/25"),
    ],
)
def test_derive_season(date_str: str, expected_season: str) -> None:
    """derive_season returns the correct football season string for a date."""
    assert derive_season(date_str) == expected_season


# ---------------------------------------------------------------------------
# safe_normalize_name
# ---------------------------------------------------------------------------


def test_safe_normalize_name_returns_casefolded_stripped_string() -> None:
    """safe_normalize_name casefolds and strips a valid name string."""
    assert safe_normalize_name("  Valencia CF  ") == "valencia cf"


def test_safe_normalize_name_returns_none_for_empty_string() -> None:
    """safe_normalize_name returns None for empty or whitespace-only input."""
    assert safe_normalize_name("   ") is None
    assert safe_normalize_name("") is None


def test_safe_normalize_name_returns_none_for_non_string() -> None:
    """safe_normalize_name returns None for non-string inputs."""
    assert safe_normalize_name(123) is None  # type: ignore[arg-type]
    assert safe_normalize_name(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# capitalize_competition_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("la liga", "La Liga"),
        ("uefa champions league", "UEFA Champions League"),
        ("FA cup", "FA Cup"),
        ("dfl supercup", "DFL Supercup"),
        ("efl championship", "EFL Championship"),
        ("copa del rey (copa)", "Copa Del Rey Copa"),
        ("", ""),
    ],
)
def test_capitalize_competition_name(raw: str, expected: str) -> None:
    """capitalize_competition_name title-cases words and uppercases known acronyms."""
    assert capitalize_competition_name(raw) == expected


# ---------------------------------------------------------------------------
# normalize_team_name
# ---------------------------------------------------------------------------


def test_normalize_team_name_returns_reference_on_exact_match() -> None:
    """normalize_team_name returns the reference name on a case-insensitive match."""
    references = ["Valencia CF", "Real Madrid"]
    assert normalize_team_name("Valencia CF", references) == "Valencia CF"


def test_normalize_team_name_strips_fc_suffix_for_match() -> None:
    """normalize_team_name matches across FC/CF prefix and suffix differences."""
    references = ["Valencia CF", "FC Barcelona"]
    assert normalize_team_name("Valencia", references) == "Valencia CF"
    assert normalize_team_name("Barcelona", references) == "FC Barcelona"


def test_normalize_team_name_is_case_insensitive() -> None:
    """normalize_team_name comparison ignores case differences."""
    references = ["Real Madrid"]
    assert normalize_team_name("real madrid", references) == "Real Madrid"


def test_normalize_team_name_returns_original_when_no_match() -> None:
    """normalize_team_name returns the original target when no reference matches."""
    references = ["Valencia CF", "Real Madrid"]
    assert normalize_team_name("Atletico Madrid", references) == "Atletico Madrid"


def test_normalize_team_name_raises_for_empty_target() -> None:
    """normalize_team_name raises ValueError when the target name is empty."""
    with pytest.raises(ValueError, match="Target name must be a non-empty string"):
        normalize_team_name("", ["Valencia CF"])


# ---------------------------------------------------------------------------
# scale_coordinates
# ---------------------------------------------------------------------------


def test_scale_coordinates_scales_leaf_roi() -> None:
    """scale_coordinates converts normalised ROI values to pixel coordinates."""
    coords = {
        "scoreboard": {"score": {"x1": 0.5, "y1": 0.25, "x2": 0.75, "y2": 0.5}}
    }
    result = scale_coordinates(coords, 1920, 1080)
    assert result["scoreboard"]["score"] == {
        "x1": 960,
        "y1": 270,
        "x2": 1440,
        "y2": 540,
    }


def test_scale_coordinates_handles_nested_structure() -> None:
    """scale_coordinates recursively descends into nested coordinate branches."""
    coords = {
        "match": {
            "home": {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 1.0},
            "away": {"x1": 0.5, "y1": 0.0, "x2": 1.0, "y2": 1.0},
        }
    }
    result = scale_coordinates(coords, 1000, 500)
    assert result["match"]["home"] == {"x1": 0, "y1": 0, "x2": 500, "y2": 500}
    assert result["match"]["away"] == {"x1": 500, "y1": 0, "x2": 1000, "y2": 500}
