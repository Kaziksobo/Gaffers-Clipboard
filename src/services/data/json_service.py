"""JSON persistence helpers used by DataManager's internal data services."""

import json
import logging
from pathlib import Path
from typing import Literal, TypeVar, overload

from pydantic import BaseModel, TypeAdapter, ValidationError

from src.contracts.backend import (
    JsonValue,
    ReadRawJsonResult,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class JsonService:
    """Handle JSON read, validation, and write operations."""

    @overload
    def load_json(
        self,
        path: Path,
        model_class: type[T],
        is_list: Literal[True] = True,
    ) -> list[T]: ...

    @overload
    def load_json(
        self,
        path: Path,
        model_class: type[T],
        is_list: Literal[False] = False,
    ) -> T | None: ...

    def load_json(
        self,
        path: Path,
        model_class: type[T],
        is_list: bool = True,
    ) -> list[T] | T | None:
        """Load and validate JSON data from disk into Pydantic models.

        This method handles both single objects and lists of objects, returning
        a default value (empty list or None) when the file is missing or invalid.

        Args:
            path (Path): The file path to load the JSON data from.
            model_class (type[T]): The Pydantic model class to validate
                                   the data against.
            is_list (bool, optional): Whether the JSON data represents a
                                      list of models. Defaults to True.

        Returns:
            list[T] | T | None: The loaded and validated data, or a fallback value.
        """
        if is_list:
            list_fallback: list[T] = []
            loaded, raw_data = self._read_raw_json(path)
            if not loaded:
                return list_fallback
            return self._validate_list_json(path, model_class, raw_data, list_fallback)

        loaded, raw_data = self._read_raw_json(path)
        if not loaded:
            return None

        return self._validate_single_json(path, model_class, raw_data)

    @staticmethod
    def _read_raw_json(path: Path) -> ReadRawJsonResult:
        """Safely read raw JSON content from disk without validation.

        Returns a success flag alongside the parsed JSON value,
        logging and falling back when files are missing or unreadable.

        Args:
            path (Path): The JSON file path to read from.

        Returns:
            ReadRawJsonResult: A tuple of (loaded_flag, raw_json_value_or_none).
        """
        if not path.exists():
            logger.warning("File not found at %s. Returning default value.", path)
            return False, None

        try:
            with Path.open(path, encoding="utf-8") as f:
                return True, json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Error loading JSON from %s: %s", path, e, exc_info=True)
            return False, None

    @staticmethod
    def _validate_single_json(
        path: Path,
        model_class: type[T],
        raw_data: JsonValue,
    ) -> T | None:
        """Validate a single JSON-compatible value against a Pydantic model.

        Converts the raw JSON structure into a typed model instance,
        logging and returning None when validation fails.

        Args:
            path (Path): The source file path used for logging context.
            model_class (type[T]): The Pydantic model class to validate against.
            raw_data (JsonValue): The decoded JSON value to validate.

        Returns:
            T | None: The validated model instance, or None if validation fails.
        """
        adapter = TypeAdapter(model_class)
        try:
            return adapter.validate_python(raw_data)
        except ValidationError:
            logger.error("Validation failed for %s, returning default.", path)
            return None

    @staticmethod
    def _validate_list_json(
        path: Path,
        model_class: type[T],
        raw_data: JsonValue,
        fallback: list[T],
    ) -> list[T]:  # sourcery skip: extract-method
        """Validate a JSON-compatible list against a Pydantic model type.

        Attempts full-list validation first, then falls back to per-item validation
        to recover as many valid models as possible while logging any invalid entries.

        Args:
            path (Path): The source file path used for logging context.
            model_class (type[T]): The Pydantic model class to validate
                                   each item against.
            raw_data (JsonValue): The decoded JSON value expected to be a list.
            fallback (list[T]): The list to return when validation cannot proceed.

        Returns:
            list[T]: A list of validated model instances, or the fallback
                     when validation fails.
        """
        if not isinstance(raw_data, list):
            logger.error(
                "Expected list in %s but got %s. Returning fallback.",
                path,
                type(raw_data).__name__,
            )
            return fallback

        item_adapter = TypeAdapter(model_class)
        try:
            return [item_adapter.validate_python(item) for item in raw_data]
        except ValidationError:
            # Partial recovery: validate each item individually
            logger.warning(
                "Full list validation failed for %s. Attempting partial recovery.",
                path,
            )
            recovered = []
            skipped = 0
            for i, item in enumerate(raw_data):
                try:
                    recovered.append(item_adapter.validate_python(item))
                except ValidationError as e:
                    skipped += 1
                    first_error = e.errors()[0] if e.errors() else {}
                    location = first_error.get("loc", ())
                    message = first_error.get("msg", "Unknown validation error")
                    logger.warning(
                        "Skipped invalid item at index %s in %s. First error at %s: %s",
                        i,
                        path,
                        location,
                        message,
                    )
            logger.warning(
                "Partial recovery: %s valid, %s skipped from %s.",
                len(recovered),
                skipped,
                path,
            )
            return recovered

    @staticmethod
    def load_raw_list_or_raise(path: Path) -> list[JsonValue]:
        """Load a raw JSON list from disk without schema validation.

        This helper is intended for append workflows where existing rows must be
        preserved exactly, even if individual entries are schema-invalid.

        Args:
            path (Path): JSON file path expected to contain a top-level list.

        Raises:
            ValueError: If the file cannot be read or does not contain a list.

        Returns:
            list[JsonValue]: Raw list entries loaded from disk.
        """
        if not path.exists():
            return []

        try:
            with Path.open(path, encoding="utf-8") as f:
                raw_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Unable to read JSON list from {path}: {e}") from e

        if not isinstance(raw_data, list):
            raise ValueError(
                f"Expected a JSON list in {path}, got {type(raw_data).__name__}."
            )

        return raw_data

    def append_item_to_json_list_atomic_or_raise(
        self,
        path: Path,
        item: JsonValue | BaseModel,
    ) -> None:
        """Append one item to a JSON list file while preserving existing rows.

        Existing entries are loaded and written back without schema validation so
        malformed historical rows are not dropped or normalized.

        Args:
            path (Path): Destination JSON list file.
            item (JsonValue | BaseModel): New entry to append.

        Raises:
            ValueError: If the target file cannot be read as a JSON list.
            OSError: If writing/replacing the target file fails.
            TypeError: If the resulting payload is not JSON serializable.
        """
        existing_rows = self.load_raw_list_or_raise(path)
        item_payload: JsonValue = (
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item
        )
        existing_rows.append(item_payload)
        self.save_json_atomic_or_raise(path, existing_rows)

    @staticmethod
    def load_list_strict_or_raise(path: Path, model_class: type[T]) -> list[T]:
        """Load a list of JSON objects from disk and validate them strictly.

        This method enforces that the file exists, contains a list, and that every item
        in the list conforms to the specified model. If any of these conditions
        are not met, it raises a ValueError with a descriptive message.

        Args:
            path (Path): The file path to load the JSON data from.
            model_class (type[T]): The Pydantic model class to
                                   validate each item against.

        Raises:
            ValueError: If the file cannot be read, is not a list,
                        or if any item fails validation.

        Returns:
            list[T]: A list of validated model instances loaded from the JSON file.
        """
        if not path.exists():
            return []

        try:
            with Path.open(path, encoding="utf-8") as f:
                raw_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(
                f"Refusing to save: unable to read {path.name} at {path}: {e}"
            ) from e

        if not isinstance(raw_data, list):
            raise ValueError(
                "Refusing to save: "
                f"{path.name} must contain a list, got "
                f"{type(raw_data).__name__}."
            )

        try:
            item_adapter = TypeAdapter(model_class)
            return [item_adapter.validate_python(item) for item in raw_data]
        except ValidationError as e:
            raise ValueError(
                "Refusing to save: "
                f"{path.name} failed strict validation with "
                f"{len(e.errors())} errors."
            ) from e

    @staticmethod
    def _serialize_for_json(
        data: JsonValue | T | list[T] | list[JsonValue] | None,
    ) -> object:
        """Convert model and raw payloads into JSON-serializable data.

        This helper normalizes None to an empty list, extracts JSON-compatible
        dictionaries from model instances, and leaves already-serializable
        values untouched.
        """
        if data is None:
            return []

        if isinstance(data, list):
            return [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in data
            ]

        elif isinstance(data, BaseModel):
            return data.model_dump(mode="json")
        else:
            return data

    def save_json(
        self,
        path: Path,
        data: JsonValue | T | list[T] | list[JsonValue] | None = None,
    ) -> None:
        """Save the provided data as JSON to the specified file path.

        Automatically handles serialization for both single Pydantic models
        and lists of models. Overwrites the file if it already exists.

        Args:
            path (Path): The path to the JSON file.
            data (JsonValue | T | list[T] | list[JsonValue] | None):
                The data to save. If None, an empty list is
                saved to clear the file.
        """
        try:
            export_data = self._serialize_for_json(data)

            # Write to file
            with Path.open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4)

        except (OSError, TypeError) as e:
            logger.error("Failed to save JSON to %s: %s", path, e, exc_info=True)

    def save_json_atomic_or_raise(
        self,
        path: Path,
        data: JsonValue | T | list[T] | list[JsonValue] | None = None,
    ) -> None:
        """Atomically write JSON data to disk, failing closed on any error.

        Serializes Pydantic models to JSON, writes to a temporary file,
        and then replaces the target to avoid partial writes.

        Args:
            path (Path): Destination path for the JSON file.
            data (JsonValue | T | list[T] | list[JsonValue] | None):
                Model instance(s) or raw JSON-compatible data to persist.

        Raises:
            OSError: If there are issues writing to disk or replacing the file.
            TypeError: If the provided data cannot be serialized to JSON.
        """
        export_data = self._serialize_for_json(data)

        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        with Path.open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=4)
        tmp_path.replace(path)
