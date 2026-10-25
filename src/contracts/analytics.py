"""Analytics service input and output contracts."""

import datetime as dt
from typing import TypedDict

type PerformanceMeansStdsMap = dict[str, dict[str, dict[str, float] | float]]
type PerformanceWeightsMap = dict[str, dict[str, float]]


class RatedAppearance(TypedDict):
    """A single rated appearance by a player.

    Attributes:
        match_id: ID of the match the rating came from.
        in_game_date: In-game date of the match, used for ordering.
        rating: Custom match rating for the appearance. Appearances without
            a rating (e.g. cameos too short to rate) are never included.
    """

    match_id: int
    in_game_date: dt.datetime
    rating: float


class PlayerRatingHistory(TypedDict):
    """A player's rated appearances plus absence context, used for form scoring.

    Built by DataManager and passed to the analytics engine via ``app.py``.

    Attributes:
        player_id: Unique ID of the player.
        player_name: Display name of the player.
        appearances: Rated appearances only, in chronological order
            (``in_game_date``, then match ID). Empty if the player has no
            rated appearances.
        matches_since_last_rated: Number of tracked team matches (matches with
            player performances recorded) since the player's last rated
            appearance. 0 if rated in the most recent tracked match; equal to
            the total tracked matches if the player has never been rated.
    """

    player_id: int
    player_name: str
    appearances: list[RatedAppearance]
    matches_since_last_rated: int


class FormPoint(TypedDict):
    """One point on a player's EMA form series.

    Attributes:
        match_id: ID of the match this point corresponds to.
        in_game_date: In-game date of the match.
        rating: The raw match rating that was fed into the EMA.
        ema: The EMA value after this appearance (before any absence decay).
    """

    match_id: int
    in_game_date: dt.datetime
    rating: float
    ema: float


class PlayerForm(TypedDict):
    """A player's current form, returned by the analytics engine.

    Attributes:
        player_id: Unique ID of the player.
        player_name: Display name of the player.
        rated_count: Number of rated appearances the form is based on.
        series: EMA series with one point per rated appearance, starting from the
            player's third rated appearance. Empty until the player has the
            minimum number of rated appearances.
        current: Current form as a match-rating-scale value, after decaying
            toward the neutral rating the longer the player has gone unrated.
            ``None`` below the minimum number of appearances.
        form_score: ``current`` rescaled and clamped to [-1, 1] for colour
            mapping: -1 is the worst, 0 is exactly average, 1 is the best.
            ``None`` below the minimum number of appearances.
        matches_since_last_rated: Tracked team matches since the player's last
            rated appearance, echoed from the input for display.
    """

    player_id: int
    player_name: str
    rated_count: int
    series: list[FormPoint]
    current: float | None
    form_score: float | None
    matches_since_last_rated: int


class ReliableRating(TypedDict):
    """A player's estimated underlying quality, returned by the analytics engine.

    Internal-only: consumed by the lineup optimiser and other analytics, never
    displayed directly.

    Attributes:
        player_id: Unique ID of the player.
        rating: Estimated underlying quality on the match-rating scale, shrunk
            toward the population mean the fewer rated appearances the player has.
        n: Number of rated appearances the estimate is based on.
        std_error: Posterior standard deviation of ``rating``; smaller means
            more certain.
    """

    player_id: int
    rating: float
    n: int
    std_error: float
