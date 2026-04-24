"""
BufferService — in-memory staging for player and match payloads.

This module implements `BufferService`, a UI-agnostic service that temporarily stores
raw payloads produced by OCR or form input (player attributes, match overview, and
per-player performances). Buffers support incremental, multi-step workflows: staging,
merging, removal, and reset. Extraction helpers return normalized, typed payloads
that are intended to be validated and persisted by the DataManager.

Responsibilities:
- Hold raw, typed payloads (see `src.contracts`) until callers commit them.
- Provide mutation APIs for staging and clearing session data.
- Provide extraction helpers that prepare data for persistence.
- (Optional) Provide lightweight display formatting; consider moving presentation
  logic to a dedicated presenter to keep services strictly UI-agnostic.

Notes:
- Buffers are ephemeral and in-memory; callers must persist staged data explicitly.
- Returned snapshots may require external synchronization in concurrent contexts.
"""

import logging
from collections.abc import MutableMapping
from typing import cast

from src.contracts.backend import (
    BufferedMatch,
    BufferedPlayer,
    DisplayRows,
    MatchOverviewPayload,
    PlayerAttributePayload,
    PlayerAttributesBuffer,
    PlayerPerformanceBuffer,
    PlayerPerformancePayload,
    RawValue,
)
from src.exceptions import (
    DataPersistenceError,
    DuplicateRecordError,
    IncompleteDataError,
    PlayerNotFoundInBufferError,
)
from src.utils import safe_normalize_name

logger = logging.getLogger(__name__)


class BufferService:
    """Manage in-memory buffers for staged player and match data.

    This service stores raw payloads captured across multi-step workflows and
    prepares them for validation and persistence. It remains UI-agnostic and
    does not coordinate frame behavior.
    """

    def __init__(self) -> None:
        """Initialize empty session buffers for player and match workflows.

        Create private in-memory containers for player attributes, match
        overview data, and per-player performance records.
        """
        self._player_attributes_buffer: PlayerAttributesBuffer = {}
        self._match_overview_buffer: MatchOverviewPayload = {}
        self._player_performances_buffer: PlayerPerformanceBuffer = []

    def clear_session_buffers(self) -> None:
        """Clear all session buffers.

        Reset the in-memory player attributes, match overview, and player performance
        buffers to empty containers. This operation discards any unsaved staged data.
        """
        logger.info("Clearing session buffers.")
        self._player_attributes_buffer = {}
        self._match_overview_buffer = {}
        self._player_performances_buffer = []

    def has_unsaved_work(self) -> bool:
        """Return True if any in-memory session buffer contains unsaved data.

        Checks whether any of the session buffers (player attributes, match
        overview, or player performances) are non-empty. The return value is a
        momentary snapshot of internal state and may change if buffers are
        mutated concurrently. This method does not perform validation or persistence.

        Returns:
            bool: True when any buffer contains data (indicating unsaved work).
        """
        return bool(
            self._player_attributes_buffer
            or self._match_overview_buffer
            or self._player_performances_buffer
        )

    # ----------------- Player Buffering Methods -----------------

    def buffer_player_attributes(
        self,
        data: PlayerAttributePayload,
        is_goalkeeper: bool,
        is_first_page: bool = True,
    ) -> None:
        """Stage raw player attribute payloads for later validation and persistence.

        Store the given attribute mapping into the appropriate private buffer slot.
        For goalkeeper data set `is_goalkeeper=True`. For outfield players, attributes
        may be split across two partitions; set `is_first_page` to True for the first
        partition and False for the second. This method does not validate the payload;
        validation and conversion occur when data is committed for persistence.

        Args:
            data (PlayerAttributePayload): Raw attribute mapping captured from UI forms.
            is_goalkeeper (bool): True when `data` contains goalkeeper attributes.
            is_first_page (bool): When buffering outfield attributes, True for the first
                partition and False for the second. Defaults to True.
        """
        logger.info(
            "Buffering player data. GK: %s, First Page: %s",
            is_goalkeeper,
            is_first_page,
        )

        if is_goalkeeper:
            self._player_attributes_buffer["gk_attr"] = data
        elif is_first_page:
            self._player_attributes_buffer["outfield_attr_1"] = data
        else:
            self._player_attributes_buffer["outfield_attr_2"] = data

    def get_buffered_player(self) -> BufferedPlayer:
        """
        Prepare buffered player attributes for saving.

        Extract player data from the session buffers (goalkeeper or two-page outfield),
        perform light sanity checks, and return a snapshot suitable for persistence.

        Returns:
            BufferedPlayer: Normalized staged payload with named fields.

        Raises:
            IncompleteDataError: If no player buffer is present, required outfield pages
                                are missing, or required context fields are empty.
            DataPersistenceError: Wraps unexpected errors raised while extracting data.
        """
        if not self._player_attributes_buffer:
            raise IncompleteDataError("Cannot save: No player data found in buffer.")
        try:
            if "gk_attr" in self._player_attributes_buffer:
                player_name, position, in_game_date, attributes = (
                    self._extract_goalkeeper_player_buffer(
                        self._player_attributes_buffer
                    )
                )
                is_gk = True
            elif (
                "outfield_attr_1" in self._player_attributes_buffer
                and "outfield_attr_2" in self._player_attributes_buffer
            ):
                player_name, position, in_game_date, attributes = (
                    self._extract_outfield_player_buffer(self._player_attributes_buffer)
                )
                is_gk = False
            else:
                raise IncompleteDataError(
                    "Cannot save: Missing page 1 or page 2 of outfield attributes."
                )

            if not player_name or not in_game_date:
                logger.error(
                    "Save aborted: Missing critical context. Name: %r, Date: %r",
                    player_name,
                    in_game_date,
                )
                raise IncompleteDataError(
                    "Cannot save: Missing required player context fields "
                    "(Name or In-game Date)."
                )

            return BufferedPlayer(
                player_name=player_name,
                attributes=attributes,
                position=position,
                in_game_date=in_game_date,
                is_goalkeeper=is_gk,
            )

        except IncompleteDataError:
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while extracting player data from buffer."
            )
            raise DataPersistenceError(
                "An unexpected error occurred while preparing player data for "
                f"saving: {e}"
            ) from e

    def reset_player_buffer(self) -> None:
        """
        Reset the staged player attributes buffer.

        Clear only the player-attributes session buffer so a new player can be entered
        without discarding staged match overview or player performance data.
        """
        logger.info("Resetting player attributes buffer for new entry.")
        self._player_attributes_buffer = {}

    # ----------------- Match Buffering Methods -----------------

    def buffer_match_overview(self, overview_data: MatchOverviewPayload) -> None:
        """Stage or merge match overview data into the session buffer.

        Merge keys from the provided mapping into the existing match overview buffer.
        When the buffer is empty a shallow copy of overview_data is stored. For
        existing buffers, incoming keys whose value is None are ignored (existing
        non-None values are preserved). This method does not validate field types;
        callers should validate before persisting.

        Args:
            overview_data (MatchOverviewPayload): Mapping of match overview fields.
        Raises:
            ValueError: If overview_data is not a mapping/dictionary.
        """
        if not isinstance(overview_data, dict):
            logger.error(
                "Attempted to buffer match overview data that is not a dictionary."
            )
            raise ValueError("Match overview data must be a dictionary.")

        logger.info("Buffering match overview data.")

        if not self._match_overview_buffer:
            self._match_overview_buffer = overview_data.copy()
            return

        for key, value in overview_data.items():
            if value is None and key in self._match_overview_buffer:
                continue
            self._match_overview_buffer[key] = value

    def buffer_player_performance(
        self, performance_data: PlayerPerformancePayload
    ) -> None:
        """Stage a single player's performance payload in the session buffer.

        Perform shallow validation (ensure the payload is a mapping and contains the
        required 'player_name') and prevent duplicate buffered entries for the same
        player. A copy of the provided mapping is appended to the internal buffer;
        full schema validation and conversion occur when data is committed for
        persistence.

        Args:
            performance_data (PlayerPerformancePayload): Raw perf fields for a player.

        Raises:
            ValueError: If performance_data is not a mapping or missing 'player_name'.
            DuplicateRecordError: If an entry for the same player already exists.
        """
        # validate that data is a dict and contains expected keys (e.g. player_name)
        if not isinstance(performance_data, dict):
            logger.error(
                "Attempted to buffer player performance data that is not a dictionary."
            )
            raise ValueError("Player performance data must be a dictionary.")

        if "player_name" not in performance_data:
            logger.error(
                "Player performance data is missing the required 'player_name' key."
            )
            raise ValueError("Player performance data must include 'player_name' key.")

        logger.info(
            "Buffering player performance data for: %s",
            performance_data.get("player_name", "Unknown"),
        )

        # Check if data for this player has already been buffered
        for dataset in self._player_performances_buffer:
            if safe_normalize_name(dataset.get("player_name")) == safe_normalize_name(
                performance_data.get("player_name")
            ):
                logger.error(
                    "Duplicate player performance detected for %s. Each player's "
                    "performance should only be buffered once per match.",
                    performance_data.get("player_name"),
                )
                raise DuplicateRecordError(performance_data.get("player_name"))

        self._player_performances_buffer.append(performance_data)

    def remove_player_from_buffer(self, player_name: str) -> None:
        """
        Remove a player's performance entry from the in-memory session buffer.

        Validate and normalize the provided player name (using safe_normalize_name) then
        filter self._player_performances_buffer to remove any records whose normalized
        player_name equals the normalized target. Logs an info message when at least one
        entry is removed and a warning when no matching entries are found.

        Args:
            player_name (str): Full player name to remove. Must be a non-empty string.

        Raises:
            ValueError: If player_name is not a non-empty string after normalization.
        """
        # Normalize the target player name once for robust comparison
        normalized_target = safe_normalize_name(player_name)
        if not normalized_target:
            logger.error(
                "Attempted to remove a player with an empty or invalid name "
                "from the buffer."
            )
            raise ValueError(
                "Player name must be a non-empty string to remove from buffer."
            )

        original_count = len(self._player_performances_buffer)
        self._player_performances_buffer = [
            performance
            for performance in self._player_performances_buffer
            if safe_normalize_name(performance.get("player_name")) != normalized_target
        ]

        if len(self._player_performances_buffer) < original_count:
            logger.info("Removed buffered performance for player: %s", player_name)
        else:
            logger.warning(
                "No buffered performance found for player: %s. No entries removed.",
                player_name,
            )

    def get_buffered_match(self) -> BufferedMatch:
        """
        Return staged match buffers for persistence.

        Validate that match overview data exists, then return the staged match overview
        mapping and buffered player-performance records.

        Returns:
            BufferedMatch: Staged match overview and buffered player performances.

        Raises:
            IncompleteDataError: If no match overview data is currently staged.
        """
        if not self._match_overview_buffer:
            raise IncompleteDataError(
                "Cannot save: No match overview data found in buffer."
            )
        return BufferedMatch(
            match_overview=self._match_overview_buffer,
            player_performances=self._player_performances_buffer,
        )

    def reset_match_buffers(self) -> None:
        """
        Reset match-related session buffers while retaining player attributes.

        Clear the match overview buffer and player-performances buffer to start entry
        for a new match without discarding staged player attributes.
        """
        logger.info(
            "Resetting match overview and player performances buffers for new entry."
        )
        self._match_overview_buffer = {}
        self._player_performances_buffer = []

    # ----------------- Match Updating Methods -----------------
    def update_match_overview(self, updates: MatchOverviewPayload) -> None:
        """Apply manual corrections to the buffered match overview.

        Args:
            updates: A partial overview payload containing corrected values,
                including nested side-stat dictionaries and score fields.

        Raises:
            IncompleteDataError: If called before a match overview is staged.
        """
        if not self._match_overview_buffer:
            raise IncompleteDataError("Cannot update overview: No match is buffered.")

        # Dictionary update overwrites existing keys or adds new ones safely
        self._match_overview_buffer.update(updates)
        logger.debug("Applied manual corrections to match overview: %s", updates)

    def update_player_performance(
        self, player_name: str, updates: dict[str, int]
    ) -> None:
        """Apply manual statistical corrections to a buffered player.

        Args:
            player_name: The un-normalized name of the player (as displayed in the UI).
            updates: A dictionary of stat keys and their corrected integer values.

        Raises:
            PlayerNotFoundInBufferError: If the normalized player name is
                                         not found in the buffer.
        """
        norm_name = safe_normalize_name(player_name)

        for performance in self._player_performances_buffer:
            if safe_normalize_name(performance.get("player_name")) == norm_name:
                perf_map = cast(MutableMapping[str, RawValue], performance)
                for key, value in updates.items():
                    perf_map[key] = value
                logger.debug(
                    "Applied manual corrections to player %s: %s", player_name, updates
                )
                return
        # If we reach here the requested player wasn't found in the buffer
        logger.warning(
            "Attempted to apply manual corrections but player not found: %s",
            player_name,
        )
        raise PlayerNotFoundInBufferError(f"Player not found in buffer: {player_name}")

    # ----------------- Buffer Display Methods -----------------

    def get_buffered_player_performances(
        self,
        display_keys: list[str],
        id_key: str = "player_name",
        default: str = "-",
    ) -> DisplayRows:
        """Format buffered player performance data for safe, human-readable display.

        Convert the internal performance payloads into a new list of flat, string-only
        dictionaries suitable for UI tables. This method does not mutate the internal
        buffers; it returns a formatted snapshot.

        Formatting rules:
        - All values are coerced to strings.
        - `list` values are joined with ", ".
        - `None` or empty-string values are replaced with `default`.
        - Records missing a non-empty `id_key` are skipped and a warning is logged.
        - Goalkeeper performances receive special-casing: when `performance_type` is
          a case-insensitive "gk", the `positions_played` display key is shown as "GK".

        Args:
            display_keys (list[str]): Ordered list of keys to include in each record.
            id_key (str, optional): The key used as the unique identifier column.
                                    Records without a non-empty `id_key` are skipped.
                                    Defaults to "player_name".
            default (str, optional): Placeholder string used when a field is missing,
                                     null, or empty. Defaults to "-".

        Returns:
            DisplayRows: New list of display-ready rows where every value is a
                                  string and each row contains the `id_key`.
        """
        formatted_performances: DisplayRows = []
        for performance in self._player_performances_buffer:
            # Explicit presence and non-empty check for the id_key avoids accidental
            # collisions when a legitimate value equals the `default` placeholder.
            if id_key not in performance or performance.get(id_key) in (
                None,
                "",
            ):
                logger.warning(
                    "Buffered performance data is missing the required id_key %r. "
                    "This entry will be skipped in display. Data: %s",
                    id_key,
                    performance,
                )
                continue
            formatted_performance = {id_key: str(performance.get(id_key, default))}
            for key in display_keys:
                if key == id_key:
                    continue
                # Ensure goalkeeper performances are displayed as 'GK' regardless
                # of how the performance_type string is cased (e.g. 'GK', 'gk').
                perf_type = performance.get("performance_type")
                if (
                    isinstance(perf_type, str)
                    and perf_type.casefold() == "gk"
                    and key == "positions_played"
                ):
                    formatted_performance[key] = "GK"
                    continue
                value = performance.get(key, default)
                if value in (None, ""):
                    value = default
                if isinstance(value, list):
                    formatted_performance[key] = ", ".join(str(v) for v in value)
                else:
                    formatted_performance[key] = str(value)
            formatted_performances.append(formatted_performance)

        return formatted_performances

    # ----------------- Internal Helpers -----------------

    @staticmethod
    def _extract_goalkeeper_player_buffer(
        buffered_data: PlayerAttributesBuffer,
    ) -> tuple[str, str, str, PlayerAttributePayload]:
        """Extract goalkeeper save data from a buffered attributes mapping.

        The buffered_data mapping must contain the key 'gk_attr' whose value
        is a mapping of goalkeeper attributes. Returns a 4-tuple:
        (name, position, in_game_date, attributes) where position is the
        constant string 'GK'. This helper does not perform full validation; callers
        should validate or convert types before persisting.

        Returns:
            tuple[str, str, str, PlayerAttributePayload]: (name, position, in_game_date, attributes)

        Raises:
            KeyError: If 'gk_attr' is missing from buffered_data.
        """  # noqa: E501
        gk_data = buffered_data["gk_attr"]
        name = str(gk_data.get("name") or "").strip()
        position = "GK"
        in_game_date = str(gk_data.get("in_game_date") or "").strip()
        return (
            name,
            position,
            in_game_date,
            gk_data,
        )

    @staticmethod
    def _extract_outfield_player_buffer(
        buffered_data: PlayerAttributesBuffer,
    ) -> tuple[str, str, str, PlayerAttributePayload]:
        """Extract normalized save data from a two-page outfield attribute buffer.

        The `buffered_data` mapping must contain the keys 'outfield_attr_1' and
        'outfield_attr_2', each holding a mapping of attribute fields for the same
        player. Page two values override page one on key collisions. Returns a 4-tuple
        `(name, position, in_game_date, attributes)` where `position` is a
        normalized string. This helper performs light
        coercion (stringifying and stripping common fields) but does not perform full
        validation; callers should validate and convert types before persisting.

        Returns:
            tuple[str, str, str, PlayerAttributePayload]: (name, position, in_game_date, attributes)

        Raises:
            KeyError: If 'outfield_attr_1' or 'outfield_attr_2' is missing from buffered_data.
        """  # noqa: E501
        outfield_page_1 = buffered_data["outfield_attr_1"]
        outfield_page_2 = buffered_data["outfield_attr_2"]
        name = str(outfield_page_1.get("name") or "").strip()
        pos_raw = outfield_page_1.get("position")
        pos = str(pos_raw or "").strip()
        in_game_date = str(outfield_page_1.get("in_game_date") or "").strip()
        data = {**outfield_page_1, **outfield_page_2}
        return (
            name,
            pos,
            in_game_date,
            data,
        )
