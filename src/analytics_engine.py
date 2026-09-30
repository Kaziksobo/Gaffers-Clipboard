"""
AnalyticsEngine - match rating orchestration.

This module defines `AnalyticsEngine`, a lightweight coordinator that loads
rating configuration and delegates match rating calculations to analytics
services.

Responsibilities:
- Load performance weights and mean/std configuration from config files.
- Instantiate analytics services with configuration.
- Route player performance payloads to GK or outfield rating pipelines.

The engine focuses on orchestration and configuration loading; rating logic
lives in analytics services.
"""

import json
import logging
from pathlib import Path
from typing import cast

from services.analytics.match_ratings_service import MatchRatingsService
from src.contracts.backend import (
    JsonValue,
    MatchOverviewPayload,
    PerformanceMeansStdsMap,
    PerformanceWeightsMap,
    PlayerPerformancePayload,
)
from src.services import analytics as analytics_services

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Coordinate analytics workflows for match rating calculations.

    AnalyticsEngine loads configuration from disk and delegates the actual
    scoring logic to the analytics service layer.
    """

    def __init__(self, project_root: Path):
        """Initialize the engine with the project root for configuration access.

        Args:
            project_root (Path): Root directory of the project used to locate
                performance weighting and normalization configuration files.
        """
        self.project_root = project_root

        self._config_cache: dict[str, JsonValue] = {}

        self._match_ratings_service: analytics_services.MatchRatingsService | None = (
            None
        )

    def _load_config[T](self, filename: str) -> T:
        """Load a JSON config file from `config/`, caching the parsed result.

        The file is read from disk on first request only; later calls for the
        same filename return the cached value.

        Args:
            filename (str): Name of the file inside the project's `config/`
                directory, e.g. "performance_weights.json".

        Raises:
            FileNotFoundError: If the configuration file is missing.
            json.JSONDecodeError: If the file contains invalid JSON.
            OSError: For other I/O errors when reading the file.

        Returns:
            T: The parsed JSON, cast to the caller's expected config type. The
                shape is not validated at runtime.
        """
        if filename not in self._config_cache:
            path: Path = self.project_root / "config" / filename
            with path.open(encoding="utf-8") as f:
                self._config_cache[filename] = json.load(f)
        return cast("T", self._config_cache[filename])

    def _get_match_rating_service(self) -> analytics_services.MatchRatingsService:
        """Return the cached match ratings service, creating it on first use.

        On the first call, loads the performance weights and historical
        means/standard deviations through `_load_config()`, constructs a
        `MatchRatingsService` from them, and caches the instance. Later calls
        return the cached instance without touching disk.

        Raises:
            FileNotFoundError: If a configuration file is missing.
            json.JSONDecodeError: If a configuration file contains invalid JSON.
            OSError: For other I/O errors when reading configuration files.

        Returns:
            MatchRatingsService: The shared service instance used to calculate
                goalkeeper and outfield ratings.
        """
        if self._match_ratings_service is None:
            weights: PerformanceWeightsMap = self._load_config(
                "performance_weights.json"
            )
            means_stds: PerformanceMeansStdsMap = self._load_config(
                "performance_means_stds.json"
            )
            self._match_ratings_service = analytics_services.MatchRatingsService(
                weights, means_stds
            )
        return self._match_ratings_service

    def calculate_match_rating(
        self,
        performance: PlayerPerformancePayload,
        match_overview: MatchOverviewPayload,
        half_length: int,
        team_name: str,
    ) -> float | None:
        """Calculate a match rating from performance and match context.

        Loads rating configuration, initializes the match rating service, and
        routes goalkeepers and outfield players through the correct pipeline.

        Args:
            performance (PlayerPerformancePayload): Raw player performance
                metrics for the match.
            match_overview (MatchOverviewPayload): Match summary data including
                xG, scores, and team context.
            half_length (int): Length of each half in in-game minutes used to
                normalize volume statistics.
            team_name (str): Name of the player's team for home/away context.

        Raises:
            FileNotFoundError: If the configuration files are missing.
            json.JSONDecodeError: If the configuration files contain invalid JSON.
            OSError: For other I/O errors when reading configuration files.

        Returns:
            float | None: The calculated match rating on a 0-10 scale, or None
                if the player did not play enough minutes to rate.
        """
        logger.debug(
            (
                "Calculating match rating "
                "(player_id=%s, type=%s, team=%s, half_length=%s)."
            ),
            performance.get("player_id"),
            performance.get("performance_type"),
            team_name,
            half_length,
        )
        service: MatchRatingsService = self._get_match_rating_service()

        if performance.get("performance_type") == "GK":
            logger.debug("Routing to GK rating pipeline.")
            return service.calculate_gk_rating(
                performance, match_overview, half_length, team_name
            )

        else:
            logger.debug("Routing to outfield rating pipeline.")
            return service.calculate_outfield_rating(
                performance, match_overview, half_length, team_name
            )
