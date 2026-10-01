# Expected Rating: plan (shelved)

**Status:** Shelved. Build after Tactical Fingerprinting and the other Phase 8 analytics. Last reviewed 1 Oct 2026.

## Goal

Predict a player's match rating for the upcoming match, shown as a range with its components (for example "6.9 (5.9-7.9)": baseline 6.8, opponent +0.1) rather than a single number. Label it "Expected rating", not "prediction". The main consumer is Match Day Prep and its Lineup Optimizer.

## Constraints

- **Existing data only.** No new capture (no fitness, sharpness, morale or in-game form screenshots). Every feature must come from fields already stored.
- **Offline/online split.** Train in `workshop/` with any library. The shipped model is exported to JSON in `config/` and evaluated with numpy only, including tree ensembles if they win. No sklearn, scipy or statsmodels in `src/`.
- **Architecture.** A pure analytics service; `app.py` supplies inputs from DataManager queries; opponent names go through `normalize_team_name`; new types live in `src/contracts/analytics.py`.
- **Ratings first.** Finalise the ratings algorithm and backfill before fitting anything. Every fitted constant must be refitted after any ratings change.

## Relationship to Form Scores

Form Scores is a descriptive indicator and is not an input to this model. Backtests show recent form (EMA at any alpha) predicts future ratings worse than a plain running mean.

## Findings so far

Data at the time: three careers, ~208 matches, ~3,000 rated appearances. All tests are walk-forward on residuals from the shrunk player mean (k=6). Refit after any ratings change.

| Test | Result |
|---|---|
| Variance split | ~80% of rating variance is match-to-match noise (noise ~0.60 of ~0.76 total); stable player identity is roughly 10-15% |
| One-step-ahead error (MSE) | Position average only 0.765; running mean 0.713; EMA alpha 0.3 0.777; **shrunk mean (k=6) 0.702**; Kalman local-level best q = 0 (identical to shrunk mean); shrunk + recency nudge 0.699 (under 0.5% better) |
| Rest days, minutes in last 3 matches, home/away, league vs cup | \|r\| <= 0.01 against the residual |
| Return from injury | +0.01 (SE 0.07) within 21 days of return; -0.09 (SE 0.07) for injuries of 14+ days within 28 days: noise |
| Match-adjusted rating (minus the match's team average) | 14% of variance is shared match context, but predictability is unchanged (8.3% raw vs 8.0% adjusted) |
| **Opponent effect** | Team-level r = +0.15 (1,803 appearances; effective sample is the match count). Player-specific record vs the opponent collapses once this is included (coefficient 0.08 vs 0.35). Median 2 prior meetings; 75 distinct opponents |

Ceiling: the shrunk mean is about 8% better than assuming everyone is average. Expect modest gains from anything added.

## Candidate features (existing data)

0. **Baseline:** shrunk player mean, `(n x mean + k x position mean) / (n + k)`, k ~6. Possible upgrade: replace the position prior with an attribute/overall + age prior (untested).
1. **Opponent effect:** mean residual of all squad players against this opponent in earlier meetings, shrunk by `m / (m + k_opp)`. Tested: small but real.
2. **Opponent archetype x position group:** needs Tactical Fingerprinting. Untested.
3. **Other untested candidates:** rolling sprint-distance workload, consecutive starts, season stage, team form and streak, head-to-head results, position played vs natural position (if derivable from stored data).
4. **Tested null (do not re-test unless data volume changes substantially):** recent form, rest days, recent minutes, home/away, competition, return from injury.

## Model plan

1. **Hierarchical (mixed-effects) linear model first.** Random intercepts for player and opponent, fixed effects for covariates. Fit in `workshop/` (statsmodels, or bambi/PyMC for full uncertainty). Export coefficients and variance components to `config/rating_prediction.json`. New players and opponents shrink to the prior automatically.
2. **Gradient-boosted trees as the challenger** (LightGBM or sklearn `HistGradientBoosting`), with monotonic constraints where the direction is known. Export trees as JSON arrays and evaluate in numpy.
3. **Validation.** Walk-forward, time-ordered. Metrics: MSE against layer 0, and interval calibration (do 80% ranges cover 80%?). Each layer or feature must beat the previous one out-of-sample to ship. Expect the linear model to win at today's data size; revisit trees as careers accumulate.
4. **Output.** Expected rating, low and high (prediction sd ~0.78, so an 80% range is roughly +/-1.0), and a components dict so the UI can show why.

## Architecture shape

- **DataManager:** a player rating-history query (shared with Form Scores) and a squad-wide `get_rated_appearances_vs_opponent`.
- **Engine:** `predict_rating(history, opponent_context)`; `app.py` exposes it for Match Day Prep.
- **New files:** `rating_prediction_service.py`, `config/rating_prediction.json`, contracts `PredictionInput` and `RatingPrediction(expected, low, high, components)`, a workshop backtest notebook, tests.
- **Availability** (injured, suspended, sold, loaned) gates who is selectable. It is not a rating input.

## Pitfalls

- Opponents are thin, so shrink every layer.
- Never feed form into the model.
- The backtest notebook is the gatekeeper; keep its report with the config it produced.
- Fitted constants go stale whenever ratings change.

## Revisit when

Tactical Fingerprinting exists, and more careers and matches are available (especially Ipswich, for lower-win-rate coverage).
