"""Fit and backtest helpers for the reliable rating (shrunk per-player estimate).

The reliable rating (``src/services/analytics/reliable_rating_service.py``) estimates a
player's underlying quality from their match ratings, shrunk toward a prior mean. Three
constants drive it: the prior mean, the between-player variance (``PRIOR_VARIANCE``) and
the within-player, match-to-match variance (``OBSERVATION_VARIANCE``). All three depend on
the live rating config, so they must be refitted after every promoted refit.

This module provides:

- **Data:** ``appearance_frame`` (one row per rated appearance, from ``datasets/``) and
  ``build_histories`` (the same rows as service ``PlayerRatingHistory`` payloads).
- **Variance components:** ``fit_variance_components`` (a one-way random-effects model
  with a player intercept, fitted by REML or ML), a player-level bootstrap, and
  ``VarianceComponents`` with the derived ``k`` and ICC.
- **Walk-forward backtest:** one-step-ahead predictions made by the real
  ``ReliableRatingService`` (so the fit and the runtime cannot diverge), scored against
  the raw running mean and the constant prior, plus a sweep over ``k`` and drift.

Match and player ids restart at 1 in every career, so players are keyed on
``"career:player_id"`` throughout, never on ``player_id`` alone.

Example:
    >>> from workshop.lib import reliable_rating as rr
    >>> frame = rr.appearance_frame("pool")
    >>> summaries = rr.player_summaries(frame)
    >>> fit = rr.fit_variance_components(summaries)
    >>> draws = rr.bootstrap_variance_components(summaries, n_resamples=1000)
    >>> rr.summarise_bootstrap(fit, draws)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from src.contracts.analytics import PlayerRatingHistory, RatedAppearance
from src.services.analytics.reliable_rating_service import ReliableRatingService
from src.utils import season_start_year
from workshop.lib import datasets, inference, rating

type Method = Literal["reml", "ml"]

# Candidate values of lambda = between_var / within_var. 0 is included explicitly because
# a zero between-player variance is a genuine possible answer, not just a limit.
_LAMBDA_GRID = np.concatenate(([0.0], np.logspace(-4, 2, 121)))


# ── Data ─────────────────────────────────────────────────────────────────────────


def appearance_frame(
    tag: str | None = "pool",
    names: list[str] | None = None,
    config_dir: Path | None = None,
) -> pd.DataFrame:
    """Return one row per rated appearance, ordered as the service expects.

    Ratings are recomputed with the live (or a candidate) config, because the stored
    ``match_rating`` is stripped in ``datasets/``. Performances too short to rate are
    dropped, since only rated appearances reach the reliable rating.

    Args:
        tag: Manifest tag selecting the careers (e.g. ``"pool"``).
        names: Explicit career names instead of a tag.
        config_dir: Rate with a candidate config instead of the live ``config/``.

    Returns:
        A frame with ``career``, ``player_key``, ``player_id``, ``name``, ``match_id``,
        ``in_game_date``, ``season`` (start year), ``primary_position`` and ``rating``,
        sorted by career, player, ``in_game_date`` then ``match_id``.
    """
    rated = rating.rated_performances(tag, names, config_dir=config_dir)
    roster = datasets.players(tag, names)[["career", "player_id", "name"]]
    frame = rated.loc[rated["rating"].notna()].merge(
        roster, on=["career", "player_id"], how="left", validate="many_to_one"
    )
    frame["player_key"] = frame["career"] + ":" + frame["player_id"].astype(str)
    frame["name"] = frame["name"].fillna(frame["player_key"])
    frame["season"] = frame["in_game_date"].map(season_start_year)
    frame = frame.sort_values(
        ["career", "player_id", "in_game_date", "match_id"], kind="stable"
    ).reset_index(drop=True)
    return frame[
        [
            "career",
            "player_key",
            "player_id",
            "name",
            "match_id",
            "in_game_date",
            "season",
            "primary_position",
            "rating",
        ]
    ]


def build_histories(frame: pd.DataFrame) -> dict[str, PlayerRatingHistory]:
    """Convert an appearance frame into service payloads, keyed by ``player_key``.

    The payload ``player_id`` is a unique integer code per player (not the career's own
    id, which collides across careers).

    Args:
        frame: Output of ``appearance_frame`` (chronological within each player).

    Returns:
        One ``PlayerRatingHistory`` per player, in frame order.
    """
    histories: dict[str, PlayerRatingHistory] = {}
    for code, (key, group) in enumerate(frame.groupby("player_key", sort=False)):
        appearances = [
            RatedAppearance(
                match_id=int(match_id),
                in_game_date=date.to_pydatetime(),
                rating=float(value),
            )
            for match_id, date, value in zip(
                group["match_id"], group["in_game_date"], group["rating"], strict=True
            )
        ]
        histories[str(key)] = PlayerRatingHistory(
            player_id=code,
            player_name=str(group["name"].iloc[0]),
            appearances=appearances,
            matches_since_last_rated=0,
        )
    return histories


# ── Variance components ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VarianceComponents:
    """Fitted components of the one-way random-effects model of match ratings.

    A rating is ``mu`` plus a player effect (variance ``between_var``) plus match noise
    (variance ``within_var``).
    """

    mu: float
    within_var: float
    between_var: float
    n_players: int
    n_rows: int

    @property
    def k(self) -> float:
        """Shrinkage strength: appearances' worth of weight carried by the prior."""
        if self.between_var <= 0:
            return float("inf")
        return self.within_var / self.between_var

    @property
    def icc(self) -> float:
        """Share of single-match rating variance that is stable player quality."""
        return self.between_var / (self.between_var + self.within_var)

    def reliability(self, n: float) -> float:
        """Reliability of a player's mean over ``n`` appearances, ``n / (n + k)``."""
        return self.between_var / (self.between_var + self.within_var / n)


def player_summaries(frame: pd.DataFrame) -> pd.DataFrame:
    """Reduce an appearance frame to per-player sufficient statistics.

    Returns:
        One row per ``player_key`` with ``n`` (rated appearances), ``mean`` and ``ssw``
        (within-player sum of squared deviations).
    """
    by_player = frame.groupby("player_key")["rating"]
    deviation = frame["rating"] - by_player.transform("mean")
    return pd.DataFrame(
        {
            "n": by_player.size(),
            "mean": by_player.mean(),
            "ssw": (deviation**2).groupby(frame["player_key"]).sum(),
        }
    )


def _profile(
    lams: np.ndarray,
    n: np.ndarray,
    ybar: np.ndarray,
    ssw: np.ndarray,
    method: Method,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Profile the (RE)ML criterion over lambda, for a whole grid at once.

    For a given lambda (between_var / within_var) the player-mean weights are
    ``n / (1 + n * lambda)``, the grand mean is the weighted mean of player means, and
    the within variance has a closed form. Returns ``(criterion, mu, within_var)``, each
    of length ``len(lams)``; the criterion is minus twice the profiled log-likelihood up
    to a constant.
    """
    lam = np.atleast_1d(lams)[:, None]
    weights = n / (1.0 + n * lam)
    weight_sum = weights.sum(axis=1)
    mu = (weights * ybar).sum(axis=1) / weight_sum
    quadratic = ssw.sum() + (weights * (ybar - mu[:, None]) ** 2).sum(axis=1)
    dof = n.sum() if method == "ml" else n.sum() - 1.0
    within = quadratic / dof
    criterion = dof * np.log(within) + np.log1p(n * lam).sum(axis=1)
    if method == "reml":
        criterion = criterion + np.log(weight_sum)
    return criterion, mu, within


def _fit_arrays(
    n: np.ndarray, ybar: np.ndarray, ssw: np.ndarray, method: Method
) -> VarianceComponents:
    """Fit the variance components from per-player arrays."""
    criterion, _, _ = _profile(_LAMBDA_GRID, n, ybar, ssw, method)
    best = int(np.argmin(criterion))
    if best in (0, len(_LAMBDA_GRID) - 1):
        # Boundary: no detectable between-player variance (lambda 0), or the grid ceiling.
        lam = float(_LAMBDA_GRID[best])
    else:
        result = minimize_scalar(
            lambda x: float(_profile(np.array([x]), n, ybar, ssw, method)[0][0]),
            bounds=(float(_LAMBDA_GRID[best - 1]), float(_LAMBDA_GRID[best + 1])),
            method="bounded",
            options={"xatol": 1e-9},
        )
        lam = float(result.x)
    _, mu, within = _profile(np.array([lam]), n, ybar, ssw, method)
    return VarianceComponents(
        mu=float(mu[0]),
        within_var=float(within[0]),
        between_var=float(lam * within[0]),
        n_players=len(n),
        n_rows=int(n.sum()),
    )


def fit_variance_components(
    summaries: pd.DataFrame, method: Method = "reml"
) -> VarianceComponents:
    """Fit the grand mean and the between- and within-player variances.

    One-way random-effects model with a player intercept, fitted by restricted maximum
    likelihood (default) or maximum likelihood. Unlike a method-of-moments estimate it
    weights players by how much evidence each carries and cannot return a negative
    variance: when the data show no player effect, ``between_var`` is exactly 0 (and
    ``k`` is infinite).

    Args:
        summaries: Output of ``player_summaries``.
        method: ``"reml"`` (less biased variances) or ``"ml"``.

    Returns:
        The fitted components.
    """
    return _fit_arrays(
        summaries["n"].to_numpy(float),
        summaries["mean"].to_numpy(float),
        summaries["ssw"].to_numpy(float),
        method,
    )


def bootstrap_variance_components(
    summaries: pd.DataFrame,
    n_resamples: int = 1000,
    seed: int = inference.DEFAULT_SEED,
    method: Method = "reml",
) -> pd.DataFrame:
    """Refit the components on resamples of whole players.

    Players are the independent units (a player's matches share their true level), so
    the bootstrap draws players with replacement and keeps each one's appearances
    together.

    Args:
        summaries: Output of ``player_summaries``.
        n_resamples: Number of bootstrap fits.
        seed: Seed for the resampling generator.
        method: Estimation method passed to the fit.

    Returns:
        One row per resample with ``mu``, ``within_var``, ``between_var``, ``k`` and
        ``icc``. ``k`` is infinite where a resample shows no player effect.
    """
    n = summaries["n"].to_numpy(float)
    ybar = summaries["mean"].to_numpy(float)
    ssw = summaries["ssw"].to_numpy(float)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float]] = []
    for _ in range(n_resamples):
        pick = rng.integers(0, len(n), size=len(n))
        fit = _fit_arrays(n[pick], ybar[pick], ssw[pick], method)
        rows.append(
            {
                "mu": fit.mu,
                "within_var": fit.within_var,
                "between_var": fit.between_var,
                "k": fit.k,
                "icc": fit.icc,
            }
        )
    return pd.DataFrame(rows)


def summarise_bootstrap(point: VarianceComponents, draws: pd.DataFrame) -> pd.DataFrame:
    """Tabulate point estimates with 95% percentile intervals.

    Nearest-rank percentiles are used so an infinite ``k`` (a resample with no player
    effect) never turns an interval bound into NaN.

    Args:
        point: The fit on the full data.
        draws: Output of ``bootstrap_variance_components``.

    Returns:
        One row per component with ``estimate``, ``ci_low`` and ``ci_high``.
    """
    estimates = {
        "mu": point.mu,
        "within_var": point.within_var,
        "between_var": point.between_var,
        "k": point.k,
        "icc": point.icc,
    }
    rows = {}
    for name, estimate in estimates.items():
        low, high = np.percentile(draws[name].to_numpy(), [2.5, 97.5], method="nearest")
        rows[name] = {"estimate": estimate, "ci_low": low, "ci_high": high}
    return pd.DataFrame(rows).T


# ── Walk-forward backtest ────────────────────────────────────────────────────────


def fitted_service(
    prior_mean: float,
    observation_variance: float,
    prior_variance: float,
    season_drift_variance: float = 0.0,
) -> ReliableRatingService:
    """Return a ``ReliableRatingService`` with candidate constants.

    The constants are class attributes, so a subclass overrides them without touching the
    shipped service or any global state.

    Args:
        prior_mean: Mean every estimate starts from.
        observation_variance: Within-player match-to-match variance.
        prior_variance: Between-player variance.
        season_drift_variance: Variance added per season elapsed (0 for none).
    """
    overrides = {
        "PRIOR_MEAN": prior_mean,
        "OBSERVATION_VARIANCE": observation_variance,
        "PRIOR_VARIANCE": prior_variance,
        "SEASON_DRIFT_VARIANCE": season_drift_variance,
    }
    return type("FittedReliableRatingService", (ReliableRatingService,), overrides)()


def walk_forward(
    histories: dict[str, PlayerRatingHistory],
    service: ReliableRatingService,
    min_prior: int = 1,
) -> pd.DataFrame:
    """Predict each rating from the player's earlier ratings only.

    For every appearance with at least ``min_prior`` earlier ones, the service is run on
    the earlier appearances and its estimate is the prediction. The predictive variance
    is the posterior variance, plus the drift accrued since the previous appearance, plus
    match noise.

    Args:
        histories: Output of ``build_histories``.
        service: Service (or ``fitted_service``) supplying the constants and the filter.
        min_prior: Minimum earlier appearances before a prediction is made (at least 1).

    Returns:
        One row per predicted appearance with ``player_key``, ``career``, ``t``
        (zero-based appearance index), ``season``, ``rating``, ``pred_mean``,
        ``pred_var``, ``raw_mean`` (mean of the earlier ratings) and ``prior_mean``.

    Raises:
        ValueError: If ``min_prior`` is below 1.
    """
    if min_prior < 1:
        raise ValueError("min_prior must be at least 1: a prediction needs evidence.")
    rows: list[dict[str, object]] = []
    for key, history in histories.items():
        appearances = history["appearances"]
        seasons = [season_start_year(a["in_game_date"]) for a in appearances]
        running_total = 0.0
        for t, appearance in enumerate(appearances):
            if t >= min_prior:
                prefix = PlayerRatingHistory(
                    player_id=history["player_id"],
                    player_name=history["player_name"],
                    appearances=appearances[:t],
                    matches_since_last_rated=0,
                )
                estimate = service.calculate_player_rating(prefix)
                assert estimate is not None
                gap = seasons[t] - seasons[t - 1]
                rows.append(
                    {
                        "player_key": key,
                        "career": key.split(":", maxsplit=1)[0],
                        "t": t,
                        "season": seasons[t],
                        "rating": appearance["rating"],
                        "pred_mean": estimate["rating"],
                        "pred_var": estimate["std_error"] ** 2
                        + service.SEASON_DRIFT_VARIANCE * gap
                        + service.OBSERVATION_VARIANCE,
                        "raw_mean": running_total / t,
                        "prior_mean": service.PRIOR_MEAN,
                    }
                )
            running_total += appearance["rating"]
    return pd.DataFrame(rows)


def score_predictions(predictions: pd.DataFrame) -> pd.Series:
    """Score walk-forward predictions against the two baselines.

    Returns:
        ``n`` predictions; mean squared error of the shrunk estimate (``mse_shrunk``), of
        the raw running mean (``mse_raw_mean``) and of the constant prior
        (``mse_prior``); and the mean Gaussian log predictive density
        (``mean_log_density``), which also rewards well-calibrated uncertainty.
    """
    error = predictions["rating"] - predictions["pred_mean"]
    log_density = -0.5 * (
        np.log(2 * np.pi * predictions["pred_var"]) + error**2 / predictions["pred_var"]
    )
    return pd.Series(
        {
            "n": float(len(predictions)),
            "mse_shrunk": float((error**2).mean()),
            "mse_raw_mean": float(
                ((predictions["rating"] - predictions["raw_mean"]) ** 2).mean()
            ),
            "mse_prior": float(
                ((predictions["rating"] - predictions["prior_mean"]) ** 2).mean()
            ),
            "mean_log_density": float(log_density.mean()),
        }
    )


def sweep_walk_forward(
    frame: pd.DataFrame,
    prior_mean: float,
    observation_variance: float,
    ks: Sequence[float],
    drifts: Sequence[float] = (0.0,),
    min_prior: int = 1,
) -> pd.DataFrame:
    """Score the walk-forward backtest across shrinkage strengths and drift values.

    ``k`` is parametrised through the between-player variance,
    ``observation_variance / k``, so ``k`` (appearances' worth of prior) is the only
    shrinkage knob.

    Args:
        frame: Output of ``appearance_frame``.
        prior_mean: Prior mean to shrink toward.
        observation_variance: Within-player variance held fixed across the sweep.
        ks: Shrinkage strengths to try (finite and positive).
        drifts: Season drift variances to try.
        min_prior: Minimum earlier appearances before predicting.

    Returns:
        One row per ``(drift, k)`` with the columns of ``score_predictions``.
    """
    histories = build_histories(frame)
    rows: list[dict[str, float]] = []
    for drift in drifts:
        for k in ks:
            service = fitted_service(
                prior_mean, observation_variance, observation_variance / k, drift
            )
            scores = score_predictions(walk_forward(histories, service, min_prior))
            rows.append({"drift": drift, "k": k, **scores.to_dict()})
    return pd.DataFrame(rows)
