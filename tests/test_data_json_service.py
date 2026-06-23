"""Tests for the data-layer JsonService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from src.services.data.json_service import JsonService


class _Simple(BaseModel):
    """Minimal Pydantic model used as a test fixture."""

    value: int


@pytest.fixture
def service() -> JsonService:
    """Return a fresh JsonService."""
    return JsonService()


# ---------------------------------------------------------------------------
# load_json — single-object mode (is_list=False)
# ---------------------------------------------------------------------------


def test_load_json_single_returns_none_when_file_missing(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """load_json (is_list=False) returns None when the target file does not exist."""
    result = service.load_json(tmp_path / "missing.json", _Simple, is_list=False)

    assert result is None


def test_load_json_single_loads_and_validates_valid_file(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """load_json (is_list=False) returns a validated model from a well-formed file."""
    path = tmp_path / "item.json"
    path.write_text(json.dumps({"value": 42}), encoding="utf-8")

    result = service.load_json(path, _Simple, is_list=False)

    assert isinstance(result, _Simple)
    assert result.value == 42


def test_load_json_single_returns_none_on_validation_failure(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """load_json (is_list=False) returns None when the JSON does not match the model."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"value": "not-an-int"}), encoding="utf-8")

    result = service.load_json(path, _Simple, is_list=False)

    assert result is None


# ---------------------------------------------------------------------------
# _read_raw_json — error paths
# ---------------------------------------------------------------------------


def test_read_raw_json_returns_false_on_corrupt_file(tmp_path: Path) -> None:
    """_read_raw_json returns (False, None) when the file contains invalid JSON."""
    path = tmp_path / "corrupt.json"
    path.write_text("not json !!!", encoding="utf-8")

    loaded, data = JsonService._read_raw_json(path)

    assert loaded is False
    assert data is None


# ---------------------------------------------------------------------------
# load_json — list mode (is_list=True, default)
# ---------------------------------------------------------------------------


def test_load_json_list_returns_empty_when_file_missing(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """load_json (is_list=True) returns [] when the target file does not exist."""
    result = service.load_json(tmp_path / "missing.json", _Simple)

    assert result == []


def test_load_json_list_loads_and_validates_valid_list(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """load_json (is_list=True) returns a list of validated models from a list file."""
    path = tmp_path / "items.json"
    path.write_text(json.dumps([{"value": 1}, {"value": 2}]), encoding="utf-8")

    result = service.load_json(path, _Simple)

    assert len(result) == 2
    assert result[0].value == 1
    assert result[1].value == 2


def test_load_json_list_returns_fallback_when_json_is_not_a_list(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """load_json (is_list=True) returns [] when the JSON root is not a list."""
    path = tmp_path / "obj.json"
    path.write_text(json.dumps({"value": 1}), encoding="utf-8")

    result = service.load_json(path, _Simple)

    assert result == []


def test_load_json_list_recovers_valid_items_when_some_are_invalid(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """load_json (is_list=True) partially recovers valid items when some entries are bad."""
    path = tmp_path / "mixed.json"
    path.write_text(
        json.dumps([{"value": 1}, {"value": "bad"}, {"value": 3}]),
        encoding="utf-8",
    )

    result = service.load_json(path, _Simple)

    assert len(result) == 2
    assert result[0].value == 1
    assert result[1].value == 3


# ---------------------------------------------------------------------------
# load_raw_list_or_raise
# ---------------------------------------------------------------------------


def test_load_raw_list_or_raise_returns_empty_when_file_missing(
    tmp_path: Path,
) -> None:
    """load_raw_list_or_raise returns [] when the file does not exist."""
    result = JsonService.load_raw_list_or_raise(tmp_path / "missing.json")

    assert result == []


def test_load_raw_list_or_raise_raises_on_corrupt_file(tmp_path: Path) -> None:
    """load_raw_list_or_raise raises ValueError when the file is not valid JSON."""
    path = tmp_path / "corrupt.json"
    path.write_text("!!!", encoding="utf-8")

    with pytest.raises(ValueError, match="Unable to read JSON list"):
        JsonService.load_raw_list_or_raise(path)


def test_load_raw_list_or_raise_raises_when_json_is_not_a_list(
    tmp_path: Path,
) -> None:
    """load_raw_list_or_raise raises ValueError when the JSON root is not a list."""
    path = tmp_path / "obj.json"
    path.write_text(json.dumps({"key": "value"}), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a JSON list"):
        JsonService.load_raw_list_or_raise(path)


def test_load_raw_list_or_raise_returns_raw_entries(tmp_path: Path) -> None:
    """load_raw_list_or_raise returns the raw list entries without validation."""
    path = tmp_path / "data.json"
    path.write_text(json.dumps([{"value": 1}, {"value": 2}]), encoding="utf-8")

    result = JsonService.load_raw_list_or_raise(path)

    assert result == [{"value": 1}, {"value": 2}]


# ---------------------------------------------------------------------------
# load_list_strict_or_raise
# ---------------------------------------------------------------------------


def test_load_list_strict_or_raise_returns_empty_when_file_missing(
    tmp_path: Path,
) -> None:
    """load_list_strict_or_raise returns [] when the target file is absent."""
    result = JsonService.load_list_strict_or_raise(tmp_path / "missing.json", _Simple)

    assert result == []


def test_load_list_strict_or_raise_raises_on_corrupt_file(tmp_path: Path) -> None:
    """load_list_strict_or_raise raises ValueError when the file is not valid JSON."""
    path = tmp_path / "corrupt.json"
    path.write_text("!!!", encoding="utf-8")

    with pytest.raises(ValueError, match="unable to read"):
        JsonService.load_list_strict_or_raise(path, _Simple)


def test_load_list_strict_or_raise_raises_when_root_is_not_list(
    tmp_path: Path,
) -> None:
    """load_list_strict_or_raise raises ValueError when the JSON root is not a list."""
    path = tmp_path / "obj.json"
    path.write_text(json.dumps({"value": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a list"):
        JsonService.load_list_strict_or_raise(path, _Simple)


def test_load_list_strict_or_raise_raises_on_invalid_items(tmp_path: Path) -> None:
    """load_list_strict_or_raise raises ValueError when any item fails validation."""
    path = tmp_path / "bad_items.json"
    path.write_text(json.dumps([{"value": "not-an-int"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="failed strict validation"):
        JsonService.load_list_strict_or_raise(path, _Simple)


def test_load_list_strict_or_raise_returns_validated_list(tmp_path: Path) -> None:
    """load_list_strict_or_raise returns a validated model list for a valid file."""
    path = tmp_path / "data.json"
    path.write_text(json.dumps([{"value": 10}, {"value": 20}]), encoding="utf-8")

    result = JsonService.load_list_strict_or_raise(path, _Simple)

    assert len(result) == 2
    assert result[0].value == 10


# ---------------------------------------------------------------------------
# _serialize_for_json — BaseModel branch
# ---------------------------------------------------------------------------


def test_serialize_for_json_handles_single_base_model() -> None:
    """_serialize_for_json converts a single BaseModel to a JSON-compatible dict."""
    model = _Simple(value=99)

    result = JsonService._serialize_for_json(model)

    assert result == {"value": 99}


def test_serialize_for_json_handles_none_as_empty_list() -> None:
    """_serialize_for_json converts None to an empty list."""
    result = JsonService._serialize_for_json(None)

    assert result == []


def test_serialize_for_json_handles_list_of_models() -> None:
    """_serialize_for_json converts a list of BaseModel instances to dicts."""
    models = [_Simple(value=1), _Simple(value=2)]

    result = JsonService._serialize_for_json(models)

    assert result == [{"value": 1}, {"value": 2}]


# ---------------------------------------------------------------------------
# save_json — error path
# ---------------------------------------------------------------------------


def test_save_json_silently_handles_os_error(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """save_json does not raise when writing fails due to an OSError."""
    path = tmp_path / "subdir_that_does_not_exist" / "file.json"

    service.save_json(path, {"key": "value"})


# ---------------------------------------------------------------------------
# append_item_to_json_list_atomic_or_raise
# ---------------------------------------------------------------------------


def test_append_item_to_json_list_appends_to_existing_file(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """append_item_to_json_list_atomic_or_raise appends without losing existing rows."""
    path = tmp_path / "list.json"
    path.write_text(json.dumps([{"value": 1}]), encoding="utf-8")

    service.append_item_to_json_list_atomic_or_raise(path, {"value": 2})

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == [{"value": 1}, {"value": 2}]


def test_append_item_to_json_list_serializes_base_model(
    tmp_path: Path,
    service: JsonService,
) -> None:
    """append_item_to_json_list_atomic_or_raise serializes BaseModel instances."""
    path = tmp_path / "list.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    service.append_item_to_json_list_atomic_or_raise(path, _Simple(value=42))

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == [{"value": 42}]
