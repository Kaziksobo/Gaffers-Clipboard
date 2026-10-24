"""Fixtures for tests that run against the real career datasets in ``datasets/``.

These tests read the same career saves the workshop calibrates on, so they catch
problems synthetic payloads cannot: an old-schema save failing to load, the rating
service raising on a real position or formation, or a dataset being overwritten by
an older export.

Any test that takes a ``career_name`` argument is automatically run once per career
registered in ``datasets/careers.toml``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from src.contracts.backend import MatchOverviewPayload, PlayerPerformancePayload
from src.data_manager import DataManager
from src.services.analytics.match_ratings_service import MatchRatingsService

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATASETS_DIR = _PROJECT_ROOT / "datasets"
_CONFIG_DIR = _PROJECT_ROOT / "config"

SLICE_MATCHES = 10

type RateFn = Callable[..., float | None]
type ProjectBuilder = Callable[..., DataManager]


@dataclass(frozen=True)
class CareerRecords:
    """Raw records of one career dataset."""

    name: str
    club: str
    metadata: dict[str, Any]
    matches: list[dict[str, Any]]
    players: list[dict[str, Any]]


@dataclass(frozen=True)
class RatedPerformance:
    """One real performance together with the rating the service gave it."""

    career: str
    club: str
    match_id: int
    player_id: int
    performance_type: str
    minutes: float | None
    rating: float | None
    match_data: dict[str, Any]
    performance: dict[str, Any]


def _read_manifest() -> dict[str, dict[str, Any]]:
    """Read ``datasets/careers.toml``."""
    with (_DATASETS_DIR / "careers.toml").open("rb") as f:
        return tomllib.load(f)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrise any test taking ``career_name`` over every registered career."""
    if "career_name" in metafunc.fixturenames:
        metafunc.parametrize("career_name", sorted(_read_manifest()))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the repository root."""
    return _PROJECT_ROOT


@pytest.fixture(scope="session")
def slice_matches() -> int:
    """Return how many leading matches ``build_career_project`` copies by default."""
    return SLICE_MATCHES


@pytest.fixture(scope="session")
def datasets_dir() -> Path:
    """Return the ``datasets/`` directory."""
    return _DATASETS_DIR


@pytest.fixture(scope="session")
def manifest() -> dict[str, dict[str, Any]]:
    """Return the parsed career manifest keyed by folder name."""
    return _read_manifest()


@pytest.fixture(scope="session")
def careers(manifest: dict[str, dict[str, Any]]) -> dict[str, CareerRecords]:
    """Load every registered career's raw records once per session."""
    loaded: dict[str, CareerRecords] = {}
    for name, entry in manifest.items():
        folder = _DATASETS_DIR / "careers" / name
        loaded[name] = CareerRecords(
            name=name,
            club=entry["club"],
            metadata=json.loads((folder / "metadata.json").read_text("utf-8")),
            matches=json.loads((folder / "matches.json").read_text("utf-8")),
            players=json.loads((folder / "players.json").read_text("utf-8")),
        )
    return loaded


@pytest.fixture(scope="session")
def import_career() -> ModuleType:
    """Load ``scripts/import_career.py`` so tests reuse its validation checks."""
    path = _PROJECT_ROOT / "scripts" / "import_career.py"
    spec = importlib.util.spec_from_file_location("import_career", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def ratings_service() -> MatchRatingsService:
    """Return a MatchRatingsService built from the live ``config/`` files."""
    weights = json.loads((_CONFIG_DIR / "performance_weights.json").read_text("utf-8"))
    means_stds = json.loads(
        (_CONFIG_DIR / "performance_means_stds.json").read_text("utf-8")
    )
    return MatchRatingsService(weights, means_stds)


@pytest.fixture(scope="session")
def rate(ratings_service: MatchRatingsService) -> RateFn:
    """Return ``rate(club, match_data, performance, half_length=None)``.

    Routes goalkeepers and outfield players to the right pipeline and ignores any
    stored ``match_rating``, exactly as the app does when saving a match.
    """

    def _rate(
        club: str,
        match_data: dict[str, Any],
        performance: dict[str, Any],
        half_length: int | None = None,
    ) -> float | None:
        perf = cast(
            "PlayerPerformancePayload",
            {k: v for k, v in performance.items() if k != "match_rating"},
        )
        overview = cast("MatchOverviewPayload", match_data)
        half = half_length if half_length is not None else match_data["half_length"]
        if performance["performance_type"] == "GK":
            return ratings_service.calculate_gk_rating(perf, overview, half, club)
        return ratings_service.calculate_outfield_rating(perf, overview, half, club)

    return _rate


@pytest.fixture(scope="session")
def rated_performances(
    careers: dict[str, CareerRecords], rate: RateFn
) -> list[RatedPerformance]:
    """Rate every performance in every career once per session."""
    rated: list[RatedPerformance] = []
    for career in careers.values():
        for match in career.matches:
            for perf in match["player_performances"]:
                rated.append(
                    RatedPerformance(
                        career=career.name,
                        club=career.club,
                        match_id=match["id"],
                        player_id=perf["player_id"],
                        performance_type=perf["performance_type"],
                        minutes=perf.get("minutes_played"),
                        rating=rate(career.club, match["data"], perf),
                        match_data=match["data"],
                        performance=perf,
                    )
                )
    return rated


@pytest.fixture
def build_career_project(
    tmp_path: Path, careers: dict[str, CareerRecords], rate: RateFn
) -> ProjectBuilder:
    """Return a factory that copies a slice of a career into a scratch ``data/``.

    The factory writes ``careers_details.json`` plus the career folder under
    ``tmp_path/data`` (the layout ``DataManager`` expects) and returns a
    ``DataManager`` rooted at ``tmp_path``. The datasets themselves are never
    written to.

    Args:
        name: Career folder name.
        matches: Number of leading matches to include (``None`` for all).
        rated: Store freshly computed ratings in ``match_rating``.
        drop_player_keys: Player keys to remove, to simulate an older save schema.
    """

    def _build(
        name: str,
        matches: int | None = SLICE_MATCHES,
        *,
        rated: bool = False,
        drop_player_keys: tuple[str, ...] = (),
    ) -> DataManager:
        career = careers[name]
        folder = tmp_path / "data" / name
        folder.mkdir(parents=True)

        match_slice = copy.deepcopy(career.matches[:matches])
        for match in match_slice:
            for perf in match["player_performances"]:
                perf["match_rating"] = (
                    rate(career.club, match["data"], perf) if rated else None
                )
        players = copy.deepcopy(career.players)
        for player in players:
            for key in drop_player_keys:
                player.pop(key, None)

        (folder / "matches.json").write_text(json.dumps(match_slice), "utf-8")
        (folder / "players.json").write_text(json.dumps(players), "utf-8")
        (folder / "metadata.json").write_text(json.dumps(career.metadata), "utf-8")
        details = [
            {
                "id": career.metadata["career_id"],
                "club_name": career.club,
                "folder_name": name,
            }
        ]
        (tmp_path / "data" / "careers_details.json").write_text(
            json.dumps(details), "utf-8"
        )
        return DataManager(project_root=tmp_path)

    return _build
