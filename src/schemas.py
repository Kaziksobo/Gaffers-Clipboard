"""Domain schemas and validation contracts for Gaffer's Clipboard.

This module defines the Pydantic models that represent persistent application
data and structured payloads exchanged between services and UI workflows. It
is the single source of truth for field constraints, normalization rules, and
cross-field business validation.

Model groups:
- Player timeline models for attribute snapshots, financial history, injuries,
    and core player identity fields.
- Match models for fixture context, team statistics, and polymorphic player
    performance records.
- Career metadata models for save configuration and lightweight listing views.

Validation strategy:
- Field constraints enforce numeric ranges, text patterns, and required
    structure.
- Date validators accept both UI-entered date strings and ISO timestamps for
    robust JSON round-tripping.
- Model validators enforce internal consistency between related fields.
- Discriminated unions keep polymorphic histories type-safe without losing
    strict validation guarantees.

Keeping these schemas centralized ensures consistent behavior across loading,
saving, and UI-driven service operations.
"""

import contextlib
import datetime as dt
from abc import ABC
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.utils import capitalize_competition_name

# Enums and constants
DifficultyLevel = Literal[
    "Beginner",
    "Amateur",
    "Semi-Pro",
    "Professional",
    "World Class",
    "Legendary",
    "Ultimate",
]
PositionType = Literal[
    "GK",
    "LB",
    "RB",
    "CB",
    "LWB",
    "RWB",
    "CDM",
    "CM",
    "CAM",
    "LM",
    "RM",
    "LW",
    "RW",
    "ST",
    "CF",
]

# Shared numeric bounds
ATTRIBUTE_RATING_MIN = 1
ATTRIBUTE_RATING_MAX = 99

PLAYER_AGE_MIN = 13
PLAYER_AGE_MAX = 60
PLAYER_WEIGHT_MIN = 100
PLAYER_WEIGHT_MAX = 400

FINANCIAL_MIN_VALUE = 0
FINANCIAL_CONTRACT_LENGTH_MIN = 0
FINANCIAL_CONTRACT_LENGTH_MAX = 15
FINANCIAL_SELL_ON_CLAUSE_MIN = 0
FINANCIAL_SELL_ON_CLAUSE_MAX = 100

MATCH_YELLOW_CARDS_MIN = 0
MATCH_YELLOW_CARDS_MAX = 16

# Career metadata bounds
CAREER_HALF_LENGTH_MIN = 4
CAREER_HALF_LENGTH_MAX = 20


class BaseAttributeSnapshot(BaseModel, ABC):
    """Represent a base snapshot of a player's attributes at a specific time.

    Provides common timing and positional fields that are shared across all
    attribute snapshot types.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    datetime: dt.datetime
    in_game_date: dt.datetime
    position: str | None = Field(
        default=None, description="Specific position (e.g. ST, LB)"
    )

    @field_validator("in_game_date", mode="before")
    @classmethod
    def parse_in_game_date(cls, value: str | dt.datetime) -> dt.datetime:
        """Convert string in dd/mm/yy, dd/mm/yyyy or ISO format to datetime object."""
        if isinstance(value, dt.datetime):
            return value

        if isinstance(value, str):
            value = value.strip()

            # 1. Attempt to parse standard ISO format (from JSON load)
            if "T" in value or "-" in value:
                with contextlib.suppress(ValueError):
                    return dt.datetime.fromisoformat(value)
            # 2. Attempt to parse custom UI format (from Tkinter input)
            for date_format in ["%d/%m/%y", "%d/%m/%Y"]:
                with contextlib.suppress(ValueError):
                    return dt.datetime.strptime(value, date_format)

            raise ValueError(
                "Invalid date format. Expected dd/mm/yy, dd/mm/yyyy or ISO, "
                f"got '{value}'"
            )

        raise ValueError(
            f"in_game_date must be a string or datetime, got {type(value)}"
        )


class GKAttributeSnapshot(BaseAttributeSnapshot):
    """Represent a snapshot of a goalkeeper's core attributes at a specific time.

    Captures key goalkeeping skills used to track development and performance
    over a career.
    """

    position_type: Literal["GK"] = Field(
        default="GK", description="Discriminator for GK attributes"
    )
    diving: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    handling: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    kicking: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    reflexes: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    positioning: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)


class OutfieldAttributeSnapshot(BaseAttributeSnapshot):
    """Represent a snapshot of an outfield player's core attributes at a specific time.

    Captures key physical, mental, and technical skills used to track
    development and performance over a career.
    """

    position_type: Literal["Outfield"] = Field(
        default="Outfield", description="Discriminator for Outfield attributes"
    )
    # Physical
    acceleration: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    sprint_speed: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    agility: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    balance: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    jumping: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    stamina: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    strength: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)

    # Mental
    aggression: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    att_position: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    composure: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    interceptions: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    reactions: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    vision: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    defensive_awareness: int = Field(
        ge=ATTRIBUTE_RATING_MIN,
        le=ATTRIBUTE_RATING_MAX,
    )

    # Technical
    ball_control: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    crossing: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    curve: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    dribbling: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    fk_accuracy: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    finishing: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    heading_accuracy: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    long_pass: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    long_shots: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    penalties: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    short_pass: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    shot_power: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    slide_tackle: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    stand_tackle: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)
    volleys: int = Field(ge=ATTRIBUTE_RATING_MIN, le=ATTRIBUTE_RATING_MAX)


class FinancialSnapshot(BaseModel):
    """Represent a snapshot of a player's financial details at a specific time.

    Captures wage, market value, contract terms, and clauses used to track a
    player's financial history over a career.
    """

    datetime: dt.datetime
    in_game_date: dt.datetime
    wage: int = Field(ge=FINANCIAL_MIN_VALUE)
    market_value: int = Field(ge=FINANCIAL_MIN_VALUE)
    contract_length: int = Field(
        default=0,
        ge=FINANCIAL_CONTRACT_LENGTH_MIN,
        le=FINANCIAL_CONTRACT_LENGTH_MAX,
    )
    release_clause: int = Field(default=0, ge=FINANCIAL_MIN_VALUE)
    sell_on_clause: int = Field(
        default=0,
        ge=FINANCIAL_SELL_ON_CLAUSE_MIN,
        le=FINANCIAL_SELL_ON_CLAUSE_MAX,
    )

    @staticmethod
    def _parse_numeric_like(value: int | str | None) -> int | None:
        """Normalize integer-like UI values, including comma-formatted strings."""
        if isinstance(value, int):
            return value

        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            if not cleaned:
                return None
            try:
                return int(cleaned)
            except ValueError as e:
                raise ValueError(
                    f"Expected an integer-like numeric value, got '{value}'"
                ) from e

        return value

    @field_validator("wage", "market_value", mode="before")
    @classmethod
    def parse_required_financial_numbers(cls, value: int | str | None) -> int:
        """Parse required money fields from int or formatted numeric strings."""
        parsed = cls._parse_numeric_like(value)
        if parsed is None:
            raise ValueError("Required financial value cannot be empty.")
        return parsed

    @field_validator(
        "contract_length",
        "release_clause",
        "sell_on_clause",
        mode="before",
    )
    @classmethod
    def parse_optional_financial_numbers(cls, value: int | str | None) -> int:
        """Parse optional money/term fields, defaulting empty values to 0."""
        parsed = cls._parse_numeric_like(value)
        return 0 if parsed is None else parsed

    @field_validator("in_game_date", mode="before")
    @classmethod
    def parse_in_game_date(cls, value: str | dt.datetime) -> dt.datetime:
        """Convert string in dd/mm/yy, dd/mm/yyyy or ISO format to datetime object."""
        if isinstance(value, dt.datetime):
            return value

        if isinstance(value, str):
            value = value.strip()

            # 1. Attempt to parse standard ISO format (from JSON load)
            if "T" in value or "-" in value:
                with contextlib.suppress(ValueError):
                    return dt.datetime.fromisoformat(value)
            # 2. Attempt to parse custom UI format (from Tkinter input)
            for date_format in ["%d/%m/%y", "%d/%m/%Y"]:
                with contextlib.suppress(ValueError):
                    return dt.datetime.strptime(value, date_format)

            raise ValueError(
                "Invalid date format. Expected dd/mm/yy, dd/mm/yyyy or ISO, "
                f"got '{value}'"
            )

        raise ValueError(
            f"in_game_date must be a string or datetime, got {type(value)}"
        )


class InjuryRecord(BaseModel):
    """Represent a single injury record for a player.

    Captures when the injury occurred, what happened, and how long the player
    is expected to be unavailable.
    """

    datetime: dt.datetime
    in_game_date: dt.datetime
    injury_detail: str
    time_out: int = Field(ge=0)
    time_out_unit: Literal["Days", "Weeks", "Months"]

    @field_validator("in_game_date", mode="before")
    @classmethod
    def parse_in_game_date(cls, value: str | dt.datetime) -> dt.datetime:
        """Convert string in dd/mm/yy, dd/mm/yyyy or ISO format to datetime object."""
        if isinstance(value, dt.datetime):
            return value

        if isinstance(value, str):
            value = value.strip()

            # 1. Attempt to parse standard ISO format (from JSON load)
            if "T" in value or "-" in value:
                with contextlib.suppress(ValueError):
                    return dt.datetime.fromisoformat(value)
            # 2. Attempt to parse custom UI format (from Tkinter input)
            for date_format in ["%d/%m/%y", "%d/%m/%Y"]:
                with contextlib.suppress(ValueError):
                    return dt.datetime.strptime(value, date_format)

            raise ValueError(
                "Invalid date format. Expected dd/mm/yy, dd/mm/yyyy or ISO, "
                f"got '{value}'"
            )

        raise ValueError(
            f"in_game_date must be a string or datetime, got {type(value)}"
        )


class Player(BaseModel):
    """Represent a player within a career save.

    Stores core biographical data, position information, and time-ordered
    histories of attributes, finances, and injuries.
    """

    id: int
    name: str
    nationality: str
    age: int = Field(ge=PLAYER_AGE_MIN, le=PLAYER_AGE_MAX)
    height: str = Field(
        pattern=r'^\d{1,2}\'\d{1,2}"$',
        description="Height in format X'Y\" (e.g., 6'2\")",
    )
    weight: int = Field(
        description="Weight in pounds",
        ge=PLAYER_WEIGHT_MIN,
        le=PLAYER_WEIGHT_MAX,
    )
    positions: list[PositionType]

    # Polymorphic List: Can store either GK or Outfield snapshots
    attribute_history: list[
        Annotated[
            GKAttributeSnapshot | OutfieldAttributeSnapshot,
            Field(discriminator="position_type"),
        ]
    ] = Field(default_factory=list)

    financial_history: list[FinancialSnapshot] = Field(default_factory=list)
    injury_history: list[InjuryRecord] = Field(default_factory=list)

    sold: bool = False
    date_sold: dt.datetime | None = None
    loaned: bool = False

    @model_validator(mode="after")
    def validate_sold_date(self) -> "Player":
        """Validate that a sold player has a corresponding sale date set.

        This enforces consistency between the player's sold status and the
        presence of a sale date.
        """
        if self.sold and self.date_sold is None:
            raise ValueError("date_sold must be provided if player is sold")
        return self

    @property
    def is_goalkeeper(self) -> bool:
        """Determines if the player is a goalkeeper based on their positions list."""
        return "GK" in self.positions

    @field_validator("date_sold", mode="before")
    @classmethod
    def parse_sold_date(cls, value: str | dt.datetime | None) -> dt.datetime | None:
        """Convert string in dd/mm/yy, dd/mm/yyyy or ISO format to datetime object."""
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            return value

        if isinstance(value, str):
            value = value.strip()

            # 1. Attempt to parse standard ISO format (from JSON load)
            if "T" in value or "-" in value:
                with contextlib.suppress(ValueError):
                    return dt.datetime.fromisoformat(value)
            # 2. Attempt to parse custom UI format (from Tkinter input)
            for date_format in ["%d/%m/%y", "%d/%m/%Y"]:
                with contextlib.suppress(ValueError):
                    return dt.datetime.strptime(value, date_format)

            raise ValueError(
                "Invalid date format. Expected dd/mm/yy, dd/mm/yyyy or ISO, "
                f"got '{value}'"
            )

        raise ValueError(f"date_sold must be a string or datetime, got {type(value)}")

    @property
    def current_attributes(
        self,
    ) -> GKAttributeSnapshot | OutfieldAttributeSnapshot | None:
        """Returns the most recent attribute snapshot for the player."""
        if not self.attribute_history:
            return None
        return sorted(self.attribute_history, key=lambda x: x.datetime)[-1]


# --- Match Models ---


class MatchStats(BaseModel):
    """Represent key team statistics recorded for a match.

    Captures possession, attacking, defensive, and disciplinary metrics used to
    summarise a team's performance.
    """

    model_config = ConfigDict(extra="forbid")

    possession: int = Field(ge=0, le=100)
    ball_recovery: int = Field(ge=0)
    shots: int = Field(ge=0)
    xg: float = Field(ge=0)
    passes: int = Field(ge=0)
    tackles: int = Field(ge=0)
    tackles_won: int = Field(ge=0)
    interceptions: int = Field(ge=0)
    saves: int = Field(ge=0)
    fouls_committed: int = Field(ge=0)
    offsides: int = Field(ge=0)
    corners: int = Field(ge=0)
    free_kicks: int = Field(ge=0)
    penalty_kicks: int = Field(ge=0)
    yellow_cards: int = Field(
        ge=MATCH_YELLOW_CARDS_MIN,
        le=MATCH_YELLOW_CARDS_MAX,
    )

    @model_validator(mode="after")
    def validate_tackles(self) -> "MatchStats":
        """Validate the relationship between total tackles and tackles won.

        Ensures that the number of tackles won cannot exceed the total number
        of tackles attempted.
        """
        if self.tackles_won > self.tackles:
            raise ValueError(
                f"tackles_won ({self.tackles_won}) cannot exceed "
                f"tackles ({self.tackles})"
            )
        return self


class MatchData(BaseModel):
    """Represent the core data and statistics for a single match.

    Stores match context, scoreline, and team statistics needed to analyse or
    display a fixture.
    """

    in_game_date: dt.datetime
    competition: str
    home_team_name: str
    away_team_name: str
    home_score: int
    away_score: int
    home_stats: MatchStats
    away_stats: MatchStats

    @field_validator("in_game_date", mode="before")
    @classmethod
    def parse_in_game_date(cls, value: str | dt.datetime) -> dt.datetime:
        """Convert string in dd/mm/yy, dd/mm/yyyy or ISO format to datetime object."""
        if isinstance(value, dt.datetime):
            return value
        if isinstance(value, str):
            value = value.strip()
            if "T" in value or "-" in value:
                with contextlib.suppress(ValueError):
                    return dt.datetime.fromisoformat(value)
            for date_format in ["%d/%m/%y", "%d/%m/%Y"]:
                with contextlib.suppress(ValueError):
                    return dt.datetime.strptime(value, date_format)
            raise ValueError(
                "Invalid date format. Expected dd/mm/yy, dd/mm/yyyy or ISO, "
                f"got '{value}'"
            )
        raise ValueError(
            f"in_game_date must be a string or datetime, got {type(value)}"
        )


class OutfieldPlayerPerformance(BaseModel):
    """Represent the performance of an outfield player in a match.

    Captures positional, attacking, defensive, and physical metrics used to
    evaluate an individual outfield display.
    """

    performance_type: Literal["Outfield"] = Field(
        default="Outfield", description="Discriminator for Outfield performance"
    )
    positions_played: list[PositionType] = Field(min_length=1)
    goals: int = Field(ge=0)
    assists: int = Field(ge=0)
    shots: int = Field(ge=0)
    shot_accuracy: int = Field(ge=0, le=100)
    passes: int = Field(ge=0)
    pass_accuracy: int = Field(ge=0, le=100)
    dribbles: int = Field(ge=0)
    dribble_success_rate: int = Field(ge=0, le=100)
    tackles: int = Field(ge=0)
    tackle_success_rate: int = Field(ge=0, le=100)
    offsides: int = Field(ge=0)
    fouls_committed: int = Field(ge=0)
    possession_won: int = Field(ge=0)
    possession_lost: int = Field(ge=0)
    minutes_played: int = Field(ge=0)
    distance_covered: float = Field(ge=0)
    distance_sprinted: float = Field(ge=0)
    player_id: int

    @model_validator(mode="after")
    def validate_distances(self) -> "OutfieldPlayerPerformance":
        """Validate total distance covered versus sprinted distance.

        Ensures that the recorded sprinting distance does not exceed the
        overall distance covered by the player.
        """
        if self.distance_sprinted > self.distance_covered:
            raise ValueError(
                f"distance_sprinted ({self.distance_sprinted}) cannot exceed "
                f"distance_covered ({self.distance_covered})"
            )
        return self


class GoalkeeperPerformance(BaseModel):
    """Represent the performance of a goalkeeper in a match.

    Captures shot, save, and penalty statistics used to evaluate an individual
    goalkeeping display.
    """

    performance_type: Literal["GK"] = Field(
        default="GK", description="Discriminator for GK performance"
    )
    shots_against: int = Field(ge=0)
    shots_on_target: int = Field(ge=0)
    saves: int = Field(ge=0)
    goals_conceded: int = Field(ge=0)
    save_success_rate: int = Field(ge=0, le=100)
    punch_saves: int = Field(ge=0)
    rush_saves: int = Field(ge=0)
    penalty_saves: int = Field(ge=0)
    penalty_goals_conceded: int = Field(ge=0)
    shoot_out_saves: int = Field(ge=0)
    shoot_out_goals_conceded: int = Field(ge=0)
    player_id: int

    @model_validator(mode="after")
    def validate_goalkeeper_performance(self) -> "GoalkeeperPerformance":
        """Validate the internal consistency of goalkeeper shot and save statistics.

        Ensures that shots on target do not exceed total shots against and that
        saves do not exceed shots on target.
        """
        if self.shots_on_target > self.shots_against:
            raise ValueError(
                f"shots_on_target ({self.shots_on_target}) "
                f"cannot exceed shots_against ({self.shots_against})"
            )
        if self.saves > self.shots_on_target:
            raise ValueError(
                f"saves ({self.saves}) cannot exceed shots_on_target "
                f"({self.shots_on_target})"
            )
        return self


class Match(BaseModel):
    """Represent a recorded match and its associated player performances.

    Links core match data with the individual outfield and goalkeeper
    performances for analysis and tracking.
    """

    id: int
    datetime: dt.datetime
    data: MatchData
    player_performances: list[
        Annotated[
            OutfieldPlayerPerformance | GoalkeeperPerformance,
            Field(discriminator="performance_type"),
        ]
    ] = Field(default_factory=list)


# --- Metadata Models ---


class CareerMetadata(BaseModel):
    """Represent core metadata for a single career save.

    Stores club, manager, configuration, and competition details used to
    identify and describe the career.
    """

    career_id: int
    club_name: str
    folder_name: str
    manager_name: str
    created_at: dt.datetime
    starting_season: str = Field(
        pattern=r"^\d{2}/\d{2}$", description="Season in format yy/yy (e.g., 23/24)"
    )
    half_length: int = Field(
        ge=CAREER_HALF_LENGTH_MIN,
        le=CAREER_HALF_LENGTH_MAX,
        description="IRL length of each half in minutes",
    )
    difficulty: DifficultyLevel
    # League name chosen at career creation. Required for new careers.
    # Existing on-disk metadata without this field will need migration.
    league: str
    # The active competition list for this career. Seeded from config defaults
    # for preset
    # leagues at career creation time; can be modified by the user per-career.
    competitions: list[str] = Field(
        default_factory=list, description="Career-specific active competitions"
    )

    @field_validator("league", mode="before")
    @classmethod
    def ensure_league_title_case(cls, value: str) -> str:
        """Ensure the league value is a title-cased string before validation."""
        if not isinstance(value, str):
            raise ValueError("league must be a string")
        if v := value.strip():
            return capitalize_competition_name(v)
        else:
            raise ValueError("league must not be empty")

    @field_validator("competitions", mode="before")
    @classmethod
    def ensure_competitions_title_case(cls, value: list[str]) -> list[str]:
        """Ensure all competitions are title-cased strings before validation."""
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("competitions must be a list of strings")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("each competition must be a string")
            if s := item.strip():
                cleaned.append(capitalize_competition_name(s))
        return cleaned


class CareerDetail(BaseModel):
    """Represent a lightweight view of a career save for listing and selection.

    Provides just enough information to identify and locate a specific career on disk.
    """

    id: int
    club_name: str
    folder_name: str
