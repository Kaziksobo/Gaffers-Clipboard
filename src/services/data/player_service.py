"""Player-focused pure helpers for DataManager orchestration.

This module holds transformation and validation helpers used by DataManager's
player update flow. It intentionally performs no filesystem I/O.
"""

import logging
from datetime import datetime
from typing import Literal

from pydantic import ValidationError

from src.contracts.backend import (
    AttributeSnapshot,
    FinancialDataPayload,
    InjuryDataPayload,
    JsonValue,
    PlayerAttributePayload,
    PlayerCoreFields,
)
from src.schemas import (
    FinancialSnapshot,
    GKAttributeSnapshot,
    InjuryRecord,
    OutfieldAttributeSnapshot,
    Player,
    PositionType,
)

logger = logging.getLogger(__name__)


class PlayerService:
    """Provide pure player-domain helpers for DataManager."""

    # ----------------- Primitive Coercion Helpers -----------------

    @staticmethod
    def _as_non_empty_str(value: JsonValue) -> str | None:
        """Normalize JSON value to a non-empty stripped string."""
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _as_int(value: JsonValue) -> int | None:
        """Normalize JSON value to int when safely coercible."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            try:
                return int(cleaned)
            except ValueError:
                return None
        return None

    # ----------------- Player Add/Update Flow -----------------

    def extract_player_core_fields(
        self,
        player_ui_data: PlayerAttributePayload,
    ) -> PlayerCoreFields:
        """Extract and normalize required top-level player identity/bio fields.

        Raises:
            ValueError: If the player name is missing or empty after normalization.
        """
        player_name = self._as_non_empty_str(player_ui_data.get("name"))
        if player_name is None:
            raise ValueError("Player name is required.")

        return PlayerCoreFields(
            name=player_name,
            country=self._as_non_empty_str(player_ui_data.get("country")),
            age=self._as_int(player_ui_data.get("age")),
            height=self._as_non_empty_str(player_ui_data.get("height")),
            weight=self._as_int(player_ui_data.get("weight")),
        )

    def find_player_by_name(self, players: list[Player], name: str) -> Player | None:
        """Find a player by name (case-insensitive) within a provided players list.

        This helper is pure and performs no I/O. It mirrors DataManager's
        previous behavior but allows the search logic to be unit-tested.
        """
        if not name:
            return None
        name_norm = name.strip().lower()
        return next(
            (player for player in players if player.name.strip().lower() == name_norm),
            None,
        )

    def build_attribute_snapshot(
        self,
        *,
        player_ui_data: PlayerAttributePayload,
        is_gk: bool,
        in_game_date: str,
        position: PositionType | None,
        player_name: str,
    ) -> AttributeSnapshot:
        """Create a validated attribute snapshot from raw UI payload data.

        This helper extracts attribute fields from the raw UI payload, constructs a
        timestamped snapshot payload, and validates it against the appropriate
        Pydantic model based on the player's position type. It raises detailed
        errors if validation fails, which can be used to inform the user about
        specific issues with the provided data.

        Args:
            player_ui_data (PlayerAttributePayload): Raw attribute data from the UI.
            is_gk (bool): Indicates if the player is a goalkeeper.
            in_game_date (str): The date of the in-game attribute update.
            position (PositionType | None): The player's position.
            player_name (str): The name of the player.

        Raises:
            ValueError: If the attribute payload is invalid.

        Returns:
            AttributeSnapshot: A validated attribute snapshot.
        """
        top_level_keys = {
            "name",
            "age",
            "height",
            "weight",
            "country",
            "in_game_date",
        }
        attributes = {
            k: v for k, v in player_ui_data.items() if k not in top_level_keys
        }

        snapshot_payload: dict[str, JsonValue | datetime] = {
            "datetime": datetime.now(),
            "in_game_date": in_game_date,
            "position_type": "GK" if is_gk else "Outfield",
            **attributes,
        }
        if position is not None:
            snapshot_payload["position"] = position

        try:
            if is_gk:
                return GKAttributeSnapshot.model_validate(snapshot_payload)
            return OutfieldAttributeSnapshot.model_validate(snapshot_payload)
        except ValidationError as e:
            logger.error(
                "Invalid attribute payload for player '%s': %s",
                player_name,
                e,
            )
            raise ValueError(f"Invalid player attributes for '{player_name}'.") from e

    def update_existing_player(
        self,
        *,
        existing_player: Player,
        attributes_snapshot: AttributeSnapshot,
        core_fields: PlayerCoreFields,
        position: PositionType | None,
    ) -> None:
        """Apply snapshot and optional bio updates to an existing player."""
        logger.info("Updating player: %s", core_fields.name)
        existing_player.attribute_history.append(attributes_snapshot)

        if core_fields.age is not None:
            existing_player.age = core_fields.age
        if core_fields.height is not None:
            existing_player.height = core_fields.height
        if core_fields.weight is not None:
            existing_player.weight = core_fields.weight
        if core_fields.country is not None:
            existing_player.nationality = core_fields.country

        if position is not None and position not in existing_player.positions:
            existing_player.positions.append(position)

    def create_new_player(
        self,
        *,
        player_id: int,
        core_fields: PlayerCoreFields,
        position: PositionType | None,
        attributes_snapshot: AttributeSnapshot,
    ) -> Player:
        """Create a new Player instance from core fields, pos and an attribute snapshot.

        This helper constructs a new Player model instance using the provided core
        fields, position, and the initial attribute snapshot. It performs validation
        to ensure that all required fields for a new player are present and
        raises detailed errors if any critical information is missing or invalid.
        The new player is initialized with the provided attribute snapshot as the
        first entry in their attribute history, and empty
        financial and injury histories.

        Args:
            player_id (int): The unique ID to assign to the new player.
            core_fields (PlayerCoreFields): The core fields for the new player.
            position (PositionType | None): The position of the new player.
            attributes_snapshot (AttributeSnapshot): The initial attribute snapshot
                                                     for the new player.

        Raises:
            ValueError: If any critical information for the new player is
                        missing or invalid.
            ValidationError: If the constructed Player model fails validation checks.

        Returns:
            Player: The newly created player instance.
        """
        country = core_fields.country
        age = core_fields.age
        height = core_fields.height
        weight = core_fields.weight

        if (
            country is None
            or age is None
            or height is None
            or weight is None
            or position is None
        ):
            raise ValueError(
                "New players require name, country, age, height, weight, and position."
            )

        logger.info("Adding new player: %s", core_fields.name)
        return Player(
            id=player_id,
            name=core_fields.name,
            nationality=country,
            age=age,
            height=height,
            weight=weight,
            positions=[position],
            attribute_history=[attributes_snapshot],
            financial_history=[],
            injury_history=[],
            sold=False,
            date_sold=None,
            loaned=False,
        )

    # ----------------- Existing Player Guards -----------------

    def require_existing_player(
        self,
        *,
        players: list[Player],
        player_name: str,
        action_description: str,
    ) -> Player:
        """Return an existing player by name or raise a context-rich error.

        Raises:
            ValueError: If the player cannot be found in the provided list.
        """
        existing_player = self.find_player_by_name(players, player_name)
        if existing_player is None:
            message = f"Player '{player_name}' not found. Cannot {action_description}."
            logger.warning(message)
            raise ValueError(message)

        return existing_player

    # ----------------- Snapshot Builders -----------------

    def create_financial_snapshot(
        self,
        *,
        player_name: str,
        financial_data: FinancialDataPayload,
        in_game_date: str,
    ) -> FinancialSnapshot:
        """Create a validated financial snapshot from raw UI payload data.

        Raises:
            ValueError: If the financial data is invalid or
                        if the in-game date is missing/invalid.
        """
        snapshot_payload = {
            "datetime": datetime.now(),
            "in_game_date": in_game_date,
            **financial_data,
        }

        try:
            return FinancialSnapshot.model_validate(snapshot_payload)
        except ValidationError as e:
            logger.error("Validation failed for financial data: %s", e)
            raise ValueError(
                f"Invalid financial data for player '{player_name}': {e}"
            ) from e

    def create_injury_snapshot(
        self,
        *,
        player_name: str,
        injury_data: InjuryDataPayload,
    ) -> InjuryRecord:
        """Create a validated injury snapshot from raw UI payload data.

        Raises:
            ValueError: If the injury data is invalid.
        """
        snapshot_payload = {
            "datetime": datetime.now(),
            **injury_data,
        }

        try:
            return InjuryRecord.model_validate(snapshot_payload)
        except (ValidationError, ValueError) as e:
            logger.error("Failed to add injury record: %s", e)
            raise ValueError(
                f"Invalid injury data for player '{player_name}': {e}"
            ) from e

    # ----------------- Status Transitions -----------------

    def apply_player_status(
        self,
        *,
        existing_player: Player,
        status_key: Literal["sold", "loaned"],
        status_value: bool,
        in_game_date: str | None = None,
    ) -> None:
        """Apply sold/loaned status transitions to an existing player.

        Raises:
            ValueError: If sold status requires a missing/invalid in-game date.
        """
        if status_key == "sold" and status_value:
            if not in_game_date:
                message = "In-game date is required when marking a player as sold."
                logger.error(message)
                raise ValueError(message)

            try:
                parsed_date_sold = Player.parse_sold_date(in_game_date)
            except ValueError as e:
                logger.error("Invalid in-game date for sold player: %s", e)
                raise ValueError("Invalid in-game date format for sold player.") from e

            if parsed_date_sold is None:
                raise ValueError("Sold player status requires a valid in-game date.")

            existing_player.date_sold = parsed_date_sold
            existing_player.loaned = False

        if status_key == "sold":
            existing_player.sold = status_value
        else:
            existing_player.loaned = status_value
