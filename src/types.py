from pydantic import BaseModel, Field, ConfigDict, model_validator, Discriminator, field_validator
from typing import List, Optional, Literal, Union, Annotated
from datetime import datetime as DatetimeType
from abc import ABC

# Enums and constants
DifficultyLevel = Literal["Beginner", "Amateur", "Semi-Pro", "Professional", "World Class", "Legendary", "Ultimate"]
PositionType = Literal["GK", "LB", "RB", "CB", "LWB", "RWB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST", "CF"]

# Attribute models
class BaseAttributeSnapshot(BaseModel, ABC):
    """Common fields for all attribute snapshots."""
    datetime: DatetimeType
    season: str
    model_config = ConfigDict(extra="forbid")

class GKAttributeSnapshot(BaseAttributeSnapshot):
    """Fields specific to Goalkeeper attributes. 
    
    The position_type field is used as a discriminator for polymorphic behavior in the Player model's attribute_history list.
    """
    
    position_type: Literal["GK"] = Field(default="GK", description="Discriminator for GK attributes")
    diving: int = Field(ge=0, le=99)
    handling: int = Field(ge=0, le=99)
    kicking: int = Field(ge=0, le=99)
    reflexes: int = Field(ge=0, le=99)
    positioning: int = Field(ge=0, le=99)

class OutfieldAttributeSnapshot(BaseAttributeSnapshot):
    """Fields specific to Outfield player attributes.
    
    The position_type field is used as a discriminator for polymorphic behavior in the Player model's attribute_history list.
    """
    
    position_type: Literal["Outfield"] = Field(default="Outfield", description="Discriminator for Outfield attributes")
    # Physical
    acceleration: int = Field(ge=0, le=99)
    sprint_speed: int = Field(ge=0, le=99)
    agility: int = Field(ge=0, le=99)
    balance: int = Field(ge=0, le=99)
    jumping: int = Field(ge=0, le=99)
    stamina: int = Field(ge=0, le=99)
    strength: int = Field(ge=0, le=99)

    # Mental
    aggression: int = Field(ge=0, le=99)
    att_position: int = Field(ge=0, le=99)
    composure: int = Field(ge=0, le=99)
    interceptions: int = Field(ge=0, le=99)
    reactions: int = Field(ge=0, le=99)
    vision: int = Field(ge=0, le=99)
    defensive_awareness: int = Field(ge=0, le=99)

    # Technical
    ball_control: int = Field(ge=0, le=99)
    crossing: int = Field(ge=0, le=99)
    curve: int = Field(ge=0, le=99)
    dribbling: int = Field(ge=0, le=99)
    fk_accuracy: int = Field(ge=0, le=99)
    finishing: int = Field(ge=0, le=99)
    heading_accuracy: int = Field(ge=0, le=99)
    long_pass: int = Field(ge=0, le=99)
    long_shots: int = Field(ge=0, le=99)
    penalties: int = Field(ge=0, le=99)
    short_pass: int = Field(ge=0, le=99)
    shot_power: int = Field(ge=0, le=99)
    slide_tackle: int = Field(ge=0, le=99)
    stand_tackle: int = Field(ge=0, le=99)
    volleys: int = Field(ge=0, le=99)

# Financial, injury and player models
class FinancialSnapshot(BaseModel):
    """Represents a snapshot of a player's financial status at a given point in time. 
    
    This includes their wage, market value, contract length, release clause, and sell-on clause. 
    The datetime and season fields indicate when this snapshot was taken.
    """
    datetime: DatetimeType
    season: str
    wage: int = Field(ge=0)
    market_value: int = Field(ge=0)
    contract_length: int = Field(ge=0, le=15)
    release_clause: int = Field(default=0, ge=0)
    sell_on_clause: int = Field(default=0, ge=0, le=100)

class InjuryRecord(BaseModel):
    datetime: DatetimeType
    season: str
    in_game_date: DatetimeType
    injury_detail: str
    time_out: int = Field(ge=0)
    time_out_unit: Literal["Days", "Weeks", "Months"]
    
    @field_validator('in_game_date', mode='before')
    @classmethod
    def parse_in_game_date(cls, value):
        """Convert string in dd/mm/yy format to datetime object."""
        if isinstance(value, DatetimeType):
            return value  # Already a datetime
        if isinstance(value, str):
            try:
                return DatetimeType.strptime(value.strip(), "%d/%m/%y")
            except ValueError as e:
                raise ValueError(f"Invalid date format. Expected dd/mm/yy, got '{value}'") from e
        raise ValueError(f"in_game_date must be a string or datetime, got {type(value)}")

class Player(BaseModel):
    """Represents a player in the career mode, including their personal information, position(s), attribute history, and financial history.
    """
    id: int
    name: str
    nationality: str
    age: int = Field(ge=16, le=60)
    height: str = Field(regex=r'^\d{1,2}\'\d{1,2}"$', description="Format: 6'2\"")
    weight: int = Field(description="Weight in pounds", ge=100, le=300)
    positions: list[str]
    
    # Polymorphic List: Can store either GK or Outfield snapshots
    attribute_history: list[Annotated[Union[GKAttributeSnapshot, OutfieldAttributeSnapshot], Field(discriminator='position_type')]] = Field(default_factory=list)
    
    financial_history: list[FinancialSnapshot] = Field(default_factory=list)
    injury_history: list[InjuryRecord] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def ensure_injury_history(self):
        """Ensure injury_history is initialized (handles migration of existing players)."""
        if self.injury_history is None:
            self.injury_history = []
        return self
    
    sold: bool = False
    loaned: bool = False
    
    @property
    def is_goalkeeper(self) -> bool:
        """Determines if the player is a goalkeeper based on their positions list."""
        return "GK" in self.positions

    @property
    def current_attributes(self) -> Optional[Union[GKAttributeSnapshot, OutfieldAttributeSnapshot]]:
        """Returns the most recent attribute snapshot for the player."""
        if not self.attribute_history:
            return None
        return sorted(self.attribute_history, key=lambda x: x.datetime)[-1]

# Match models
class MatchStats(BaseModel):
    """Represents the statistics for a team in a match.
    """
    possession: int = Field(ge=0, le=100)
    ball_recovery: int = Field(ge=0)
    shots: int = Field(ge=0)
    xG: float = Field(ge=0)
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
    yellow_cards: int = Field(ge=0, le=16)
    
    @model_validator(mode='after')
    def validate_tackles(self):
        """Ensures that tackles_won does not exceed tackles."""
        if self.tackles_won > self.tackles:
            raise ValueError(
                f'tackles_won ({self.tackles_won}) cannot exceed tackles ({self.tackles})'
            )
        return self

class MatchData(BaseModel):
    """Represents the data for a match, including the date and time, competition, teams involved, scores, and team statistics."""
    competition: str
    home_team_name: str
    away_team_name: str
    home_score: int
    away_score: int
    home_stats: MatchStats
    away_stats: MatchStats

class OutfieldPlayerPerformance(BaseModel):
    """Represents the performance of an outfield player in a match
    
    The performance_type field is used as a discriminator for polymorphic behavior in the Match model's player_performances list.
    """
    performance_type: Literal["Outfield"] = Field(default="Outfield", description="Discriminator for Outfield performance")
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

class GoalkeeperPerformance(BaseModel):
    """Represents the performance of a goalkeeper in a match
    
    The performance_type field is used as a discriminator for polymorphic behavior in the Match model's player_performances list.
    """
    performance_type: Literal["GK"] = Field(default="GK", description="Discriminator for GK performance")
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
    
    @model_validator(mode='after')
    def validate_goalkeeper_performance(self):
        """Ensures that shots_on_target does not exceed shots_against and saves does not exceed shots_on_target."""
        if self.shots_on_target > self.shots_against:
            raise ValueError(
                f'shots_on_target ({self.shots_on_target}) '
                f'cannot exceed shots_against ({self.shots_against})'
            )
        if self.saves > self.shots_on_target:
            raise ValueError(
                f'saves ({self.saves}) cannot exceed shots_on_target ({self.shots_on_target})'
            )
        return self

class Match(BaseModel):
    """Represents a match in the career mode, including the match data and player performances."""
    id: int
    datetime: DatetimeType
    data: MatchData
    player_performances: list[Annotated[Union[OutfieldPlayerPerformance, GoalkeeperPerformance], Field(discriminator='performance_type')]] = Field(default_factory=list)

class CareerMetadata(BaseModel):
    """Represents the metadata for a career"""
    career_id: int
    club_name: str
    folder_name: str
    manager_name: str
    created_at: DatetimeType
    starting_season: str
    half_length: int
    difficulty: str

class CareerDetail(BaseModel):
    """Represents the basic details of a career"""
    id: int
    club_name: str
    folder_name: str