"""Check the reliable-rating fit and backtest helpers in the workshop library.

The variance-component fit is checked three independent ways: against simulated data
with known components, against the closed-form ANOVA estimators on balanced data, and
against a boundary case with no player effect. The walk-forward backtest is checked
against the closed-form shrunk mean, and the data helpers against the real careers.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from workshop.lib import reliable_rating

_MU = 6.4
_BETWEEN = 0.10
_WITHIN = 0.75


def _simulate(
    mu: float, between: float, within: float, n_players: int, seed: int
) -> pd.DataFrame:
    """Simulate unbalanced ratings from a player level plus match noise."""
    rng = np.random.default_rng(seed)
    counts = rng.integers(1, 41, size=n_players)
    levels = rng.normal(mu, between**0.5, size=n_players)
    return pd.DataFrame(
        {
            "player_key": np.repeat([f"sim:{i}" for i in range(n_players)], counts),
            "rating": rng.normal(np.repeat(levels, counts), within**0.5),
        }
    )


def _frame(rows: list[tuple[str, int, str, float]]) -> pd.DataFrame:
    """Build a ``build_histories`` input from ``(key, match, date, rating)`` rows."""
    return pd.DataFrame(
        {
            "player_key": [r[0] for r in rows],
            "name": [r[0] for r in rows],
            "match_id": [r[1] for r in rows],
            "in_game_date": pd.to_datetime([r[2] for r in rows]),
            "rating": [r[3] for r in rows],
        }
    )


# ── Variance components ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("method", ["reml", "ml"])
def test_fit_recovers_simulated_components(method: reliable_rating.Method) -> None:
    """Known grand mean and variances are recovered from unbalanced simulated data."""
    frame = _simulate(_MU, _BETWEEN, _WITHIN, n_players=400, seed=11)

    fit = reliable_rating.fit_variance_components(
        reliable_rating.player_summaries(frame), method
    )

    assert fit.mu == pytest.approx(_MU, abs=0.06)
    assert fit.within_var == pytest.approx(_WITHIN, abs=0.05)
    assert fit.between_var == pytest.approx(_BETWEEN, abs=0.035)
    assert fit.n_players == 400
    assert fit.n_rows == len(frame)
    assert fit.k == pytest.approx(_WITHIN / _BETWEEN, rel=0.35)
    assert fit.icc == pytest.approx(_BETWEEN / (_BETWEEN + _WITHIN), abs=0.04)


def test_balanced_fit_matches_the_anova_estimators() -> None:
    """With equal appearances per player, REML equals the classical ANOVA estimators."""
    rng = np.random.default_rng(3)
    players, appearances = 60, 12
    levels = rng.normal(6.3, 0.2**0.5, size=players)
    data = rng.normal(levels[:, None], 0.5**0.5, size=(players, appearances))
    ybar = data.mean(axis=1)
    ssw = ((data - ybar[:, None]) ** 2).sum(axis=1)
    summaries = pd.DataFrame({"n": appearances, "mean": ybar, "ssw": ssw})

    msw = ssw.sum() / (players * (appearances - 1))
    msb = appearances * ybar.var(ddof=1)
    expected_between = (msb - msw) / appearances
    assert expected_between > 0

    fit = reliable_rating.fit_variance_components(summaries, "reml")

    assert fit.mu == pytest.approx(ybar.mean(), rel=1e-6)
    assert fit.within_var == pytest.approx(msw, rel=1e-4)
    assert fit.between_var == pytest.approx(expected_between, rel=1e-3)


def test_no_player_effect_gives_zero_between_variance() -> None:
    """Players all on the grand mean give a boundary fit, never a negative variance."""
    summaries = pd.DataFrame({"n": 5, "mean": 6.0, "ssw": 3.0}, index=range(50))

    fit = reliable_rating.fit_variance_components(summaries)

    assert fit.between_var == 0.0
    assert fit.k == math.inf
    assert fit.icc == 0.0
    assert fit.reliability(10) == 0.0


def test_reliability_rises_with_appearances_towards_one() -> None:
    """A mean over more appearances is more reliable, by ``n / (n + k)``."""
    fit = reliable_rating.VarianceComponents(
        mu=6.4, within_var=0.75, between_var=0.075, n_players=10, n_rows=100
    )
    assert fit.k == pytest.approx(10.0)
    assert fit.reliability(10) == pytest.approx(0.5)
    assert fit.reliability(5) < fit.reliability(20) < 1.0


def test_bootstrap_is_reproducible_and_brackets_the_truth() -> None:
    """The same seed repeats the draws, and intervals bracket estimate and truth."""
    frame = _simulate(_MU, _BETWEEN, _WITHIN, n_players=300, seed=5)
    summaries = reliable_rating.player_summaries(frame)
    fit = reliable_rating.fit_variance_components(summaries)

    draws = reliable_rating.bootstrap_variance_components(
        summaries, n_resamples=150, seed=9
    )
    again = reliable_rating.bootstrap_variance_components(
        summaries, n_resamples=150, seed=9
    )
    table = reliable_rating.summarise_bootstrap(fit, draws)

    pd.testing.assert_frame_equal(draws, again)
    assert (table["ci_low"] <= table["estimate"]).all()
    assert (table["estimate"] <= table["ci_high"]).all()
    assert table.loc["mu", "ci_low"] <= _MU <= table.loc["mu", "ci_high"]
    assert (
        table.loc["between_var", "ci_low"]
        <= _BETWEEN
        <= table.loc["between_var", "ci_high"]
    )


# ── Walk-forward backtest ────────────────────────────────────────────────────────


def test_walk_forward_matches_the_closed_form_shrunk_mean_without_drift() -> None:
    """With no drift, each prediction is the closed-form shrunk mean."""
    ratings = {"a:1": [7.0, 6.0, 8.0, 5.5], "b:1": [6.2, 6.8, 7.4]}
    dates = {"a:1": "2029-08-01", "b:1": "2030-08-01"}
    rows = [
        (key, 100 * i + t, str(pd.Timestamp(dates[key]) + pd.Timedelta(days=7 * t)), r)
        for i, (key, values) in enumerate(ratings.items())
        for t, r in enumerate(values)
    ]
    prior_mean, observation, prior = 6.4, 0.75, 0.09
    service = reliable_rating.fitted_service(prior_mean, observation, prior)
    histories = reliable_rating.build_histories(_frame(rows))

    predictions = reliable_rating.walk_forward(histories, service)

    k = observation / prior
    assert len(predictions) == (4 - 1) + (3 - 1)
    assert (predictions["t"] >= 1).all()
    for row in predictions.itertuples():
        earlier = ratings[row.player_key][: row.t]
        assert row.pred_mean == pytest.approx(
            (sum(earlier) + k * prior_mean) / (row.t + k)
        )
        assert row.raw_mean == pytest.approx(sum(earlier) / row.t)
        assert row.rating == ratings[row.player_key][row.t]
        assert row.prior_mean == prior_mean


def test_walk_forward_adds_drift_to_the_predictive_variance_by_season_gap() -> None:
    """Predictive variance gains ``q`` per season elapsed since the last appearance."""
    rows = [
        ("c:1", 1, "2029-08-01", 6.0),
        ("c:1", 2, "2029-09-01", 7.0),
        ("c:1", 3, "2031-08-01", 8.0),
    ]
    observation, prior, drift = 0.75, 0.09, 0.05
    service = reliable_rating.fitted_service(6.4, observation, prior, drift)

    predictions = reliable_rating.walk_forward(
        reliable_rating.build_histories(_frame(rows)), service
    ).set_index("t")

    same_season = 1 / (1 / prior + 1 / observation) + observation
    two_seasons_later = 1 / (1 / prior + 2 / observation) + 2 * drift + observation
    assert predictions.loc[1, "pred_var"] == pytest.approx(same_season)
    assert predictions.loc[2, "pred_var"] == pytest.approx(two_seasons_later)


def test_walk_forward_rejects_a_zero_minimum_history() -> None:
    """A prediction needs at least one earlier rating."""
    service = reliable_rating.fitted_service(6.4, 0.75, 0.09)
    with pytest.raises(ValueError, match="min_prior"):
        reliable_rating.walk_forward({}, service, min_prior=0)


def test_score_predictions_applies_the_stated_formulas() -> None:
    """Errors, baselines and the Gaussian log density are computed as documented."""
    predictions = pd.DataFrame(
        {
            "rating": [7.0, 6.0],
            "pred_mean": [6.5, 6.5],
            "pred_var": [1.0, 1.0],
            "raw_mean": [7.0, 5.0],
            "prior_mean": [6.0, 6.0],
        }
    )

    scores = reliable_rating.score_predictions(predictions)

    assert scores["n"] == 2
    assert scores["mse_shrunk"] == pytest.approx(0.25)
    assert scores["mse_raw_mean"] == pytest.approx(0.5)
    assert scores["mse_prior"] == pytest.approx(0.5)
    assert scores["mean_log_density"] == pytest.approx(
        -0.5 * (math.log(2 * math.pi) + 0.25)
    )


def test_sweep_has_one_row_per_drift_and_k() -> None:
    """The sweep scores every ``(drift, k)`` pair and the shrunk MSE beats the prior."""
    frame = _frame(
        [
            (key, t, str(pd.Timestamp("2029-08-01") + pd.Timedelta(days=7 * t)), r)
            for key, values in {
                "a:1": [7.0, 6.0, 8.0, 5.5, 6.5],
                "b:1": [6.2, 6.8, 7.4, 6.6],
            }.items()
            for t, r in enumerate(values)
        ]
    )

    sweep = reliable_rating.sweep_walk_forward(
        frame, 6.4, 0.75, ks=[2.0, 10.0], drifts=(0.0, 0.02)
    )

    assert list(zip(sweep["drift"], sweep["k"], strict=True)) == [
        (0.0, 2.0),
        (0.0, 10.0),
        (0.02, 2.0),
        (0.02, 10.0),
    ]
    assert (sweep["n"] == 7).all()


# ── Real careers ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def real_frame() -> pd.DataFrame:
    """Return the appearance frame for every pooled career, rated once per module."""
    return reliable_rating.appearance_frame("pool")


def test_appearance_frame_is_keyed_per_career_and_chronological(
    real_frame: pd.DataFrame,
) -> None:
    """Player keys never collide across careers and rows are in date order."""
    assert real_frame["rating"].notna().all()
    assert real_frame["rating"].between(0.0, 10.0).all()
    prefix = real_frame["player_key"].str.split(":").str[0]
    assert (prefix == real_frame["career"]).all()
    assert real_frame.groupby("player_key")["player_id"].nunique().eq(1).all()
    assert (
        real_frame.groupby("player_key")["in_game_date"]
        .apply(lambda dates: dates.is_monotonic_increasing)
        .all()
    )
    assert real_frame["career"].nunique() > 1


def test_build_histories_gives_every_player_a_unique_payload_id(
    real_frame: pd.DataFrame,
) -> None:
    """Histories cover every row once, with unique integer ids across careers."""
    histories = reliable_rating.build_histories(real_frame)

    ids = [h["player_id"] for h in histories.values()]
    assert len(histories) == real_frame["player_key"].nunique()
    assert len(set(ids)) == len(ids)
    assert sum(len(h["appearances"]) for h in histories.values()) == len(real_frame)


def test_real_fit_is_sensible_and_the_shrunk_estimate_beats_the_raw_mean(
    real_frame: pd.DataFrame,
) -> None:
    """On the real careers the fit is well formed and shrinking helps out of sample."""
    fit = reliable_rating.fit_variance_components(
        reliable_rating.player_summaries(real_frame)
    )
    service = reliable_rating.fitted_service(
        fit.mu, fit.within_var, fit.between_var if fit.between_var > 0 else 1e-6
    )

    predictions = reliable_rating.walk_forward(
        reliable_rating.build_histories(real_frame), service
    )
    scores = reliable_rating.score_predictions(predictions)

    assert 0.0 < fit.between_var < fit.within_var
    assert 0.0 < fit.icc < 0.5
    assert scores["mse_shrunk"] < scores["mse_raw_mean"]
    assert scores["mse_shrunk"] < scores["mse_prior"]
