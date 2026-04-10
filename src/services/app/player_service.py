"""
PlayerService - controller-facing player workflow operations.

This module defines PlayerService, a thin service layer over DataManager for
creating and updating player records and handling related lifecycle actions
(financial updates, sales, loans, injuries, and read-only player lookups).

The service performs lightweight context validation before write operations,
delegates persistence and retrieval to DataManager, and wraps backend failures
in domain-specific exceptions so the application layer receives consistent
error semantics.

Responsibilities:
- Validate required player context before mutation operations.
- Delegate player mutations and queries to DataManager.
- Surface consistent error boundaries with IncompleteDataError and DataPersistenceError.
- Provide UI-friendly read models such as filtered name lists and
    lightweight player bio snapshots.

The service is UI-agnostic and focused on orchestration, validation gates,
and error-boundary behavior for player workflows.
"""

import logging

from src.contracts.backend import (
    FinancialDataPayload,
    InjuryDataPayload,
    PlayerAttributePayload,
    PlayerBioDict,
)
from src.data_manager import DataManager
from src.exceptions import DataPersistenceError, IncompleteDataError
from src.schemas import PositionType

logger = logging.getLogger(__name__)


class PlayerService:
    """High-level coordinator for player-related actions and data persistence.

    Provides validation, error handling, and routing between the UI layer and
    the underlying data manager for player records, contracts, and status changes.

    """

    def __init__(self, data_manager: DataManager) -> None:
        """Initialize the player service with a shared DataManager instance.

        Args:
            data_manager (DataManager): Persistence layer used for player reads
                and writes.
        """
        self._data_manager = data_manager

    def save_player(
        self,
        player_name: str,
        attributes: PlayerAttributePayload,
        position: PositionType | None,
        in_game_date: str,
        is_gk: bool = False,
    ) -> None:
        """Persist core player data and attributes for the active career.

        Routes validated UI input to the DataManager to create or update a player
        record, surfacing incomplete data and persistence failures as domain errors.

        Args:
            player_name (str): Display name of the player being created or updated.
            attributes (PlayerAttributePayload): Raw attribute values captured
                from the UI for the player.
            position (PositionType | None): Primary on-pitch position associated
                with the player, if known.
            in_game_date (str): In-game date used to contextualize the saved
                attributes (e.g., season or match date).
            is_gk (bool, optional): Whether the player should be treated as a
                goalkeeper for attribute grouping and filters. Defaults to False.

        Raises:
            IncompleteDataError: If the DataManager detects missing or invalid
                required fields for the player.
            DataPersistenceError: If a lower-level validation or storage error
                occurs while saving the player record.
        """
        try:
            self._data_manager.add_or_update_player(
                player_ui_data=attributes,
                position=position,
                in_game_date=in_game_date,
                is_gk=is_gk,
            )
        except IncompleteDataError:
            logger.error("Incomplete data provided for player '%s'", player_name)
            raise
        except Exception as e:
            # We catch the generic exception (like a Pydantic ValidationError)
            # and wrap it in our custom DataPersistenceError for the UI to handle.
            logger.error(
                "DataManager failed to save player '%s': %s",
                player_name,
                e,
                exc_info=True,
            )
            raise DataPersistenceError(
                f"Failed to save player data to the database: {e}"
            ) from e

    def save_financial_data(
        self,
        player_name: str,
        financial_data: FinancialDataPayload,
        in_game_date: str,
    ) -> None:
        """Validate and persist financial details for a specific player.

        Ensures core context fields are present, then delegates financial data
        storage to the DataManager while wrapping backend failures for the UI.

        Args:
            player_name (str): Name of the player whose financial data is being saved.
            financial_data (FinancialDataPayload): Dictionary of financial
                fields captured from the UI (e.g., wage, value, contract
                length).
            in_game_date (str): In-game date associated with this financial snapshot.

        Raises:
            IncompleteDataError: If the player name, financial data, or in-game date
                is missing, blank, or empty.
            DataPersistenceError: If the backend fails to validate or persist the
                financial data payload.
        """
        # Validate critical context before hitting the DataManager
        if not player_name or not player_name.strip():
            logger.error("Financial save aborted: Player name is missing.")
            raise IncompleteDataError("Cannot save: No player selected.")

        if not financial_data:
            logger.error(
                "Financial save aborted: No data provided for %s.",
                player_name,
            )
            raise IncompleteDataError("Cannot save: Financial data fields are empty.")

        if not in_game_date or not in_game_date.strip():
            logger.error("Financial save aborted: In-game date is missing.")
            raise IncompleteDataError("Cannot save: In-game date is required.")

        logger.info("Initiating financial save for player '%s'", player_name)
        try:
            self._data_manager.add_financial_data(
                player_name,
                financial_data,
                in_game_date,
            )
        except Exception as e:
            logger.error(
                "Failed to persist financial data for %s: %s",
                player_name,
                e,
                exc_info=True,
            )
            raise DataPersistenceError(
                f"Backend failed to save financial data: {e}"
            ) from e

    def add_injury_record(
        self,
        player_name: str,
        injury_data: InjuryDataPayload,
    ) -> None:
        """Create and persist an injury record for a specific player.

        Validates required context, forwards the injury payload to the DataManager,
        and wraps common backend validation failures into a persistence error.

        Args:
            player_name (str): Name of the player for whom the injury is being recorded.
            injury_data (InjuryDataPayload): Dictionary of injury details captured from
                the UI, including type, dates, and expected return.

        Raises:
            IncompleteDataError: If player_name is blank or injury_data is empty.
            DataPersistenceError: If the backend fails to validate or save the
                injury record, including incorrect date formatting.
        """
        # Validate critical context before hitting the DataManager
        if not player_name or not player_name.strip():
            logger.error("Injury save aborted: Player name is missing.")
            raise IncompleteDataError("Cannot save injury: No player selected.")

        if not injury_data:
            logger.error("Injury save aborted: No data provided for %s.", player_name)
            raise IncompleteDataError(
                "Cannot save injury: Injury data fields are empty."
            )

        logger.info("Initiating injury record save for player '%s'", player_name)

        # Cross the Pydantic Boundary
        try:
            self._data_manager.add_injury_record(player_name, injury_data)
        except Exception as e:
            logger.error(
                "Failed to persist injury data for %s: %s",
                player_name,
                e,
                exc_info=True,
            )
            raise DataPersistenceError(f"Failed to save injury data: {e}") from e

    def sell_player(self, player_name: str, in_game_date: str) -> None:
        """Record the sale of a player on a specific in-game date.

        Validates basic context, forwards the sale request to the DataManager, and
        converts backend failures into a UI-friendly persistence error.

        Args:
            player_name (str): Name of the player being marked as sold.
            in_game_date (str): In-game date when the sale occurs.

        Raises:
            IncompleteDataError: If player name or in-game date is missing/blank.
            DataPersistenceError: If DataManager fails to record the sale.
        """
        if not player_name or not player_name.strip():
            logger.error("Sell action aborted: No player name provided.")
            raise IncompleteDataError("Cannot sell: No player selected.")

        if not in_game_date or not in_game_date.strip():
            logger.error("Sell action aborted: No in-game date provided.")
            raise IncompleteDataError("Cannot sell: In-game date is required.")

        logger.info("Routing sell request for player: %s", player_name)
        try:
            self._data_manager.sell_player(player_name, in_game_date)
        except Exception as e:
            logger.error(
                "Failed to sell player '%s': %s",
                player_name,
                e,
                exc_info=True,
            )
            raise DataPersistenceError(f"Failed to sell player: {e}") from e

    def loan_out_player(self, player_name: str) -> None:
        """Mark a player as loaned out for the current career context.

        Performs basic validation, forwards the loan-out request to the DataManager,
        and wraps backend errors so the UI receives a consistent failure signal.

        Args:
            player_name (str): Name of the player being sent out on loan.

        Raises:
            IncompleteDataError: If no player name is provided or it is blank.
            DataPersistenceError: If the underlying DataManager cannot update the
                player's loan status.
        """
        if not player_name or not player_name.strip():
            logger.error("Loan out action aborted: No player name provided.")
            raise IncompleteDataError("Cannot loan out: No player selected.")

        logger.info("Routing loan out request for player: %s", player_name)
        try:
            self._data_manager.loan_out_player(player_name)
        except Exception as e:
            logger.error(
                "Failed to loan out player '%s': %s",
                player_name,
                e,
                exc_info=True,
            )
            raise DataPersistenceError(f"Failed to loan out player: {e}") from e

    def return_loan_player(self, player_name: str) -> None:
        """Mark a loaned player as returned to the parent club.

        Validates the provided player name, delegates the return operation to
        the DataManager, and wraps backend failures for consistent UI handling.

        Args:
            player_name (str): Name of the player being returned from loan.

        Raises:
            IncompleteDataError: If the player name is missing or blank.
            DataPersistenceError: If the underlying DataManager fails to update
                the player's loan status.
        """
        if not player_name or not player_name.strip():
            logger.error("Return loan action aborted: No player name provided.")
            raise IncompleteDataError("Cannot return from loan: No player selected.")

        logger.info("Routing return from loan request for player: %s", player_name)
        try:
            self._data_manager.return_loan_player(player_name)
        except Exception as e:
            logger.error(
                "Failed to return player '%s' from loan: %s",
                player_name,
                e,
                exc_info=True,
            )
            raise DataPersistenceError(f"Failed to return player from loan: {e}") from e

    def get_all_player_names(
        self,
        only_outfield: bool = False,
        only_gk: bool = False,
        remove_on_loan: bool = False,
    ) -> list[str]:
        """Return a filtered, surname-sorted list of active player names.

        Syncs in-memory players with storage, applies loan and positional filters,
        and produces a UI-ready list of display names.

        Args:
            only_outfield (bool, optional): If True, include only non-goalkeepers
                in the returned list. Defaults to False.
            only_gk (bool, optional): If True, include only goalkeepers in the
                returned list. Defaults to False.
            remove_on_loan (bool, optional): If True, exclude players who are
                currently on loan. Defaults to False.

        Returns:
            list[str]: A list of title-cased player names sorted by surname.
                Returns an empty list when no players match the filters.
                Blank names are handled safely by sorting them with an empty
                surname key.
        """
        # Ensure memory is synced with disk before building the list
        self._data_manager.refresh_players()

        if not self._data_manager.players:
            return []

        # Filter out sold players
        active_players = [
            player
            for player in self._data_manager.players
            if not player.sold and not (remove_on_loan and player.loaned)
        ]

        # Make sure only_outfield and only_gk can't both be true
        if only_outfield and only_gk:
            logger.warning(
                "Both only_outfield and only_gk are True. Defaulting to no filter."
            )
            only_outfield = False
            only_gk = False

        # Apply positional filters using the Player model's `is_goalkeeper` property
        if only_outfield:
            active_players = [
                player for player in active_players if not player.is_goalkeeper
            ]
        elif only_gk:
            active_players = [
                player for player in active_players if player.is_goalkeeper
            ]

        # Extract and sort player names by surname
        if active_players:

            def _surname_sort_key(name: str) -> tuple[str, str]:
                parts = name.split()
                surname = parts[-1] if parts else ""
                return surname.casefold(), name.casefold()

            return sorted(
                [player.name.title() for player in active_players],
                key=_surname_sort_key,
            )
        return []

    def get_player_bio(self, name: str) -> PlayerBioDict | None:
        """Return a lightweight bio snapshot for a single player by name.

        Looks up the player in the DataManager and, if found, exposes key bio
        fields in a UI-friendly dictionary shape.

        Args:
            name (str): Name of the player whose bio information is requested.

        Returns:
            PlayerBioDict | None: Dictionary containing age, height, weight,
            country, and positions for the player, or None if not found.
        """
        player = self._data_manager.find_player_by_name(name)
        if player is None:
            return None
        return {
            "age": player.age,
            "height": player.height,
            "weight": player.weight,
            "country": player.nationality,
            "positions": player.positions,
        }
