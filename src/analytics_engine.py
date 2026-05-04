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

from src.contracts.backend import (
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
        # Importing weights, means and stds
        config_path: Path = self.project_root / "config"
        weights_path: Path = config_path / "performance_weights.json"
        means_stds_path: Path = config_path / "performance_means_stds.json"
        with Path.open(weights_path) as f:
            weights: PerformanceWeightsMap = json.load(f)
        with Path.open(means_stds_path) as f:
            means_stds: PerformanceMeansStdsMap = json.load(f)

        # Initialising MatchRatingsService
        match_ratings_service = analytics_services.MatchRatingsService(
            weights, means_stds
        )

        if performance.get("performance_type") == "GK":
            return match_ratings_service.calculate_gk_rating(
                performance, match_overview, half_length, team_name
            )

        else:
            return match_ratings_service.calculate_outfield_rating(
                performance, match_overview, half_length, team_name
            )
