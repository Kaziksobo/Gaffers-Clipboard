"""Shared typed contracts used across services and UI buffering flows."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NotRequired, Protocol, TypedDict

from src.schemas import (
    CareerDetail,
    CareerMetadata,
    DifficultyLevel,
    GKAttributeSnapshot,
    OutfieldAttributeSnapshot,
    PositionType,
)

# Generic aliases reused by service-layer contracts.
type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
type ReadRawJsonResult = tuple[Literal[False], None] | tuple[Literal[True], JsonValue]
type AttributeSnapshot = GKAttributeSnapshot | OutfieldAttributeSnapshot
type RawValue = JsonValue
type RawPayload = dict[str, RawValue]
type PlayerAttributePayload = RawPayload
type FinancialNumericInput = int | str
type DisplayRow = dict[str, str]
type DisplayRows = list[DisplayRow]
type OverlayCallback = Callable[[int, str], None]
type UIFlushCallback = Callable[[], None]
type OCRScalar = int | float | None
type OCRFlatStats = dict[str, OCRScalar]
type OCRTeamStats = dict[str, OCRFlatStats]
type OCRStatsResult = OCRFlatStats | OCRTeamStats
type ROIMap = dict[str, ROIBounds]
type PerformanceMeansStdsMap = dict[str, dict[str, dict[str, float] | float]]
type PerformanceWeightsMap = dict[str, dict[str, float]]


class SupportsId(Protocol):
    """Protocol for model instances carrying an integer id field."""

    id: int


@dataclass(frozen=True, slots=True)
class CareerCreationArtifacts:
    """Planned artifacts required for creating a new career.

    DataManager should persist these artifacts and only then mutate its own
    in-memory state.
    """

    career_folder_name: str
    career_path: Path
    players_path: Path
    matches_path: Path
    metadata: CareerMetadata
    new_detail: CareerDetail


@dataclass(frozen=True, slots=True)
class PlayerCoreFields:
    """Normalized core player identity and bio fields from UI payloads."""

    name: str
    country: str | None
    age: int | None
    height: str | None
    weight: int | None


class PlayerBioDict(TypedDict):
    """Bio snapshot of a player for UI display."""

    age: int
    height: str
    weight: int
    country: str
    positions: list[PositionType]


class PlayerAttributesBuffer(TypedDict, total=False):
    """Internal buffer shape for staged player attributes."""

    gk_attr: PlayerAttributePayload
    outfield_attr_1: PlayerAttributePayload
    outfield_attr_2: PlayerAttributePayload


class FinancialDataPayload(TypedDict):
    """Expected financial payload shape used by player finance mutations."""

    wage: FinancialNumericInput
    market_value: FinancialNumericInput
    contract_length: NotRequired[FinancialNumericInput | None]
    release_clause: NotRequired[FinancialNumericInput | None]
    sell_on_clause: NotRequired[FinancialNumericInput | None]


class InjuryDataPayload(TypedDict):
    """Expected injury payload shape used by player injury mutations."""

    in_game_date: str
    injury_detail: str
    time_out: int
    time_out_unit: Literal["Days", "Weeks", "Months"]


class CareerMetadataUpdate(TypedDict, total=False):
    """Partial metadata patch payload accepted by career metadata updates."""

    club_name: str
    manager_name: str
    starting_season: str
    half_length: int
    difficulty: DifficultyLevel
    league: str
    competitions: list[str]


class ROIBounds(TypedDict):
    """Single OCR region bounds in pixel coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int


class MatchStatsPayload(TypedDict, total=False):
    """Match stats payload shape used before schema validation."""

    possession: int
    ball_recovery: int
    shots: int
    xg: float
    passes: int
    tackles: int
    tackles_won: int
    interceptions: int
    saves: int
    fouls_committed: int
    offsides: int
    corners: int
    free_kicks: int
    penalty_kicks: int
    yellow_cards: int


type MatchOverviewValue = str | int | float | None | MatchStatsPayload
type MatchOverviewPayload = dict[str, MatchOverviewValue]


class OutfieldPerformancePayload(TypedDict):
    """Raw outfield performance payload captured from UI/buffer flows."""

    player_name: str
    performance_type: Literal["Outfield"]
    positions_played: list[PositionType]
    goals: int
    assists: int
    shots: int
    shot_accuracy: int
    passes: int
    pass_accuracy: int
    dribbles: int
    dribble_success_rate: int
    tackles: int
    tackle_success_rate: int
    offsides: int
    fouls_committed: int
    possession_won: int
    possession_lost: int
    minutes_played: int
    distance_covered: float
    distance_sprinted: float
    match_rating: NotRequired[float | None]


class GoalkeeperPerformancePayload(TypedDict):
    """Raw goalkeeper performance payload captured from UI/buffer flows."""

    player_name: str
    performance_type: Literal["GK"]
    shots_against: int
    shots_on_target: int
    saves: int
    goals_conceded: int
    save_success_rate: int
    punch_saves: int
    rush_saves: int
    penalty_saves: int
    penalty_goals_conceded: int
    shoot_out_saves: int
    shoot_out_goals_conceded: int
    match_rating: NotRequired[float | None]


type PlayerPerformancePayload = (
    OutfieldPerformancePayload | GoalkeeperPerformancePayload
)
type PlayerPerformanceBuffer = list[PlayerPerformancePayload]


class PartialPlayerPerformancePayload(TypedDict, total=False):
    """Partial/patch payload for updating player performances.

    All fields are optional so callers can provide a subset of keys to update.
    This TypedDict covers both outfield and goalkeeper fields used in
    `PlayerPerformancePayload`.
    """

    player_name: str
    performance_type: Literal["Outfield", "GK"]
    positions_played: list[PositionType]
    goals: int
    assists: int
    shots: int
    shot_accuracy: int
    passes: int
    pass_accuracy: int
    dribbles: int
    dribble_success_rate: int
    tackles: int
    tackle_success_rate: int
    offsides: int
    fouls_committed: int
    possession_won: int
    possession_lost: int
    minutes_played: int
    distance_covered: float
    distance_sprinted: float
    shots_against: int
    shots_on_target: int
    saves: int
    goals_conceded: int
    save_success_rate: int
    punch_saves: int
    rush_saves: int
    penalty_saves: int
    penalty_goals_conceded: int
    shoot_out_saves: int
    shoot_out_goals_conceded: int
    match_rating: float | None


@dataclass(frozen=True, slots=True)
class BufferedPlayer:
    """Normalized staged player payload ready for persistence."""

    player_name: str
    attributes: PlayerAttributePayload
    position: str
    in_game_date: str
    is_goalkeeper: bool


@dataclass(frozen=True, slots=True)
class BufferedMatch:
    """Staged match payload ready for persistence."""

    match_overview: MatchOverviewPayload
    player_performances: PlayerPerformanceBuffer
