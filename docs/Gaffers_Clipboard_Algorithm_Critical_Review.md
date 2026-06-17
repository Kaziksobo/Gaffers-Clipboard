# Gaffer's Clipboard Rating Algorithm — Critical Review

**A companion reference to the Quantitative Design whitepaper**

---

## Preamble: scope, ground truth, and evidence base

This document is a section-by-section critical review of the Gaffer's Clipboard match-rating algorithm. It is deliberately exhaustive: sections that hold up are explained as much as sections that don't, because "why it holds up" is as useful for the whitepaper as "why it breaks".

Three ground rules govern the analysis:

1. **The live code is the source of truth.** Where `match_ratings_service.py` and the whitepaper disagree, the code wins, and the disagreement is flagged.
2. **Claims are grounded in artefacts.** Every numeric assertion is checked against `performance_weights.json`, `performance_means_stds.json`, the two calibration notebooks, or the stress-test / real-match outputs in `ratings_testing.ipynb`. Where I reproduce a number, I say so.
3. **Severity is labelled.** Findings are tagged **[BUG]** (objectively wrong / does not do what it claims), **[SKEW]** (train/inference inconsistency), **[DESIGN]** (a defensible choice with a real downside), or **[SOUND]** (holds up — with the reasoning).

**A note on what is *not* a ground truth here.** The `match_rating` field in `example_matches.json` and the `[Expected: …]` values in the testing notebook are **outputs of a previous version of this same algorithm**, not an independent reference. They are therefore disregarded entirely in this review: no agreement statistic is computed against them, and they are not treated as a validation target anywhere. This is an important constraint, because it means **the model currently has no external reference of any kind** in the provided files. The only evidence available is therefore (i) the algorithm's own outputs and their internal behaviour, and (ii) the *designed* stress tests in `ratings_testing.ipynb`, which encode an *intended qualitative* result (a masterclass striker should rate ~9.8; a nightmare centre-back should rate low; the sigmoid should not jump across a volume threshold). Those designed checks are self-contained and remain valid; the prior-version numbers are not used. Much of Part 1 concerns where the model manufactures its central compression (low-minute games and dominant-team performances both pulled toward ~6.0); that compression is established from the algorithm's *own* output behaviour, not from any comparison.

---

# PART 1 — SECTION-BY-SECTION CRITICAL REVIEW

## 1.1 Temporal standardisation and baseline half-length scaling — **[SOUND]**

**What it does.** Every cumulative volume metric is rescaled to a notional 10-minute half via `time_scalar = H_BASE / half_length` (`H_BASE = 10.0`), applied before any per-90 conversion. A 4-minute-half game multiplies counting stats by 2.5; a 10-minute-half game is the identity.

**Why it holds up.** This is the correct first step and it is dimensionally honest. Career Mode lets the user pick half length, so raw counting stats are on an arbitrary per-match time base; without rescaling, a 4-minute-half game and a 10-minute-half game would feed incomparable volumes into the same positional means. Crucially, the *same* `H_BASE = 10.0` convention is applied identically in the calibration notebooks (ST notebook, CODE 6: `pos_df[col] = pos_df[col] * (h_base / pos_df["half_length"])`) and at inference (`calculate_outfield_rating`, the `vol_columns` loop). Train and inference agree here, which is exactly what you want and is *not* true everywhere else (see 1.6).

**The one subtlety worth a whitepaper sentence.** The scalar is applied to volumes but the smoothing prior `d` (15/30/45) is expressed in *minutes*, and `minutes_played` is the *real* minutes, not rescaled. So for a 4-minute-half game the player's volumes are inflated 2.5× but their minutes are not. This is internally consistent — the per-90 formula `(X_scaled / (minutes + d)) * 90` treats `X_scaled` as "volume the player would have produced in a 10-min-half world" and divides by real minutes — but it does quietly assume that a player's *rate* is invariant to half length, i.e. that someone playing 8 real minutes of 4-minute halves behaves like someone playing 8 real minutes of 10-minute halves. That's a reasonable assumption and almost certainly fine; it is just an assumption, and it should be stated rather than left implicit. No fix required.

## 1.2 Bayesian smoothing: three-tier `d`, bifurcated prior, and the `expm1` back-conversion

**What it does.** `_apply_bayesian_smoothing` blends the observed per-match rate toward a prior using pseudo-count `d`:

```
r_smoothed = [M/(M+d)]·r_obs + [d/(M+d)]·r_prior
```

implemented in the algebraically-reduced volume form `X_p90 = ((X + r_prior·(d/90)) / (M + d))·90`. Three tiers: `d = 15` (high-frequency: passes, distances, possession won/lost), `d = 30` (medium: dribbles, tackles, fouls, offsides), `d = 45` (rare: goals, assists, shots). Rare events shrink toward a prior of **0.0**; volume events shrink toward the **positional historical mean**.

### 1.2.1 The three-tier `d` values — **[SOUND, with one calibration caveat]**

The *ordering* is correct and well-motivated. Pseudo-count `d` is, in conjugate-prior terms, the number of "prior minutes" of evidence you're injecting. Metrics that stabilise quickly (a player's passing rate is informative after very few minutes) should get a small `d`; metrics that are noisy and rare (goals) should get a large `d` so a single fluke goal in 15 minutes doesn't dominate. `15 < 30 < 45` encodes exactly that. The effect is visible and correct in the stress tests: the Golden Sub (15 min, 1 goal) returns **7.3**, not a 9-something — the `d = 45` on goals plus the 15-minute sample means the single goal is heavily regressed. That is the intended behaviour and it works.

The caveat is that `d = 45` is enormous relative to the data scale. With `M = 15` and `d = 45`, the observed signal is weighted `15/60 = 25%` and the prior (0) gets 75%. For a 90-minute game it's `90/135 = 67%` observed. This is a *strong* shrinkage prior on the single most important attacking events. Combined with the additive raw-goal bonuses in the positional modifiers (1.9.4), this is partly self-correcting — the literal goal count is added back outside the z-score — but it means the **z-score channel** for goals is almost inert at low minutes and only moderately active at full time. Whether `45` is right is an empirical question that wants a sensitivity sweep (Part 3.6), not an a priori answer. The value is defensible; it is not validated.

### 1.2.2 The bifurcated prior (0.0 for rare, μ_historical for volume) — **[SOUND]**

This is the cleverest part of the smoothing design and it is correct. The two metric classes have genuinely different "null hypotheses":

- For **volume** metrics (passes, distance, tackles), a player who has been on the pitch and produced *no* passes is anomalous; the maximum-entropy prior belief about an unseen player is "they perform like a positional-average player", so shrinking toward `μ_historical` is right. A 5-minute cameo with 2 passes shouldn't read as "near-zero passer"; it should read as "average until proven otherwise".
- For **rare** events (goals, assists, shots), the maximum-entropy prior is "they did *not* score", because the base rate is near zero. Shrinking a goal tally toward `μ_historical ≈ 0.2/90` would *inflate* a goalless striker toward a phantom goal. Shrinking toward **0** is correct: absence of a goal is the expected state, and the player must earn positive goal-z by actually scoring.

This bifurcation is mathematically principled (it's an empirical-Bayes choice of prior mean matched to each metric's base rate) and I'd defend it in the whitepaper exactly as above. It is currently under-explained in the documentation relative to how good it is.

### 1.2.3 The `expm1` back-conversion for the four log-transformed volume metrics — **[SOUND, and a genuinely subtle correctness fix]**

This is the part most likely to look like a bug to a reviewer and is in fact *correct*, so it deserves a careful note. Four volume metrics — `possession_won`, `possession_lost`, `fouls_committed`, `offsides` — were log-transformed *before* their means were computed in the calibration notebooks (`cols_to_log`). So the stored `mean` for these is `mean(log(x+1))`, not a raw p90 rate. The smoothing formula needs `r_prior` in **raw** units (it's blended with a raw observed count `X`). The code correctly back-converts:

```python
if col in {"possession_won","possession_lost","fouls_committed","offsides"}:
    league_average_p90 = float(np.expm1(league_average_p90))
```

`expm1` is `exp(x) − 1`, the exact inverse of `log1p`. Without this line the prior would be on the wrong scale (a log-mean of ~0.66 for CB possession-won would be injected as a raw prior of 0.66 instead of `expm1(0.66) ≈ 0.93`), systematically *under-priming* these metrics. The fix is correct and the inverse is the right one.

**The one thing to verify in the whitepaper:** this is silently coupled to the calibration notebooks' `cols_to_log` list. If anyone ever changes which columns are log-transformed in calibration without updating this set literal in the service, the priors will silently desynchronise. This is a latent fragility — a string-keyed coupling across two files with no shared constant. **Recommendation:** export `cols_to_log` (and the negative-stats / log-transformed lists in `_calculate_z_scores`) as a single shared module-level constant imported by both the notebooks and the service, so the coupling is enforced rather than hoped for. This same class of "two lists that must agree but are maintained separately" problem recurs in 1.6 and 1.8 and is, structurally, the single biggest maintainability risk in the pipeline.

## 1.3 The synthetic xT proxy

**Formula (live code, `_calculate_xt_bonus`):**

```
xT = S_pos · C_ctrl · (D_sprint / D_total) · ln(A_pass · V_pass + 1)
```

with `S_pos ∈ {0.35, 0.25, 0.10}` by positional progression responsibility, `C_ctrl = min((won+1)/(lost+1), 2.5)` (Laplace-smoothed possession-control ratio), and `A_pass` = pass accuracy (as a 0–100 number), `V_pass` = smoothed passes p90.

This is the single most conceptually load-bearing invention in the model — it is the *only* term standing in for the entire family of progression/threat metrics that the data can't provide — so it gets the most scrutiny.

### 1.3.1 Does it capture progressive threat, or reward defensive ball-winners? — **[DESIGN, with a real false-positive channel]**

The user's framing question is exactly the right one. Verdict: the proxy is a *defensible* construction of "involvement-weighted forward intensity", but it does **not** measure threat in the xT sense (probability-weighted ball progression into dangerous zones), and two of its four factors are vulnerable to rewarding the wrong player.

Walk the factors:

- **`D_sprint / D_total` (sprint share).** This is the heart of the proxy and its biggest liability. Sprint *share* is positionally and tactically confounded: a recovering full-back chasing back, a CB sprinting to cover, and a winger making an overlapping run all show high sprint share. Sprinting is correlated with *intensity of movement*, not *direction* or *value* of movement. The "Recovery CB" stress test exists precisely because the author knew this: `test_3_recovery_cb` has "Huge sprint distance" / "Absurdly high sprint distance" (6.5 km sprinted in the 10m variant) and the rating lands at **5.1–5.4**, i.e. the proxy did *not* runaway-reward it. But it didn't because of the **control-ratio damper** (next bullet) and the CB's near-zero `xt_bonus_p90` weight (0.030), not because the sprint-share term itself discriminates threat. On a position where xT *is* weighted heavily (RWB xt weight 0.118, RM 0.113, CAM 0.110), the same false-positive sprint has real leverage.

- **`C_ctrl = min((won+1)/(lost+1), 2.5)` (control ratio).** This is the explicit "defensive noise filter", and it is the cleverest defensive move in the formula: a player who wins more than they lose gets scaled up to 2.5×, a player who loses more than they win gets scaled *down* toward (won+1)/(lost+1) < 1. So a ball-winning *recovery* sprinter (high possession_won) is *not* penalised, but a player who sprints a lot while haemorrhaging possession is damped. The Laplace +1 on both sides is correct (prevents 0/0 and divide-by-zero, and shrinks small-sample ratios toward 1). The 2.5 cap is sensible (stops a 6-won/0-lost cameo from exploding). **However** — this is the subtle inversion the user asked about — by rewarding `possession_won`, the proxy *does* hand xT credit to pure defensive ball-winners who happen to also sprint. A destroyer CDM who wins 8 balls, loses 2, and sprints back repeatedly gets `C_ctrl` near its 2.5 cap and a healthy sprint share, producing a non-trivial xT bonus that has nothing to do with *threat generation*. For CDM/CB this is neutralised by tiny xT weights (CDM 0.004, CB 0.030). For a ball-winning full-back or wide-mid it leaks through. So the honest statement is: **the control ratio successfully prevents the proxy from rewarding *wasteful* sprinters, but it does so by rewarding *ball-winning* sprinters, which is a different bias, not the absence of bias.**

- **`ln(A_pass · V_pass + 1)` (logarithmic passing restraint).** Multiplying accuracy (0–100) by volume and log-compressing is the right shape: it makes the term monotone increasing in both passing volume and accuracy with strongly diminishing returns, so a metronome on 60 passes doesn't dwarf everyone. But note `A_pass` enters as a raw 0–100 number, so the product is on the order of `85 × 20 = 1700`, and `ln(1701) ≈ 7.44`. The dynamic range of this factor across realistic games is roughly `ln(100·5)=6.2` to `ln(100·60)=8.7` — a span of only ~2.5 in a term that's then multiplied by the other three. So in practice this factor is **nearly constant** for anyone who passes at all; it mostly acts as a soft on/off gate ("did this player touch the ball enough to be progressing it"). That's not wrong, but the whitepaper currently implies passing *quality* meaningfully modulates xT, and the log compression has largely flattened that. If you want passing to matter more inside xT, drop the +1-inside-log scale or use `ln(A_pass)·ln(V_pass+1)` so accuracy and volume contribute on comparable log scales.

### 1.3.2 The positional scalar is three-tier, not fixed (correcting the whitepaper) — **[SKEW between doc and code, code is better]**

The whitepaper (per the audit) describes a fixed scalar; the code uses `{ST/RW/LW/CAM/CF: 0.35, CM/RM/LM/RWB/LWB/RB/LB: 0.25, CDM/CB: 0.10}` with a `0.25` default. The three-tier version is the *correct* design and the doc should be updated to match. The reason it's correct: the scalar multiplies a quantity that is then **z-scored against a positional mean** — so a constant scalar shift would be absorbed by the z-score anyway. What actually matters is that the scalar changes the *shape* of the xT distribution per position (it interacts multiplicatively with the other three factors, which have different positional variances), and the per-tier values let the spread of xT differ by role. This is a real, non-cosmetic difference and the code's version is the defensible one.

### 1.3.3 The deeper structural problem: xT is computed on one scale, standardised on wildly different scales — **[SKEW / latent inconsistency]**

This is the most important xT finding and it is easy to miss. The *same* formula produces `xt_bonus_p90` at inference for every position, but the stored standardisation baselines for it vary by an order of magnitude:

| Position | xt_bonus_p90 mean | xt_bonus_p90 std |
|---|---|---|
| ST | 0.189 | 0.141 |
| CB | 0.467 | 0.145 |
| RB / LB | 1.463 | 0.544 |
| RWB / LWB | **2.195** | 0.666 |
| CAM | 0.702 | 0.444 |

The wingback mean (2.195) is **11.6× the striker mean** (0.189). These baselines come from two different worlds: the ST/CB/CM/etc. means are computed empirically from Valencia data in the position notebooks, whereas the **RWB/LWB means are *inherited* from RB via a ×1.5 multiplier** (1.8, below), and there is *no wingback in the dataset to check them against*. So a real wingback's live xT (produced by the universal formula) is being z-scored against a fabricated mean of 2.195 that no observed player generated. If the formula systematically produces xT around, say, 0.8 for a wide attacking role, that player will score `(0.8 − 2.195)/0.666 ≈ −2.1` on the xT axis — a large, undeserved negative — purely because the inherited baseline is an unvalidated extrapolation. **This is the single most likely source of mis-rating for the derived wide positions and should be the first thing you empirically check** once you have any real WB data.

## 1.4 Volume masking (continuous logistic confidence) — **[SOUND in form, [DESIGN] on thresholds]**

**What it does.** Efficiency *percentages* (pass accuracy, shot accuracy, dribble success, tackle success) are unreliable at low volume — 100% pass accuracy on 1 pass is noise. The code multiplies each such z-score by a logistic confidence weight `W_mask = 1/(1 + e^(−λ(X − T)))` keyed to the *volume* of the underlying action, with `(T, λ)`: pass accuracy `(3, 1.1)`, dribble success `(2, 1.5)`, shot accuracy `(1.5, 2.0)`, tackle success `(1.5, 2.0)`.

### 1.4.1 Continuous logistic, not a hard cutoff — **[SOUND, and a real correctness improvement over the whitepaper]**

The audit correctly flags that the doc describes hard binary cutoffs while the code uses a continuous sigmoid. The continuous version is unambiguously better and the reasoning is worth stating: a hard cutoff at "3 passes" creates a discontinuity where a 2-pass and 3-pass game get wildly different treatment, which is both unfair and a source of rating instability near the boundary. The logistic ramp removes the discontinuity. The sigmoid-gradient stress test (6A/6B/6C: 1, 3, 6 passes) returns **5.8 / 5.8 / 5.9** — deliberately demonstrating that crossing the threshold produces no jump, which is exactly the property you want and a good test to keep.

### 1.4.2 The thresholds are low — but that's correct for this data scale, *given* one caveat — **[DESIGN]**

The user flags the thresholds (3, 2, 1.5, 1.5) as "very low", and in absolute football terms they are — 3 passes is nothing. But the masking is keyed to `x_vol = normalized_metrics.get(vol_col)`, i.e. the **half-length-normalised** count, which is on the 10-minute-half scale, *not* the per-90 or raw-match scale. On a 10-minute-half (20-minute-match) base, "3 passes" is a different beast than 3 passes in 90 minutes. So the thresholds are calibrated to the compressed Career-Mode volume scale, and in that frame they're more reasonable than they look. At `T = 3, λ = 1.1` for pass accuracy, `W_mask` is 0.5 at exactly 3 passes, ~0.23 at 1 pass, ~0.76 at 5 passes — a gentle ramp that never fully zeroes and never fully trusts. That's a sane confidence curve.

**The caveat (and it's a real one):** because the mask never reaches 0, a player with literally **1 pass at 100% accuracy** still passes ~0.23 of a potentially large positive z-score through. With pass-accuracy means around 88 and std ~12–20, a 100% game is `(100−88)/12 ≈ +1.0σ`, and 0.23 of that is +0.23σ on a metric that for some positions carries real weight (CDM pass_accuracy weight 0.186). So a 1-pass cameo can still bank a small efficiency bonus it didn't earn. **Recommendation:** either raise λ slightly (so the low tail decays faster) or floor the mask contribution to 0 below ~1 action. This is minor in rating terms but it's one of the mechanisms behind the low-minute upward compression visible in the model's own outputs (1.10).

## 1.5 Log-normal transforms and Z-score standardisation (incl. the inverted negative formula) — **[SOUND]**

**What it does.** In `_calculate_z_scores`: right-skewed metrics (`goals_p90, assists_p90, non_goal_shots_p90, offsides_p90, fouls_committed_p90, possession_won_p90, possession_lost_p90`) get `np.log1p` applied before standardisation, to match the log-space baselines; standardisation is `(value − mean)/std`, except for `negative_stats` (fouls, possession lost, offsides) where it's **inverted** to `(mean − value)/std` so that "more is worse" produces negative z; and `std == 0` short-circuits to `raw_z = 0`.

**Why it holds up.**

- The **log1p before z** is the textbook fix for the normality violation the research doc itself identifies (rare events ~Poisson, distances ~Gamma; a Gaussian z-score on a right-skewed count over-rewards the long tail). `log1p` is the right choice over `log` because it's defined at 0. And critically, the **same** transform is applied in calibration (notebook `cols_to_log` + `np.log(x+1)`) and inference (`np.log1p`) — `log1p(x)` ≡ `log(x+1)`, so train and inference agree. Good.
- The **sign inversion** for negative stats is correct and necessary: it lets the downstream dot-product use uniformly "higher z = better" semantics, so a single weight sign convention works for all 17 features. Without it you'd need negative weights for fouls/losses, which would fight the PCA's non-negative magnitude construction (1.6).
- The **`std == 0 → z = 0`** guard matters more than it looks: CB and CDM have `offsides_p90` std = 0 (defenders are never offside in the data), and RB/LB/RWB have *hardcoded* goal stds (0.25, 0.15) to avoid exactly this. Setting z = 0 (rather than dividing by zero or by a tiny std) is the safe, neutral choice — it says "this axis carries no information for this position", which is true. **One observation:** because several of these zero-variance or hardcoded-variance axes also carry near-zero PCA weight, the model is doubly insulated, but it does mean a CB who somehow *is* caught offside registers literally nothing on that axis (z = 0), which is the intended forgiveness.

**The one genuine inconsistency to fix:** `non_goal_shots_p90` is in `log_transformed_stats` and is z-scored *after* `log1p`, but `non_goal_shots_p90` is **derived in the service** as `max(0, shots_p90 − goals_p90)` *after* smoothing, whereas in the ST calibration notebook it's derived as `(shots_p90 − goals_p90).clip(lower=0)` and *then* logged inside `cols_to_log`. These match. But the service computes `non_goal_shots_p90` (line ~679) *before* calling `_calculate_z_scores`, and the smoothed `shots_p90`/`goals_p90` it subtracts have *already* been through the p90 smoothing — consistent with calibration. So this is actually fine; I flag it only because it's the kind of two-place derivation that *looks* like it could desync and is worth a comment in the code asserting the invariant.

## 1.6 Offline weight generation (the PCA pipeline)

This is where the most consequential findings live. The pipeline (ST notebook) is: possession-adjust → half-length standardise → Bayesian smooth → xT synthesise → log-transform a subset → z-score → block-scale by tactical philosophy → MCD robust covariance → eigendecomposition → top-`k=9` truncation → |loading|·√λ aggregation → post-hoc scale correction → normalise.

### 1.6.1 Possession adjustment `√(50/P_team)` — **[SKEW: applied in training, absent at inference. This is the most important single finding in Part 1.]**

In the ST calibration notebook (CODE 4), every player's stats are possession-adjusted *before* means/stds and weights are computed:

```python
# attacking cols
pos_df[col] = pos_df[col] * np.sqrt(50.0 / pos_df["team_possession"])
# defensive cols
pos_df[col] = pos_df[col] * np.sqrt(50.0 / (100.0 - pos_df["team_possession"]))
```

The logic is sound *as a normalisation*: if your team monopolises the ball, your raw attacking volume is context-inflated, so deflate it; defensive actions are rarer for a dominant team, so inflate them. The `√` softens the penalty (the notebook comment calls it the "Softened … Tax"). Fine.

**The problem:** `match_ratings_service.py` does **not** apply this adjustment at inference. `calculate_outfield_rating` normalises by half length and smooths, but there is no `√(50/possession)` anywhere. Yet the means/stds it z-scores against (`performance_means_stds.json`, CODE 13) were computed on possession-*adjusted* data. So:

- Means for attacking volume stats were computed on **deflated** numbers (Valencia plays 59–66% possession in the sample, so `√(50/60) ≈ 0.913` — attacking volumes were shrunk ~9% before the mean was taken).
- At inference, a live player's attacking volume is **not** deflated.
- Result: live attacking z-scores for a high-possession team are biased **high** by roughly the amount of the missing deflation, and defensive z-scores biased **low** (training inflated them ~10%, inference doesn't).

Quantitatively the bias is modest per-stat (≈ +0.1 to +0.3σ on attacking volume for a 60%-possession side, scaling with how far possession sits from 50%) but it is **systematic, position-wide, and directional**, and it compounds across every attacking volume feature in the dot product. For a possession-dominant save like this Valencia file it pushes attacking-heavy roles up and defensive roles down relative to where the calibration intended them to sit.

**This is a genuine train/serve skew, not a rounding issue.** Two clean fixes, pick one:
1. **Apply the possession adjustment at inference** (preferred — it's a few lines: pull `team_possession` from the overview, scale the same attacking/defensive columns by the same `√` factors before smoothing). This makes inference match calibration exactly and *also* adds a genuinely useful context normalisation that the model currently lacks at runtime.
2. **Remove it from calibration** and regenerate all means/stds/weights on unadjusted data. Simpler, but throws away a sensible normalisation.

Fix (1) is the right call. It also partially addresses a Part 2 weakness (the model has weak team-context handling beyond the supremacy scalar).

### 1.6.2 Guided PCA with block scaling `W_block/√k` — **[DESIGN, but the philosophy is applied with roughly squared strength and the PCA does less than it appears]**

The block scaling (ST notebook CODE 10) divides each z-score by `scale_factor = √k / philosophy[block]` before PCA, i.e. multiplies by `philosophy/√k`. So Attacking (`φ=2.5, k=4`) is multiplied by `2.5/2 = 1.25×` (variance inflated to 1.56×); Safety (`φ=0.3, k=1`) by `0.3×`; Defending (`φ=0.4, k=3`) by `0.231×`. Inflating a column's variance rotates the top eigenvectors toward it, so PCA assigns the attacking block large loadings.

Then the **post-hoc correction** (CODE 11) divides the resulting weights by the *same* scale factors and renormalises: `corrected = raw_weights / (√k/φ)`. The comment frames this as a change-of-variables to express the weights in raw-z coordinates, and as a change-of-variables it is internally valid (if the rating is `Σ vᵢ·scaled_zᵢ = Σ (vᵢ/sfᵢ)·raw_zᵢ`, then `vᵢ/sfᵢ` is the correct raw-z weight).

**But here is the issue the user should see clearly.** The philosophy multiplier `φ` enters the final weights **twice**: once by biasing which directions PCA loads onto (inflated columns get bigger loadings), and again in the post-hoc `/sf` step (which multiplies attacking weights up by `φ/√k` once more). I verified the net effect numerically against the notebook outputs:

- **Pre-correction** ST weights: Attacking block (goals+assists+shots+shot_acc) = 0.132+0.136+0.119+0.099 = **0.486** of total.
- **Post-correction** (shipped) ST weights: = 0.181+0.187+0.163+0.136 = **0.665** of total.

The "correction" *increased* attacking dominance from 49% to 67%. If the correction were genuinely neutralising the calibration bias you'd expect it to move the weights *away* from the philosophy, not deeper into it. Instead, because attacking has the smallest scale factor (`sf = 0.8`) and the crushed blocks have the largest (`Safety sf = 3.33`, `Defending sf = 4.33`), dividing every weight by its `sf` and renormalising boosts exactly the blocks the philosophy wanted boosted. So the construction is self-reinforcing.

The honest characterisation for the whitepaper: **these are not "weights discovered by PCA". They are hand-set tactical priors (the `philosophy` dict) lightly textured by the data's covariance structure.** That is a *legitimate* modelling choice for a tiny single-team dataset — pure unguided PCA on ~30–50 striker-games would be noise — but it should be described honestly as "prior-dominated, PCA-regularised" rather than "data-driven". Two concrete consequences:
- The `philosophy` dictionary is the real model. If a reviewer wants to change striker behaviour, they tune `philosophy`, not the data.
- The post-hoc correction's framing ("divide out the scaling") is misleading about what it does. Either (a) drop the correction and use the pre-correction weights (philosophy applied once, cleaner story), or (b) keep it but document it as "a second deliberate amplification of the tactical prior", because that is empirically what it is.

### 1.6.3 MCD at `support_fraction = 0.98` — **[DESIGN: this barely does anything robust]**

`MinCovDet(support_fraction=0.98)` computes the covariance on the 98% least-outlying subset. MCD's whole purpose is robustness via a low support fraction (the classic choice is ~0.5–0.75, giving a high breakdown point). At 0.98 the estimator trims roughly the single most extreme multivariate point and is otherwise ≈ the empirical covariance. On a dataset of ~30–50 rows that's trimming ~1 game. So the "robust PCA" is, for practical purposes, **vanilla PCA with one point shaved**. That's not wrong, but the whitepaper should not lean on "robust covariance estimation" as a strength — it isn't, at this setting. If robustness to fluke games (a 4-goal striker outlier) is actually wanted, drop `support_fraction` to ~0.75 and re-examine the weights; if it isn't wanted, use plain `np.cov` and stop implying robustness. Right now it's the cost of MCD (it's slower, needs a `random_state`) with little of the benefit.

### 1.6.4 `k = 9` truncation and the `|loading|·√λ` aggregation — **[DESIGN]**

Two non-standard choices stacked together:
- **Aggregation:** `raw_weights = Σ_{j≤9} |v_ij|·√λ_j`. Taking the **absolute value** of loadings discards sign — which is acceptable here only because sign is re-applied separately via the `negative_stats` inversion in z-scoring, so the weights are intended as pure magnitudes. The `√λ` weighting (rather than `λ`) is a defensible "standard-deviation explained" weighting. But summing `|v|·√λ` across 9 components is a bespoke "feature importance from PCA" heuristic, not a standard PCA weight derivation.
- **`k = 9` of 17:** the more components you include, the more `Σ_j λ_j v_ij²` approaches the (scaled) feature variance, i.e. the result drifts toward "weight ∝ each feature's engineered variance" — which is set by the block scaling, i.e. by the philosophy. With `k = 9` and the `|·|` (not `²`) you're in a messy middle ground. The practical implication reinforces 1.6.2: **the more components retained, the more the weights are just the philosophy**, because the high-index components mostly re-encode the per-axis variances you imposed. `k = 9` is a lot of components to retain for a "principal" component analysis whose first PC should already carry the dominant signal; retaining 9 dilutes whatever genuine covariance structure PC1–PC2 found.

**Recommendation:** report the eigenvalue scree (how much variance PC1, PC2, … actually explain). If PC1 alone explains, say, 40%+, consider `k = 2–3` and the standard `Σ λ_j v_ij²` (or just |PC1| loadings). If the scree is flat (no dominant direction — likely, given the small n and the imposed scaling), that is itself the finding: there is no robust low-dimensional structure to extract, which is further evidence that the weights are prior-driven and should be presented as such.

### 1.6.5 The dead-code xG-anchoring of striker goals — **[BUG: vestigial code that never executes; the documented "philosophy" was never applied]**

This is a clean, verifiable bug. The ST notebook defines `st_goal_share = 0.4`, `st_assist_share = 0.1`, and a z-score loop (CODE 9) that *intends* to anchor striker goals to a fraction of team xG:

```python
for col in stat_names:        # stat_names contains "goals_p90", "assists_p90", ...
    if col == "goals":        # <-- never true: col is "goals_p90"
        mean = np.log(pos_df["team_xg"] * st_goal_share + 1)
        ...
    elif col == "assists":    # <-- never true: col is "assists_p90"
        ...
    else:
        mean = pca_df[col].mean()   # <-- this branch ALWAYS runs for goals_p90/assists_p90
```

The list `stat_names` holds `"goals_p90"` / `"assists_p90"` (with the `_p90` suffix), but the branches test for `"goals"` / `"assists"` (without it). **The special branches never fire.** Goals and assists are standardised by their own sample mean/std like every other stat, and `st_goal_share`, `st_assist_share`, and the entire team-xG-anchoring idea are **dead code**. The intended design — "a striker's goal expectation should be a share of the team's chance creation, not the squad's historical goal rate" — was never in the shipped model.

This matters beyond tidiness, because the xG-anchoring would have *changed the striker weights*: anchoring goals to `log(team_xg·0.4 + 1)` gives every striker-game a context-dependent mean, which would have reduced goal-z variance for high-xG games and changed how strongly goals load in PCA. Its absence is part of why the next finding (assists ≥ goals) looks the way it does.

**Fix:** decide whether you want xG-anchoring. If yes, fix the keys (`"goals_p90"`, `"assists_p90"`) and re-derive ST (and propagate to CAM via inheritance). If no, delete the dead branches and the two share constants so the notebook stops advertising a mechanism it doesn't use. Either way the whitepaper's description of striker goal handling must be corrected to match reality.

## 1.7 Direct scrutiny of the trained weights

### 1.7.1 ST: `assists_p90 (0.187) > goals_p90 (0.181)` — **[DESIGN artefact, not a finding; and partly caused by a defensible-but-questionable choice]**

The user asks whether this is a meaningful PCA result or a dataset artefact. It is **an artefact**, for three compounding reasons, and it should not be treated as the model "discovering" that assists matter more than goals for a striker:

1. **Sample size.** These weights come from one team's striker-games. The 0.006 gap between assists (0.187) and goals (0.181) is far inside the bootstrap confidence interval you'd get from resampling ~30–50 games (Part 3.7). They are statistically indistinguishable; reading a ranking into a 3% gap is over-interpretation.
2. **Log-compression of goals hurts goals specifically.** Both goals and assists are `log1p`-transformed before PCA. Log compression bites hardest on the *longest right tail*, and for a striker the goal distribution has the longest tail (the occasional 2–3 goal game). So the transform preferentially shrinks the variance of the very events that should make goals the dominant axis. This is a real structural reason goals don't pull away from assists, and it's arguably a mis-application: **for the striker position specifically, log-transforming `goals_p90` is philosophically backwards** — goal-scoring *is* the striker's primary signal and you're compressing its dynamic range before letting PCA see it. Consider exempting `goals_p90` from the log transform for ST (and CAM), or using a gentler transform (√ rather than log), and re-deriving.
3. **The dead xG-anchoring (1.6.5)** would have differentiated goals from assists had it run; without it they're treated symmetrically by the standardiser.

The shipped model partly *compensates* for the weak goal-z via the additive raw-goal bonus (`+goals·1.2` for ST, 1.9.4), so in practice strikers are not under-rewarded for scoring — the masterclass ST stress test hits **9.8–9.9**, and the real-match 2-goal strikers (P48, P66) land at 9.0–9.5. But that means the *weight vector* is not where the striker's scoring signal lives; it lives in the bolt-on bonus. That's fine operationally but the whitepaper should not present the ST weight vector as evidence of what drives striker ratings — the bonus does.

### 1.7.2 CB goals/assists effectively zero (`3e-33`, `3.7e-17`) — **[SOUND; no downstream pathology, and here's the proof]**

The user asks whether zeroed CB attacking weights create downstream pathology. They do not, and the reason is structural:

- The near-zero values are PCA floor noise (a CB's goal axis has almost no variance in the data, so it loads near zero; `3e-33` is effectively a hard zero). This correctly encodes "scoring is not part of the CB's evaluated role".
- **The pathology you'd worry about** — a CB who scores getting no credit — is prevented because CB goal/assist credit is delivered *outside* the weight vector, via the additive bonus in `_apply_cb_modifiers`: `raw_score += goals·0.6 + assists·0.4`. So a scoring CB is rewarded through the bonus channel, not the (zeroed) weight channel. The two channels are complementary by design: the weight vector handles the *continuous* defensive/possession signal; the additive bonuses handle *rare discrete* events. Zeroing the weight is correct *because* the bonus exists.
- The only thing to watch: because the weight is `~0`, the `goals_p90_z` value (which still gets computed and could be large for a scoring CB) contributes nothing to the dot product — that's intended, but it means the CB's clean-sheet/defensive z-scores are the entire weighted signal. Given the CB weight mass sits on `tackles (0.220), possession_won (0.226), tackle_success (0.183), possession_lost (0.139)` — a coherent "win it, keep it, don't lose it" profile — this is exactly right for the position. No fix.

### 1.7.3 The CDM distribution overall — **[SOUND, well-shaped]**

CDM weights: `pass_accuracy 0.186, passes 0.172, possession_lost 0.160, possession_won 0.139, tackles 0.135, tackle_success 0.108, fouls 0.036`. This is a textbook deep-lying-pivot profile: distribution quality (pass accuracy + volume = 0.358 combined) and ball security/recovery dominate, tackling is present but secondary, and `fouls_committed` carries non-trivial weight (0.036, the highest defensive-discipline weight of any position) — consistent with the "tactical fouling is part of the job, but tracked" philosophy. Goals are zeroed (`1.7e-33`), handled via the ×0.5 additive bonus. `xt_bonus` is near-zero (0.004), correctly reflecting that a CDM is not the progression engine. I have no criticism of the *shape*. The one caveat is inherited from 1.6: this shape is substantially the CDM `philosophy` dict, not an emergent finding — but it's a *good* prior, well-matched to the role.

**Cross-position sanity check (verified):** computing the implied "attacking mass" (goals+assists+shots+shot_acc) by position gives ST ≈ 0.665, CAM ≈ 0.299, RW ≈ 0.230, CM ≈ 0.154, CDM ≈ 0.039, CB ≈ 0.020 — a monotone, sensible ordering from pure striker to pure stopper. The weight vectors, whatever their derivation, encode a coherent positional hierarchy. That is the strongest thing that can be said for them and it should be said.

## 1.8 Derived position inheritance (WB, WM, CAM) — the most methodologically exposed component

The three positions with no training data (Wingback, Wide Midfielder, CAM) inherit a proxy's weights/means/stds and apply hand-set multipliers: WB ← RB (×attacking-up, ×defending-down), WM ← Winger (×defence-way-up), CAM ← CM (×attacking-up). This is a reasonable strategy for zero-data positions. The execution contains two concrete bugs and several fragilities.

### 1.8.1 The renormalisation is a no-op — the shipped derived weights do not sum to 1 — **[BUG, verified against the shipped JSON]**

In all three derivations the "re-normalise to sum to 1" step is written as:

```python
for value in wingback_weights.values():
    value /= total_wb_weight
```

Iterating over `.values()` and reassigning the loop variable `value` **does not modify the dictionary** — `value` is rebound to a local float and discarded. The renormalisation never happens. I verified this against the shipped `performance_weights.json`:

- `RWB`/`LWB` weights sum to **1.0563**, not 1.0.
- `RM`/`LM` sum to **1.0920**.
- `CAM` sums to **1.1184**.
- And the values are *exactly* `base × multiplier` with no division: e.g. shipped `CAM.goals_p90 = 0.09142 = CM.goals_p90 (0.04571) × 2.0` to five decimals; `CAM.passes_p90 = 0.15558 = CM.passes_p90 (0.10372) × 1.5`. Confirmed for all checked entries.

**Effect on ratings.** The dot product `Σ wᵢ·zᵢ` scales linearly with the weight vector's magnitude, so an over-unity weight sum inflates the raw score uniformly: CAM raw scores are ~11.8% high, WM ~9.2%, WB ~5.6%, *before* the sigmoid. That is a systematic, position-specific rating inflation for exactly the three positions that are already the least validated. Through the `k=0.85` sigmoid near the centre this is on the order of +0.1 to +0.3 rating points depending on raw score — not catastrophic, but it's pure artefact, it's silent, and it differs by position so it distorts cross-position comparability.

**Fix (one line):** `wingback_weights = {k: v/total_wb_weight for k, v in wingback_weights.items()}` (and the same for WM, CAM), then regenerate. After the fix, re-run any saved ratings — the three derived positions will shift down slightly and the relative ordering within those positions is unchanged (uniform rescale), but cross-position comparisons (e.g. a hybrid CAM/CM player, 1.13) will change.

### 1.8.2 The WB mean/std multiplier dictionary has a key-mismatch silent failure — **[BUG]**

Same class of error as the ST dead code. In the WB means/stds step the multiplier dict (CODE 11) contains `'offsides': 2.0` (no `_p90`), but the loop does `wb_stat_multipliers.get('offsides_p90', 1.0)` → returns the **default 1.0**. So the intended ×2.0 offsides-mean adjustment silently never applies; WB inherits the RB offsides mean unchanged (verified: shipped `RWB.offsides_p90.mean = 0.00776 = RB value`). The WM derivation, by contrast, correctly uses `'offsides_p90'`. So the two notebooks are *inconsistent* about the same key, and one of them silently failed. Offsides barely matters numerically (tiny weight, tiny mean), so the rating impact is negligible — but it's a second instance of string-keyed multiplier dicts failing silently, which is the real lesson: **these dicts need a key-validation assert** (`assert set(mult) <= set(col_names)`), or they'll keep eating typos.

### 1.8.3 Multiplying near-zero proxy weights by large multipliers amplifies noise, not signal — **[DESIGN]**

The WM derivation applies `tackles ×8.0` and `possession_won ×7.0` to the Winger weights. But the Winger tackle weight is `0.0026` and possession-won is `0.0047` — these are *PCA floor noise* (wingers don't tackle, so the loading is at the estimation floor). Scaling noise by 8 produces `0.021`, which is now "real" weight built on an unstable base: if you re-derived the winger weights on a bootstrap resample, that 0.0026 could be 0.0008 or 0.0051, and ×8 turns a 6× sampling wobble into a 6× weight wobble on a defensively-important axis for the WM. The cleaner approach for "WM needs CM-like defensive weight that the Winger proxy lacks" is to **blend toward a position that actually has the signal** — e.g. `WM_weight = 0.5·Winger + 0.5·CM` for the defensive block — rather than amplifying the proxy's noise floor. The current approach can't distinguish "winger tackle weight is 0.0026 because tackling is irrelevant" from "…because it's a noisy estimate of something small but real", and it treats both as a base to multiply.

### 1.8.4 The inheritance can't discover position-specific covariance, which feeds back into Alpha Drag — **[DESIGN, with a circularity worth noting]**

Because WB = RB × (per-axis multipliers), the *shape* of the WB weight vector is the RB shape stretched along single axes; the inter-feature covariance structure (e.g. that for a real wingback, sprint distance and xT co-move much more tightly than for a full-back) is never estimated. Two consequences:
- The derived means/stds use `std_multiplier = √(mean_multiplier)` (a Poisson variance≈mean heuristic) — principled, but it's an *assumption* that variance scales as the square root of the mean shift, applied uniformly, with no data to check it.
- The cosine similarity used by Alpha Drag (1.13) will see WB and RB as nearly identical (I computed `cos(RWB, RB) = 0.906`, `cos(CAM, CM) = 0.882`) **by construction** — they're scalar-stretched versions of the same vector. So when a player lists both WB and RB, Alpha Drag's "tactical similarity" reads high partly because the two vectors were *defined* from each other, not because the model independently learned they're similar roles. The similarity is real-ish (the roles *are* related) but it's partly circular, and the whitepaper should not present these cosine values as independent evidence of role similarity.

**Provenance red flag (verified):** the CAM means/stds in the shipped file match the CAM notebook output exactly, but the CAM *weights* in the notebook's printed cell (`goals 0.0645`) do **not** match the shipped weights (`goals 0.0914`) — yet the shipped weights *do* exactly equal `CM × cam_multipliers` (no renorm). This means the shipped CAM weights were produced by a run that differs from the saved notebook output, i.e. the notebook as committed does not reproduce the artefact it supposedly generated. Whatever the history, **the calibration notebooks are not currently a reproducible record of the shipped weights.** Before trusting any of this in the whitepaper, re-run all calibration notebooks end-to-end and diff the outputs against the shipped JSONs; commit them only when they match.

## 1.9 Positional modifiers pipeline

The post-dot-product modifier layer is large and per-position. I'll evaluate it by mechanism rather than re-listing every position, since the mechanisms repeat.

### 1.9.1 Pre-synthesis Z-score floors — **[SOUND, with one ordering subtlety]**

Each attacking position floors certain z-scores before the dot product (e.g. ST floors `goals_p90_z ≥ −2.0`, `tackles_p90_z ≥ −0.5`, `offsides_p90_z ≥ −1.5`). The philosophy is correct: a striker who gets no service shouldn't be driven to `−4σ` on goals (which the dot product would then weight heavily and the sigmoid would map to near-0), and a striker isn't expected to tackle so shouldn't be punished to the floor for not. Flooring caps the downside of role-irrelevant or service-dependent metrics. This is a sound, well-targeted forgiveness mechanism and the per-position floor sets are individually reasonable (CAM gets the most generous suite, appropriate for the most boom-or-bust role).

**The subtlety:** floors are applied to the z-scores *in place* (`_apply_z_score_floors` mutates the dict), and they run *before* the tactical-isolation multiplier (1.9.2) reads the build-up z-scores. So a CAM whose passing/dribbling z-scores have been floored at `−1.0` will have a *less negative* `z_build` than their raw performance implies, which makes the isolation multiplier *less* likely to fire. The floors and the isolation decay partly fight each other. This is probably benign (both are forgiveness mechanisms) but it's an interaction the whitepaper doesn't acknowledge: **the passenger floors soften the very signal the isolation multiplier uses to detect passengers.**

### 1.9.2 Tactical build-up isolation and the exponential decay `e^(z_build+1.0)` — **[DESIGN, with a sharp activation cliff]**

`_calculate_tactical_isolation_multiplier` averages six build-up z-scores; if `z_build < −1.0` it returns `e^(z_build+1.0)`, else 1.0. So a player who is statistically absent from build-up has their goal/assist *bonuses* (not their whole score) exponentially decayed. The intent — "a striker who did nothing but tap in one goal while ghosting the entire match shouldn't get the full goal bonus" — is good and addresses a real failure mode of additive goal bonuses.

Two issues:
- **Continuity at the threshold is fine, but the gradient is not.** At `z_build = −1.0` the multiplier is `e^0 = 1.0`, matching the else-branch, so there's no jump (good). But just below, the decay is steep: `z_build = −1.5 → e^{−0.5} = 0.61`, `z_build = −2.0 → e^{−1.0} = 0.37`, `z_build = −3.0 → e^{−2.0} = 0.14`. A player can lose 40% of their goal bonus by drifting from `−1.0` to `−1.5` average build-up z. Whether that's too aggressive depends on taste, but it means the multiplier is close to a switch in practice — most players are either ~1.0 or sharply penalised, with little middle. If you want a gentler ramp, use `e^{(z_build+1.0)/2}` (halves the decay rate).
- **It only decays bonuses, not the base.** Because it multiplies only the additive goal/assist terms (and is passed as `isolation_multiplier` into those lines), an isolated player's *dot-product* score is untouched. That's defensible (the dot product already reflects their poor build-up via low z-scores) but it means the mechanism is narrowly targeted at the bonus channel. Fine, but document that scope.

### 1.9.3 Bottleneck synergy bonuses (`min(z_a, z_b)`) across all positions — **[SOUND; this is the best-designed idea in the modifier layer]**

Every position has "mastery" bonuses of the form `if min(z_a, z_b) > τ: raw_score += (min(z_a, z_b) − τ)·c` — e.g. CB "Dominant Stopper" needs `min(tackles_z, possession_won_z) > 1.5`; FB "Express Train" needs `min(sprint_z, xt_z) > 1.0`. Using **`min`** (the bottleneck) rather than a sum or product is the right operator and is genuinely elegant: it means a player only earns the "complete X" bonus if they are *simultaneously* elite at *both* required skills, and cannot buy the bonus by maxing one axis. A CB with monstrous tackles but average recovery gets nothing from the stopper bonus. This correctly encodes archetype *completeness* and resists single-stat gaming. The linear scaling above the threshold (`(min − τ)·c`) with per-bonus caps elsewhere is sensible. I'd hold this up in the whitepaper as the model's cleanest piece of football reasoning.

The one watch-item is **additivity across many bonuses**: an elite all-rounder can trigger several `min`-bonuses at once (a CAM can hit Maestro + Shadow Striker + Modern 10), and they stack additively with no global cap on total bonus. The masterclass-ST and elite-real-match cases hit 9.8–9.9, so the stacking is clearly bounded *in practice* by the sigmoid ceiling, but there's no explicit cap and a contrived god-game could pile bonuses pre-sigmoid. Low priority (the sigmoid saturates anyway), but a global per-position bonus cap would make the ceiling behaviour explicit rather than emergent.

### 1.9.4 The additive goal/assist multipliers ("absolute output multipliers", ST ×1.2 → CDM ×0.5) — **[SOUND in intent, but they're the real scoring engine and that should be acknowledged]**

These are flat per-goal / per-assist additions to the raw score, scaled by position: ST `goals×1.2/assists×0.6`, Winger `0.8/0.6`, CAM `0.7/0.9`, CM `0.8/0.6`, WM/WB `0.6/0.8`, CDM `0.5/0.4`, CB `0.6/0.4`, FB `0.4/0.6`. The ordering is football-sensible (strikers most rewarded for goals; creators/wide players tilted toward assists; defenders least). 

The important structural point (connecting to 1.7.1): because the goal *z-score* channel is heavily smoothed and log-compressed, **these additive bonuses are where the bulk of a goalscorer's rating actually comes from.** A striker who scores 2 gets `+2.4` to the raw score from this line alone — which, pre-sigmoid, is enormous (it's larger than most full dot-products). So the model's response to goals is dominated by a hand-set linear coefficient, not by the PCA weights. That's a legitimate design (it makes goal response predictable and tunable) but the whitepaper currently frames the weight vector as the scoring mechanism, when empirically this bonus line is. The finishing stress test makes the dominance visible: the Clinical Assassin (2 shots, 2 goals) and Wasteful Shooter (8 shots, 2 goals) both land ~9.2–9.4 — the **goals** (via this +1.2/goal line) set the rating; the shot volume barely moves it.

### 1.9.5 The contextual gates — evaluated individually

- **Wasteful Finisher Penalty (ST)** — **[DESIGN: the trigger is too easy to dodge].** Fires only if `shots > 3` **and** `finishing_deficit = (shots·0.20) − goals > 0.75`. The 0.20-xG-per-shot proxy is crude but acceptable given no per-shot xG. The problem is exposed by stress test 7B: the "Wasteful Shooter" (8 shots, 2 goals) **scores higher (9.4) than the Clinical Assassin (9.2)**, because `estimated_xg = 8·0.2 = 1.6 < 2 goals`, so `finishing_deficit = −0.4` and the penalty *never fires* — the player "out-finished" the 0.2/shot line, and the 6 extra non-goal shots add positive `non_goal_shots_p90` weight. So **taking more shots is rewarded as long as you also score**, and the penalty only catches players who both shoot a lot *and* fail to score. A striker has to be genuinely profligate (e.g. 8 shots, 0–1 goals) to be docked. If the intent is to discourage shot-hogging, the gate as written mostly doesn't, because the `non_goal_shots` reward and the lenient deficit threshold cancel it. Consider penalising on *shot volume above a positional norm* independent of goals, or lowering the deficit threshold. As-is, it's close to inert.
- **Black Hole Penalty (ST)** — **[SOUND].** Fires on `possession_lost > 4` and `turnover_ratio > 1.5` (losses per positive involvement), scales with excess losses, capped at 0.6. Targeted, capped, sensible. The `safe_positive_involvements = max(…, 1)` guard is correct. Good.
- **Target Man / Hold-Up Bonus (ST)** — **[SOUND].** Requires high involvement (≥15) *and* strong retention ratio (>4 involvements per loss), scales with excess retention, capped at 0.4. Reasonable and well-bounded. The `min` of conditions makes it hard to fake. Good.
- **Dynamic Clean Sheet Bonus (defenders/GK)** — **[SOUND, genuinely smart].** Scales the reward by opponent xG: low-xG clean sheet (dominant defending) → +0.5; high-xG clean sheet (rode luck / keeper bailed them out) → +0.15. This correctly separates "we stifled them" from "we survived them" using the one context signal the data does provide (xG). Strong design.
- **Collapse Penalty (defenders)** — **[SOUND].** `if opponent_goals ≥ 3 and minutes ≥ 60: −0.3`. The minutes gate correctly avoids punishing a defender for a collapse that happened after they were subbed. Simple, correct.

## 1.10 Impact scalar `√(min(M,90)/90)` and its interaction with Bayesian smoothing — **[DESIGN: not redundant, but the two mechanisms double-compress low-minute games toward neutral]**

The impact scalar multiplies the *processed raw score* by `√(min(minutes,90)/90)` before the sigmoid: 10 min → 0.333, 15 min → 0.408, 45 min → 0.707, 90 min → 1.0. Since the raw score is centred near 0 (it's a weighted sum of z-scores), multiplying by a sub-1 factor pulls low-minute performances **toward 0 → toward the 6.0 sigmoid anchor**, symmetrically: a *good* cameo is pulled down toward 6.0, a *bad* cameo is pulled up toward 6.0.

**Is this redundant with Bayesian smoothing ("dual protection")?** No — and this is the right answer to the user's question, but with an important qualification. The two mechanisms protect against *different* things:
- **Bayesian smoothing** regularises each *metric's rate* toward a prior, controlling the variance of the *inputs* (a 1-pass cameo doesn't read as a real passing rate).
- **The impact scalar** discounts the *aggregate conclusion* by sample size, controlling confidence in the *output* (even if every input were perfectly measured, 10 minutes is little evidence about overall contribution).

These are genuinely distinct: smoothing handles per-feature noise; the impact scalar handles overall sample confidence. You could have perfectly smoothed inputs and still want to discount a 12-minute conclusion. So it is **not** over-engineering in the sense of doing the same job twice.

**However**, they *compound* in the same direction (both shrink low-minute games toward neutral), and the result is the dominant source of the model's central compression — visible in the algorithm's *own* outputs, independent of any external reference. Every short cameo in the real-match runs collapses to a narrow band around 5.5–6.0 regardless of how the player actually did: a 14-minute LW who recorded nothing rates **5.6**; a 14-minute CB rates **5.7**; a 13-minute ST rates **5.7**. At 14 minutes the impact scalar is ~0.41, which (times a raw score already pulled toward 0 by the smoothing priors) leaves a near-zero input to the sigmoid, and the sigmoid maps near-zero to ~5.6–5.7. The designed Golden Sub stress test confirms the *upper* side of the same effect: a 15-minute, 1-goal cameo — which should arguably rate higher — is held to **7.3**, because the same 0.41 scalar caps how far a short sample can climb. **The dual mechanism makes the model structurally unable to strongly punish *or* strongly reward low-minute performances** — every cameo regresses to ~5.5–6.0.

Whether that's a flaw depends on philosophy. Statistically it's *defensible* (you genuinely have little evidence from 14 minutes, so regressing the conclusion toward neutral is the correct Bayesian move). But it is a deliberate design *choice* — "we regress short samples to neutral rather than over-reacting to them" — and it should be presented as that choice, with its consequence stated plainly: the model has very low rating resolution for substitutes and short cameos. If you want short games to retain more of their signal, soften one of the two mechanisms — e.g. raise the impact-scalar floor (`√(min(M,90)/90)` → `0.5 + 0.5·√(...)`) so a 14-minute game keeps ~65% rather than ~41% of its raw signal. **There is currently no external target in the data against which to judge whether the present compression is "too much" or "about right"** — that is a validation question (Part 3) that cannot be answered from the provided files, because the only comparison values are prior-version outputs and are disregarded.

**One concrete asymmetry to note:** because the impact scalar multiplies the raw score *before* the asymmetric sigmoid (1.11), and the sigmoid is steeper for positive scores (`k=0.85`) than negative (`k=0.45`), a good cameo and a bad cameo of equal |raw score| are *not* pulled toward 6.0 symmetrically in *rating* space — the good one moves more per unit of raw score. So the compression is slightly biased upward: a poor cameo lands a little above 6.0's mirror-point and a strong cameo a little below its, which is why the cameo band sits around 5.6–5.7 rather than symmetrically straddling 6.0.

## 1.11 Asymmetric sigmoid (`k=0.85` positive, `k=0.45` negative, anchor 6.0) — **[SOUND, with a kink to be aware of]**

`_apply_sigmoid_transformation`: `k = 0.85 if raw_score ≥ 0 else 0.45`; `s_0 = ln(2/3)/k`; `rating = 10·σ(k·(raw_score − s_0))`. I verified both branches yield exactly **6.0 at raw_score = 0** (because `s_0` is defined as a function of `k` precisely so that `σ(−k·s_0) = σ(−ln(2/3)) = 2/3`, giving `10·(... )`... — concretely `10/(1+e^{ln(2/3)}) = 10/(1+2/3)... ` resolves to 6.0 for both k). So the function is **continuous in value at the join** (no jump at 6.0).

**Why the asymmetry is correct:** `k=0.85` (steeper) on the positive side means good performances climb to 9–10 relatively quickly; `k=0.45` (shallower) on the negative side means bad performances descend toward 0 more slowly, so the model is *reluctant to hand out very low ratings*. This matches how football ratings actually behave (a 9.5 is rare but reachable; a sub-3 is almost never given for a player who completed the match) and it matches the research doc's observation that commercial scales bottom out around 3.0 in practice. The asymmetry deliberately compresses the bottom of the scale. Combined with the impact scalar (1.10) this is *why* the algorithm floors poor performances around 5.5 — the shallow negative branch plus low-minute discounting.

**The kink:** the function is continuous in value but **not in derivative** at raw_score = 0 — the slope jumps from `0.45·(...)` to `0.85·(...)` as you cross zero. This means a player sitting right at raw_score ≈ 0 experiences a slope discontinuity: a tiny improvement from −0.01 to +0.01 changes the *rate* at which further improvement is rewarded. In practice raw_score = 0 maps to 6.0 and the kink is mild, but it does mean the rating is marginally more "sticky" just below average than just above. If smoothness matters (e.g. for the sensitivity analysis in Part 3.6, where you differentiate the rating w.r.t. inputs), consider a single smooth asymmetric sigmoid (e.g. a skew-logistic) rather than two glued half-logistics. Low priority — the kink is small and at the least consequential point of the scale.

## 1.12 Match Supremacy Scalar — **[SOUND in construction, but with a strong, undocumented systematic interaction for attacking teams]**

`_calculate_match_supremacy_scalar`: `Δ = (team_xg+1)/(xg_against+1)`; `scalar = 0.2·ln(Δ)`; bounded `[−0.35, +0.25]`. Applied as `final_rating = raw_rating − scalar`. The logic: if your team dominated the chance-creation battle, an *average individual* line is less impressive (deduct); if your team was besieged, the same line is more impressive (the "siege bonus", which *adds* because subtracting a negative scalar raises the rating).

**Construction is sound:**
- The **Laplace +1** on both xG terms prevents division blow-ups and shrinks the ratio toward 1 in low-xG games (correct — you shouldn't infer dominance from 0.3 vs 0.1 xG).
- The **`ln`** dampening with **γ = 0.2** keeps the adjustment small and diminishing — a 2× xG edge gives `0.2·ln(2) = 0.14`, a 4× edge `0.2·ln(4) = 0.28` (then capped). Sensible scale.
- The **asymmetric bound** (`+0.25` deduction cap, `−0.35` siege floor) correctly makes the siege bonus larger than the dominance penalty — being heroic under siege should move the needle more than being ordinary in a rout.

**The undocumented interaction (important).** For this user's actual save, the supremacy scalar is **almost always a deduction**, because Valencia is consistently the xG-dominant team. I computed it for every match in the files:
- Match 95 (drew 2-2 away): Valencia xG 3.6 vs 2.3 → **−0.066** to every Valencia player.
- Match 96 (won 3-2): Valencia xG 5.5 vs 2.4 → **−0.130**.
- Match 87 (**lost** 1-0): Valencia xG 3.2 vs 1.6 → **−0.096**.
- Example match 106 (won 4-0): xG 6.4 vs 0.2 → capped at **−0.25**.

So in 100% of the available matches the scalar *suppresses* Valencia's ratings, including a match they **lost**, and the `−0.35` siege floor — the entire positive half of the mechanism — **never activates** for this user, because Valencia never gets out-created. (These deductions are computed directly from the team xG values in the match data and stand on their own; they don't depend on any rating comparison.) The result is a quiet, league-wide downward pressure on a possession-dominant team's ratings, applied uniformly to all 10 outfielders regardless of individual merit: a brilliant individual game in a dominant match eats a `−0.13` to `−0.25` deduction it did nothing to cause. A standout 92-minute holding midfielder in the 5.5-xG win, for instance, is docked the full `−0.13` purely for his team's chance-creation edge — the player who often *built* that edge is penalised for it.

**This is not a bug** — it's the mechanism working as designed — but its *practical* effect for an attacking team is one-sided, and the whitepaper should say so. Two things worth considering: (a) the scalar is **team-level**, so it can't tell apart the player who *created* the dominance from one who coasted in it — arguably the deduction should be modulated by individual involvement (an isolation-style gate), so the players who built the xG edge aren't docked for their team's success; (b) if a team is systematically xG-dominant, the scalar becomes a near-constant offset, and a constant offset on a rating scale is just a re-centring that could be absorbed elsewhere — its discriminative value comes from *variation* in supremacy across matches, which is small for a consistently dominant side.

## 1.13 Alpha Drag multi-position hybridisation `α = 0.25·cos_sim` — **[DESIGN: the cosine-similarity idea is reasonable, the 0.25 base is arbitrary, and the inputs are partly circular]**

For multi-position players, the final rating is `r_max − α·(r_max − r_mean)` with `α = 0.25·mean_cosine_similarity(max_pos, other_positions)`. So the player is rated primarily at their best position, dragged toward the mean of all positions by an amount proportional to how *tactically similar* the positions are.

**The core idea is sound.** If a player is listed at two near-identical roles (CM/CDM), the secondary rating is informative and should pull the final toward the average (high α). If listed at two orthogonal roles (a CB/ST emergency reshuffle), the secondary rating is an artefact of evaluating a defender with striker weights, so it should be largely ignored (low α, stay near `r_max`). Using cosine similarity between weight vectors to gate this is a clever, cheap proxy. And the floor behaviour is right: `cos(ST, CB) = 0.097` (I verified), so an emergency CB-as-ST gets almost no drag — correct.

**Three criticisms:**
1. **The 0.25 base coefficient is unjustified.** Why 0.25 and not 0.3 or 0.5? At `cos = 1` (identical roles) α = 0.25, so even for two *identical* positions the player is dragged only 25% of the way from their best to their mean rating — i.e. their *worse* position is given at most 25% weight. There's no derivation for this; it's a taste parameter, and it interacts with the cosine range (cosines among real outfield positions cluster in 0.5–0.9, so effective α is mostly 0.13–0.23 — a narrow, gentle band). That may be fine, but it should be acknowledged as a free parameter and tuned against an external reference once one is acquired (Part 3 — none exists in the current files).
2. **Cosine similarity between PCA-derived vectors is a noisy similarity proxy, and for derived positions it's partly circular.** As noted in 1.8.4, `cos(CAM, CM) = 0.882` and `cos(RWB, RB) = 0.906` are high *because those vectors were defined by multiplying each other*. So for the common case of a player listed at a base position and its derivative (RB/RWB, CM/CAM), the "tactical similarity" the model uses is an artefact of the inheritance, not independent evidence. The drag will be strong for exactly the pairs where the weight vectors are least independent.
3. **It only ever drags down (toward the mean), never reflects genuine versatility positively.** A player who is *genuinely good at two different roles* (a real CM/CDM who'd rate 7.5 at both) gets `r_max ≈ r_mean`, so the drag is ~0 and they just get their (deserved) high rating — fine. But a player who is excellent at one and mediocre at a *similar* role gets pulled down, with no mechanism to reward the rarity of competent multi-role play. That's a philosophical choice (versatility isn't intrinsically rewarded) and defensible, but worth stating.

The mechanism is reasonable and I wouldn't rip it out; I'd (a) document 0.25 as a tunable, (b) note the circularity for base/derived pairs, and (c) consider computing cosine similarity from the *means/stds profile* or an independent role taxonomy rather than from the weight vectors themselves, to break the circularity.

## 1.14 Goalkeeper isolation pipeline — **[SOUND core, with a heavily hand-tuned conditional ladder that risks overfitting to specific past matches]**

The GK path is entirely separate (different heuristic, no PCA weights, own mean/std). Core heuristic:

```
H_GK = (xGP · 1.5) + (ln(saves + 1) · save% / 100)
```

where `xGP = xg_against − goals_conceded` (expected goals prevented). Then `raw_score = (H_GK − μ_GK)/σ_GK` (μ=2.10, σ=1.70), followed by four adjustment layers, a clean-sheet bonus ladder, the supremacy scalar, and the sigmoid.

**The core heuristic is sound and well-shaped:**
- **`xGP · 1.5`** is the right primary signal — it directly measures shot-stopping value over expectation (did the keeper concede fewer than the chances warranted?), which is the one thing GK xG data *can* tell you. The 1.5 multiplier makes it the dominant term. Good.
- **`ln(saves+1)·save%/100`** rewards save *volume* (log-compressed, so a 7-save game doesn't dwarf a 3-save game linearly) gated by save *quality* (success rate). The product means high volume only helps if the success rate is decent — a keeper who faced 10 and saved 5 (50%) gets less than one who faced 6 and saved 5 (83%). Sensible.
- The combination cleanly separates "prevented goals vs expectation" (primary) from "was busy and reliable" (secondary). I'd keep it.

**The concern is the adjustment ladder.** The explicit-conditionals layer (`_apply_gk_explicit_adjustments`) has named special cases — "Spectator Exemption" (0 SoT, 0 conceded → return 0.0), "1-Goal Narrow Miss" (floor −0.15), "Positive Impact Anchor", "Shootout Victim" (floor −0.35) — and the low-volume layer has the **"Match 69 Fix"** (`shots ≤ 3 and conceded ≤ 1 → floor −0.5`). The name "Match 69 Fix" is a tell: this is a floor reverse-engineered to repair one specific historical match's output. A ladder of hand-set floors tuned to named past matches is **overfitting to the calibration set** — each fix repairs a known case but the stack of them has unknown behaviour on unseen score/shot combinations, and they interact (a game can satisfy multiple floors; the order of application then matters — and the code applies them as sequential early-returns, so the *first* matching floor wins, which is an implicit and undocumented priority ordering). Concretely, in `_apply_gk_explicit_adjustments` the `return` on each branch means a 1-goal game with `xgp ≥ −0.25` exits at the −0.15 floor and never sees later logic — that priority is doing real work and isn't documented.

The GK pipeline produces internally sensible outputs on the example data (the example GK: 7 shots, 3 on target, 2 saves, 1 conceded, 67% save rate — the ladder's 1-goal/low-volume floors are what stop the raw score from running away downward on a single-goal game). But "sensible on the cases it was tuned on" is exactly the overfitting risk. **Recommendations:** (a) replace the named-match floors with a *single* principled low-volume confidence shrink analogous to the outfield impact scalar — e.g. shrink `raw_score` toward 0 by `√(shots_against / k)` so few-shot games regress to neutral without a ladder of special cases; (b) make the priority ordering explicit and tested; (c) the **penalty heroics** (`+0.5` per pen/shootout save) and **inverted clean-sheet bonus** (passenger +0.30 / standard +0.50 / bailout +0.80, scaled by xG-against and saves) are both well-designed and should stay — the bailout/passenger split mirrors the outfield dynamic clean-sheet bonus and correctly rewards a keeper who earned the clean sheet over one who watched it. The problem is specifically the reverse-engineered floors, not the bonuses.

---

# PART 2 — PROFESSIONAL COMPARISON

The research doc (`Football_Player_Rating_Algorithm_Design.docx`) already establishes the commercial landscape — Sofascore's 3.0–10.0 scale with a 6.5 init and ~60 in-match iterations, WhoScored/Opta's 0.0–10.0 with a 6.0 init, the GLMM + Elastic Net reverse-engineering of 2,100 players, the ICC ≈ 0.26 finding, the Poisson/Gamma → log → inverse-logistic chain. I won't restate that. This part is my own assessment of **where Gaffer's Clipboard actually sits relative to those systems and to the academic state of the art, given the specific data it has to work with** — what it does as well as a professional system *despite* the data gap, and where it falls short *even within* the gap.

## 2.1 The right frame: this is a data-availability problem, not an algorithm-sophistication problem

The instinct is to compare algorithms. That's the wrong axis. The gap between Gaffer's Clipboard and Sofascore/StatsBomb is overwhelmingly a **data** gap, and only secondarily a modelling gap. Lay out what the commercial and academic systems consume that Career Mode's box score does not provide:

| Signal | Sofascore / Opta | StatsBomb (VAEP/OBV) | FBref/StatsBomb composites | **Gaffer's Clipboard (Career Mode box score)** |
|---|---|---|---|---|
| Per-event location (x,y) | ✓ | ✓ (freeze-frames) | ✓ | ✗ |
| Per-shot xG (location/bodypart/GK position) | ✓ | ✓ | ✓ | ✗ (only *team* match xG) |
| Progressive passes / carries | ✓ | ✓ | ✓ | ✗ |
| Pressures / PPDA / pressing | partial | ✓ | ✓ | ✗ |
| Pass network / receiving location | partial | ✓ | ✓ | ✗ |
| Defensive actions by zone | ✓ | ✓ | ✓ | ✗ (only totals: tackles, possession won) |
| Aerial duels, interceptions split out | ✓ | ✓ | ✓ | ✗ (folded into tackles/possession) |
| On/off and sequence involvement | ✓ | ✓ | partial | ✗ |
| Per-player minute-by-minute | ✓ | ✓ | — | ✗ (one aggregate line per player) |

What Gaffer's Clipboard *does* have: per-player match totals (goals, assists, shots, shot accuracy, passes, pass accuracy, dribbles, dribble success, tackles, tackle success, offsides, fouls, possession won/lost, distance covered, distance sprinted, minutes) plus **team-level** match xG and possession. That's roughly the granularity of a 1990s paper box score plus two modern team aggregates (xG, distance). 

So the honest benchmark is not "is this as good as VAEP?" — it categorically cannot be, because VAEP needs event-stream location data this model will never see. The benchmark is: **given a box score, does this extract close to the maximum recoverable signal, and does it degrade gracefully where the data simply isn't there?** On that benchmark it does well, with specific exceptions below.

## 2.2 Versus Sofascore / WhoScored (event-weighted accumulation)

Sofascore and WhoScored are, mechanically, **weighted accumulators**: each on-ball event has a coefficient (positive or negative, often context-multiplied by location/difficulty), and the rating is an initialised baseline (6.0/6.5) plus the running sum, iterated through the match. Gaffer's Clipboard is structurally *similar in spirit* — a positional weight vector dotted with standardised contributions, plus event bonuses, mapped through a sigmoid — but with three architectural differences that are worth being precise about:

- **Standardisation vs raw accumulation.** The commercial systems weight *raw* events; Gaffer's Clipboard weights **z-scores against a positional baseline**. This is actually a *more* statistically defensible core than naive accumulation: it automatically handles "a CB making 5 tackles is exceptional; a CDM making 5 is average" without per-position event coefficients, because the baseline is positional. This is a genuine strength and arguably the model's best structural decision. The cost is that it needs reliable positional means/stds — which, on a single team's data, are themselves noisy (the recurring theme of Part 1).
- **The initialisation anchor.** Both Gaffer's Clipboard (6.0 at z=0) and the commercial systems (6.0–6.5) anchor an average game near 6. Gaffer's Clipboard's asymmetric sigmoid (1.11) reproduces a known *behaviour* of the commercial scales — reluctance to go below ~3, faster ascent to the top — that the research doc notes is empirically observed in Sofascore/WhoScored outputs. So the *output distribution shape* is plausibly close to commercial systems even though the inputs are far poorer. This is a real point in its favour: **the model targets the right output manifold.**
- **In-match iteration.** Sofascore iterates ~60×/match, letting the rating reflect *when* things happened and momentum. Gaffer's Clipboard is a **single post-match computation** on totals — it has no temporal within-match resolution at all (the data doesn't support it). For a Career Mode companion this is the correct scope (you enter the box score after the match), but it means the model can never capture the "came alive in the last 20 minutes" or "anonymous after a bright start" texture that the iterated systems encode. Not a flaw — a scope boundary — but worth stating so the whitepaper doesn't over-claim parity.

**Where it matches the commercial systems well:** positional context handling (via z-scores) is arguably *cleaner* than the commercial per-event coefficient tables. **Where it falls short of them even on shared data:** it has no event-difficulty weighting — a tackle is a tackle, a pass is a pass, because the box score doesn't say which tackle was a last-ditch block and which was a 30-yard-from-goal nothing. The commercial systems weight by location/difficulty; this model fundamentally can't, and the `xT` proxy (1.3) is its only — and weak — attempt to recover a difficulty/threat dimension.

## 2.3 Versus StatsBomb VAEP / OBV (possession-value chain) — the largest conceptual gap, and the most instructive

This is where the comparison is most useful, because VAEP/OBV represent a *different paradigm*, not just better data, and understanding the gap clarifies what Gaffer's Clipboard is and isn't.

VAEP (Decroos et al., 2019) and OBV value **every action by its effect on the probability of scoring and conceding in the near future**, learned from millions of possession sequences: an action's value is `ΔP(score) − ΔP(concede)` over the next few actions. This is a *possession-value chain* — it credits the pass *before* the assist, the carry that broke the line, the recovery that started the move. It is the current state of the art for on-ball valuation.

Gaffer's Clipboard has **no possession-value chain and cannot have one**, for two reasons: (a) no event sequence data (it has totals, not ordered actions), and (b) no location data (VAEP's probabilities are location-conditioned). So the entire "value the build-up, not just the end product" philosophy is inaccessible. What the model does instead is interesting and worth framing honestly:

- It **approximates chain involvement with the `xt_bonus` proxy and the bottleneck-synergy bonuses.** The `min(passes_z, xt_z)` "Maestro", `min(sprint_z, xt_z)` "Express Train", etc. (1.9.3) are crude stand-ins for "this player was involved in progression", reconstructed from totals rather than sequences. This is genuinely clever *given the constraint* — it's trying to reward the VAEP-style "involved in good stuff" signal without the data VAEP needs.
- But it **cannot attribute value across players.** VAEP's headline capability is taking a goal and distributing credit backward along the chain (the assister, the line-breaker, the recoverer). Gaffer's Clipboard credits the **goal to the scorer** (via the +1.2 bonus) and the **assist to the assister** (via +0.6–0.9) and nothing to the player two passes back, because totals don't encode the chain. So it systematically **under-credits deep build-up contributors** and **over-credits end-product** relative to VAEP. This is visible in the model's DNA: the additive goal/assist bonuses (1.9.4) are the scoring engine, and there is no "pre-assist" or "chain involvement" credit beyond the weak xT proxy.

**The instructive conclusion:** Gaffer's Clipboard sits philosophically *closer to the pre-VAEP, box-score-composite tradition* (weight observable totals) than to the modern possession-value paradigm — and that's not a failing, it's the only option on this data. The thing to *avoid* is implying in the whitepaper that the `xt_bonus` is an "xT" in the Karun Singh sense. Real xT is a **positional value surface** — the probability-weighted value of having the ball in a given pitch zone, used to value a pass by `xT(end_zone) − xT(start_zone)`. Gaffer's Clipboard's `xt_bonus` is a **player-effort heuristic** (sprint share × control × passing involvement) with no pitch model and no zone values. It shares the *name* and the *goal* (capture progression/threat) but none of the *method*. Calling it an "xT proxy" is fair; calling it "xT" would be a category error the whitepaper should be careful to avoid.

## 2.4 Versus FBref / StatsBomb composite percentile profiles

FBref-style player evaluation doesn't produce a single match rating — it produces **per-90 percentile profiles** against positional peers (this player is in the 88th percentile for progressive passes among CMs, etc.). Gaffer's Clipboard's **z-score-against-positional-baseline core is the same idea** — it's computing, in effect, a standardised positional percentile for each metric, then collapsing them with weights. So the *input layer* of Gaffer's Clipboard is conceptually aligned with the most respected public evaluation framework. The difference is:
- FBref percentiles are computed against **thousands of peers across many teams/leagues**; Gaffer's Clipboard's baselines come from **one team's matches**. So the "percentile" is really "percentile within this Valencia save", which is a much narrower and noisier reference class. A metric where Valencia is unusual (they're a high-possession side) will have a baseline that doesn't generalise to how Career Mode's *opponents'* players would be rated by the same model.
- FBref stops at the profile and lets a human judge; Gaffer's Clipboard collapses the profile into one number via the weighted sum. The collapse is where the philosophy/PCA weighting lives, and (per Part 1) where most of the modelling risk concentrates.

**Net:** the model's standardisation layer is in good company — it's doing something close to what FBref does and what the z-score literature prescribes. Its weakness is the **reference class** (one team) and the **collapse** (prior-dominated weights), not the standardisation concept itself.

## 2.5 Where the design handles the data gap *well*

To be concrete about strengths, because the whitepaper should claim these confidently:

1. **Positional z-score standardisation as the core.** Automatically handles role-relative evaluation without per-event coefficient tables. This is the single best structural decision and it aligns with both FBref practice and the z-score literature the research doc cites.
2. **The bifurcated Bayesian prior (1.2.2).** Shrinking rare events toward 0 and volume events toward the positional mean is exactly the empirical-Bayes move you'd want, and it's the right answer to small-sample Career Mode games (short halves, subs).
3. **xG-scaled clean-sheet bonuses (1.9.5) and the GK bailout/passenger split (1.14).** These extract real signal from the *one* contextual variable the data provides (team xG), separating "earned it" from "rode luck". This is the model using its scarce context data intelligently.
4. **Bottleneck-synergy `min()` bonuses (1.9.3).** A genuinely elegant way to reward archetype *completeness* from totals, resistant to single-stat gaming. No commercial system needs this trick (they have richer data), but as a box-score device it's excellent.
5. **The asymmetric sigmoid targeting the commercial output manifold (1.11).** The model lands ratings in a distribution shaped like the systems it's emulating — bottoming out around 3 rather than 0, rising quickly to 9–10 — which is a deliberate, defensible structural choice (it matches the empirically-observed shape of the commercial scales described in the research doc), independent of any agreement statistic.

## 2.6 Where it falls short *even within* the data constraints (i.e. fixable without new data)

These are shortfalls the model *could* address with the data it already has — they're not data-gap-imposed:

1. **No event-difficulty or threat-location weighting — and the one attempt (xT proxy) measures effort, not threat (1.3).** Within the box score there's no location, true — but the proxy currently rewards sprint share and ball-winning, which is closer to *work rate* than *threat*. A box-score-honest threat proxy would lean harder on shots, shot accuracy, key-pass-implied assists, and final-third involvement signals, not sprint distance. This is fixable within the data.
2. **Team context is under-used and one-sided (1.12).** The model has team xG and possession but uses them only for the supremacy scalar (which, for an attacking team, is a near-constant deduction) and clean-sheet scaling. It does **not** use possession at inference at all (the train/serve skew of 1.6.1), and it doesn't use the opponent's defensive strength or the match state. There's recoverable context signal being left on the table.
3. **Action-level attribution is absent where it's partially recoverable.** True VAEP chains need sequences, but the model could still approximate "involvement in scoring moves" better than it does — e.g. crediting a high-pass-volume, high-xT game in a high-team-xG match more than the current weak coupling does. The supremacy scalar even *penalises* players in high-xG matches rather than crediting the creators.
4. **The reference class is a single team.** Every baseline is Valencia's. Opponent players rated by this model would be judged against Valencia norms. Within the data constraint you can't fix the *source*, but you can (a) be honest that the model is calibrated to one team's style, and (b) widen the calibration set as more saves accumulate. This is the most important medium-term improvement and needs no new *kind* of data, just more of the same.
5. **Prior-dominated weights presented as data-driven (1.6).** The PCA pipeline could be simplified to an explicit expert-weighting model (which is largely what it already is) with PCA used honestly as a light regulariser, or the dataset widened until PCA has enough signal to lead. Right now it's the worst of both: the complexity and opacity of PCA with the substance of hand-set priors.

## 2.7 Overall placement

Gaffer's Clipboard is a **well-constructed box-score composite rating** that, on the axis that matters (extracting positional, context-aware signal from match totals), is methodologically *ahead* of naive event-accumulation and *aligned* with the respected percentile-profile tradition (FBref) at its input layer. It is **categorically behind** the possession-value paradigm (VAEP/OBV) and the iterated commercial systems (Sofascore) — but that gap is imposed by data availability, not by the algorithm, and the model degrades into that gap fairly gracefully via Bayesian shrinkage and the impact scalar. Its real, *addressable* weaknesses are internal: the xT proxy measures the wrong thing, team context is under-exploited and one-sided, the weights are prior-dominated while presented as learned, and everything is calibrated to a single team. None of those require richer data to fix. The structural design is coherent and the designed stress tests behave as intended — but it must be stated plainly that the model's accuracy is, at present, **unvalidated**: there is no external reference in the provided files (the prior-version `match_rating`/`Expected` values are disregarded), so no agreement statistic can stand behind a claim that "the core is sound". Part 3 is therefore about two things: the internal/stability/sensitivity evidence you *can* generate now, and — more importantly — what kind of external target you would need to **acquire** before any validity claim is defensible.

---

# PART 3 — VALIDATION METHODOLOGY

Each method below is presented as: **what it tests for this specific algorithm**, **how to run it on this data**, and **what a pass/fail looks like**. Where I can, I anchor the method with the numbers already computable from the files. Citations are given confidently from the literature; any I'm not fully certain about are flagged **[verify]**.

## 3.0 The validation-target problem (read this first — it is now the binding constraint)

There is **no true ground truth** for a football rating — "the correct rating" doesn't exist as a measurable quantity. Worse, for this project there is currently **no external reference of any kind**. The `match_rating` field in `example_matches.json` and the `[Expected: …]` values in the testing notebook are **outputs of a previous version of this same algorithm**. They must **not** be used as a validation target, and they are not used anywhere in this review. The reason is not pedantry: correlating the current model against a previous version of itself measures **version-to-version drift**, not validity. A high correlation there would mean only "the refactor didn't change much"; it says nothing about whether *either* version is *correct*, and treating it as validation would manufacture a circular illusion of accuracy (the model looks good because it agrees with an earlier model built on the same assumptions). That is the single most dangerous trap in evaluating this system, and it is worth stating in the whitepaper explicitly.

So the validation families actually available split into two groups:

- **Runnable now, with no external target** — because they interrogate the model's *internal* behaviour:
  - **Internal reliability / stability** (3.4): does the model give stable outputs under trivial input changes and across the user-chosen half length?
  - **Sensitivity / robustness** (3.5, 3.6): which parameters drive the ratings, and how much do the small-sample weights wobble under resampling?
  - **Face / known-groups validity** (3.7) via the *designed* stress tests: does a masterclass striker rate ~9.8 and a nightmare centre-back rate low? These scenarios encode an intended qualitative ordering and need no external rater.
  - **Predictive validity against match outcomes** (3.8): the match *results* are in the data and are a genuine external signal that is **not** a rating — does team-average rating track results? This is the one external-criterion check available right now, and it should be elevated.
  - **The model's own variance structure** (3.1): fit a GLMM to the algorithm's *own* ratings and compare its context-ICC to the commercial ≈ 0.26 benchmark — this needs the model's outputs only.

- **Blocked until an external target is acquired** — rank agreement (3.2) and Bland–Altman agreement (3.3) both compare two raters, and you do not currently have a legitimate second rater. To unblock them you must **source an independent reference**, e.g.: (a) you hand-label a held-out set of games with your own expert rating (slow but honest, and it makes *you* the criterion — defensible for a personal tool); (b) genuine third-party ratings if Career Mode or a community source exposes them; (c) consensus ratings from multiple human annotators. Until one exists, **the model's accuracy is unvalidated**, and the whitepaper should say so rather than imply otherwise.

The practical consequence: the headline validation for now is **stability + sensitivity + known-groups + outcome-prediction**, not agreement. Agreement is the goal, but it requires an investment in a reference dataset that doesn't yet exist.

## 3.1 Generalised Linear Mixed Models — to validate the Match Supremacy Scalar against the ICC ≈ 0.26 finding

**What it tests.** The research doc's headline statistic is that ≈ 26% of commercial-rating variance is *hierarchical context* (match/team/player), not individual on-ball action — i.e. roughly a quarter of "how good a rating looks" is the situation, not the player. The Match Supremacy Scalar (1.12) is the model's *entire* attempt to absorb that 26%. A GLMM is the correct tool to ask: **does the supremacy scalar actually capture the match/team-level variance it's meant to, or is it leaving structured context variance in the residuals?**

**How to run it on this data (no external target needed).** Fit the GLMM on the algorithm's **own** ratings as the response, with random intercepts for `match` and `player` (and `team` once you have more than one):

```
rating_ij = β0 + (fixed effects: per-feature contributions) + u_match[j] + u_player[i] + ε_ij
```

using `lme4::lmer` in R or `statsmodels`/`pymer4` in Python, then compute the variance partition (ICC per level) via the Nakagawa–Schielzeth decomposition. **Interpretation specific to this model:**
- Compute *your* model's **match-level ICC** — the share of total rating variance attributable to which match a player was in. Compare it to the commercial ≈ 0.26 benchmark from the research doc. If your model's match/team ICC is **much lower** than 0.26, the supremacy scalar + clean-sheet bonuses are under-contextualising relative to commercial systems (the model is treating players too much as islands); if **much higher**, the supremacy scalar is over-contextualising (match identity is swamping individual signal — plausible for an attacking team where the scalar is a near-constant per-match deduction, 1.12).
- The **player-level ICC** tells you how much a player's rating is "who they are" vs "what they did this match" — a sanity check on whether the model has accidentally become a reputation system.
- This is the right way to interrogate the supremacy scalar's job (absorbing the 26% context variance) **without** needing any external rating, because it asks how *your* variance is structured, not whether it matches someone else's.

**Caveat for this dataset:** with only a handful of matches and one team, the `team` random effect is unidentifiable (no between-team variance — there's one team) and `match` has few levels. You need many more matches (ideally 30+) before GLMM variance estimates are stable. Until then this is the *target* methodology, not one you can run reliably yet — state that honestly.

*Citations:* Nakagawa, S. & Schielzeth, H. (2013), "A general and simple method for obtaining R² from generalized linear mixed-effects models", *Methods in Ecology and Evolution* 4(2):133–142 — the marginal/conditional R² and ICC partitioning. Bates, D., Mächler, M., Bolker, B., Walker, S. (2015), "Fitting Linear Mixed-Effects Models Using lme4", *Journal of Statistical Software* 67(1). Gelman, A. & Hill, J. (2007), *Data Analysis Using Regression and Multilevel/Hierarchical Models*, CUP — for the hierarchical framing and partial pooling. For ICC interpretation thresholds, Koo, T.K. & Li, M.Y. (2016), "A Guideline of Selecting and Reporting Intraclass Correlation Coefficients for Reliability Research", *Journal of Chiropractic Medicine* 15(2):155–163.

## 3.2 Spearman ρ and Kendall τ — rank agreement (blocked: needs an external target)

**What it tests.** A rating system's first job is to get the *ordering* right — within a match, did the best players get the highest ratings? Rank correlation tests exactly this and is robust to scale/offset differences between two raters (you need only their order to agree, not their numbers). Spearman (ρ) is rank-Pearson; Kendall (τ) counts concordant vs discordant pairs and is more robust to ties and small n — report both, with τ the more honest one at ~15 players per match.

**Why it's blocked right now.** Rank correlation requires a *second* rater to correlate against, and you do not currently have a legitimate one. The prior-version `Expected` values are not a valid target (3.0). Computing ρ/τ against them would only tell you whether the current version preserves the *ordering* produced by the previous version — which is a useful **regression test** (e.g. "did my refactor of the CDM modifiers reorder the midfielders?") but is **not** validation and must never be reported as such. Keep it in your test suite labelled as a regression check; keep it out of any accuracy claim.

**How to unblock and run it.** Once you have an external reference (3.0: your own held-out hand-labels, or sourced third-party ratings), pool the per-match `(algorithm, reference)` pairs and compute ρ and τ — but report **per-match** rank correlation as the headline, not pooled. Pooled correlation is inflated by the easy cross-match spread (separating a 9-something masterclass from a 5-something cameo is trivial); the real test is *within-match* ordering, which is what a manager actually reads. A per-match mean τ in the 0.6–0.8 band against honest expert labels would be a credible "the ordering is right"; low *variance* in per-match τ would show it's *consistently* right, not just on average.

*Citations:* Spearman, C. (1904), "The proof and measurement of association between two things", *American Journal of Psychology* 15:72–101. Kendall, M.G. (1938), "A new measure of rank correlation", *Biometrika* 30:81–93. For ranking-quality evaluation of player-rating systems against a reference, see Pappalardo et al. (2019), *PlayeRank* (cited in 3.8) — they emphasise rank/agreement-based evaluation; **[verify]** whether the specific coefficient is Spearman.

## 3.3 Bland–Altman agreement (blocked: needs an external target) — and what to do instead now

**What it tests.** Where rank correlation says "order is right", Bland–Altman says "are the two raters' *values* interchangeable, and if not, *where* do they drift?" It plots the difference `(rater A − rater B)` against the mean, draws the bias and 95% limits of agreement, and reveals **proportional bias** (does the gap depend on the rating level?). For a rating system this is the most diagnostic single agreement plot.

**Why it's blocked right now.** Like 3.2, Bland–Altman compares two raters and you have no valid second rater. Running it against the prior-version values would chart **version drift**, not agreement-with-truth — fine as a release diagnostic ("how far did v_n move from v_{n−1}, and at which part of the scale?"), useless as validation. Do not present any Bland–Altman result until you have an external reference (3.0).

**What you *can* establish now without a second rater.** The thing Bland–Altman would have diagnosed — the model's **central compression** — is observable directly from the algorithm's *own* output distribution, no comparison required:
- **Rating vs minutes played.** Plot every output rating against minutes. You will see the cameo band: sub-20-minute games collapse into ~5.5–6.0 regardless of performance (the impact-scalar + smoothing effect, 1.10). This is intrinsic to the outputs and is real evidence of the compression mechanism, established with zero reliance on any target.
- **Rating vs team xG (or supremacy deduction).** Plot ratings against the match's supremacy deduction. For a possession side every match sits on the deduction side (1.12), so you'll see a near-constant downward shift on dominant matches — again visible in the outputs alone.
- **Output histogram.** Plot the distribution of all ratings. If it's tightly piled around 5.5–6.5 with thin tails, that *quantifies* the compression (and you can compare its spread to the commercial scales' known spread from the research doc — a distribution-shape check, not an agreement check).

These three plots give you most of the diagnostic value of a Bland–Altman analysis (where and how the model compresses) using only the model's own outputs, and they're the right thing to ship in the whitepaper now. Reserve true Bland–Altman for when a reference exists.

*Citations:* Bland, J.M. & Altman, D.G. (1986), "Statistical methods for assessing agreement between two methods of clinical measurement", *The Lancet* 327(8476):307–310. Bland, J.M. & Altman, D.G. (1999), "Measuring agreement in method comparison studies", *Statistical Methods in Medical Research* 8(2):135–160 — for the proportional-bias extension you'll want once a reference is in hand.

## 3.4 Intraclass Correlation (test–retest reliability across similar match conditions)

**What it tests.** Reliability ≠ agreement. ICC here asks: **does the model give the *same* player the *same* rating across matches where they performed similarly?** A rating system that swings wildly for near-identical box scores is unreliable regardless of whether it's accurate. This is a purely internal check — it needs no external reference, which is exactly why it's available now.

**How to run it on this data.** You can't do classic test–retest (you don't have the same match scored twice), so use one of two proxies:
1. **Synthetic perturbation retest (available now).** Take a real player-line, perturb non-substantive inputs slightly (±1 on a counting stat, ±5 min, swap half-length representation), recompute, and measure rating stability. The model should be near-invariant to trivial perturbations. The sigmoid-gradient stress test (6A/6B/6C → 5.8/5.8/5.9) is exactly this kind of check and it *passes* — small input changes produce small output changes, no discontinuities. Formalise it: ICC(consistency) across a grid of perturbed versions of each real line. High ICC = stable.
2. **Near-neighbour retest (needs more data).** Cluster historical player-games by box-score similarity; within tight clusters, the model's rating variance should be low relative to its across-cluster variance. ICC(2,1) (two-way random, absolute agreement; Shrout–Fleiss type) quantifies this.

**Specific thing to test for this model:** the **half-length invariance**. The stress tests run each scenario at both 4-min and 10-min halves (e.g. Golden Sub 7.3 vs 7.0, Nightmare CB 4.3 vs 4.1). The ratings are *close* but **not identical** (~0.2–0.3 apart). That residual half-length sensitivity is a mild reliability leak — the temporal scalar (1.1) plus the minute-based smoothing prior don't fully cancel, so the same performance at different half lengths rates slightly differently. ICC across half-length variants would quantify it; ideally it's > 0.95 (it looks close). This is worth a formal check because half length is a *user setting*, and ratings shouldn't depend on it.

**Pass/fail:** ICC(consistency) > 0.9 across trivial perturbations and half-length variants.

*Citations:* Shrout, P.E. & Fleiss, J.L. (1979), "Intraclass correlations: uses in assessing rater reliability", *Psychological Bulletin* 86(2):420–428 — the canonical ICC(model,form) taxonomy. Koo & Li (2016, cited above) for choosing the right ICC form and interpreting magnitude (poor <0.5, moderate 0.5–0.75, good 0.75–0.9, excellent >0.9). McGraw, K.O. & Wong, S.P. (1996), "Forming inferences about some intraclass correlation coefficients", *Psychological Methods* 1(1):30–46 — **[verify]** for the consistency-vs-absolute-agreement distinction you'll need.

## 3.5 Sensitivity analysis on the weight vectors and the hand-set parameters

**What it tests.** Part 1 establishes that the model is **prior-dominated**: the PCA weights are substantially the `philosophy` dicts (1.6.2), the goal/assist response is the additive bonus (1.9.4), and there are many free constants (sigmoid `k=0.85/0.45`, supremacy `γ=0.2` and bounds, Alpha-Drag base `0.25`, impact-scalar exponent, smoothing `d=15/30/45`, every bonus cap and threshold). Sensitivity analysis asks: **which of these knobs actually move ratings, and is the model fragile to the ones that were set by taste?** A parameter that swings ratings by a full point per small change is one you *must* justify; one that barely matters can be left alone.

**How to run it.** One-at-a-time (OAT) and then variance-based:
- **OAT:** perturb each parameter ±10–20%, recompute every rating, and record the resulting mean |Δrating| and the change in the output distribution's shape (and in the known-groups separation of 3.7 — does a masterclass still clear a nightmare game by the same margin?). Rank parameters by influence. I'd predict from Part 1 that the **goal/assist additive multipliers** and the **sigmoid `k`** dominate, the **supremacy γ** matters for dominant-team players, the **impact-scalar exponent** drives the low-minute compression, and most **bonus caps/thresholds** barely register (they fire rarely). Confirming that prediction tells you where to spend validation effort and which "taste" parameters carry the most unjustified weight.
- **Weight-vector sensitivity:** since the weights are the model's heart, perturb each positional weight vector with Dirichlet noise (preserving sum-to-1) and measure rating stability. If ratings are robust to weight perturbation, the exact PCA-vs-philosophy debate (1.6) *doesn't matter much* and you can stop worrying about it; if they're fragile, the weight derivation needs to be defensible, which currently it isn't.
- **Variance-based (Sobol) indices** if you want to capture interactions (the supremacy × impact-scalar interaction noted in 1.10 is exactly the kind of thing OAT misses).

**Specific high-value test:** sweep the **impact-scalar floor** and re-measure the rating-vs-minutes plot from 3.3. This directly tests the Part 1 hypothesis that the impact scalar manufactures the low-minute compression — if raising the floor visibly widens the cameo band (lets short games escape the 5.5–6.0 pile), the diagnosis is confirmed and you have a tuning lever, all without needing any external target.

*Citations:* Saltelli, A. et al. (2008), *Global Sensitivity Analysis: The Primer*, Wiley — OAT vs variance-based, Sobol indices. For the principle that composite-index weights must be sensitivity-tested, the OECD/JRC *Handbook on Constructing Composite Indicators: Methodology and User Guide* (Nardo, M., Saisana, M., Saltelli, A., Tarantola, S., et al., OECD, 2008) is the standard reference and is directly on-point — it treats exactly this problem (how to validate a weighted composite of standardised indicators) and recommends uncertainty + sensitivity analysis as mandatory. **[verify]** exact year/edition (2005 working version vs 2008 OECD publication).

## 3.6 Bootstrap stability — especially for the derived-position inheritance and the small-n weights

**What it tests.** Every weight and baseline in this model comes from a *small* single-team sample, and the derived positions (1.8) come from multiplying those small-sample weights. Bootstrap asks: **how much would the weights (and therefore the ratings) change if you'd observed a slightly different sample of the same matches?** This is the direct test of the recurring Part 1 worry that things like "ST assists (0.187) > goals (0.181)" (1.7.1) are sampling noise.

**How to run it.** Resample player-games with replacement (B = 1000), re-run the *entire* calibration pipeline (possession adjust → smooth → PCA → correct → normalise) on each resample, and collect the bootstrap distribution of every weight. Then:
- **Weight confidence intervals.** I'd expect the ST goals/assists CIs to overlap heavily — which would *prove* the assists>goals ordering is noise (1.7.1) and that it shouldn't be reported as a finding. Any weight whose 95% CI spans an order of magnitude is not a real estimate.
- **Derived-position propagation.** Because WB = RB × multipliers, bootstrap the RB weights and propagate through the multipliers to get WB rating CIs. Given the renorm bug (1.8.1) and the noise-amplification concern (1.8.3, ×8 on a 0.0026 base), I'd expect wide WB/WM rating CIs — quantifying exactly how unreliable the zero-data positions are. This is the number to put in the whitepaper next to every derived-position rating: an honest uncertainty band.
- **Rating-level bootstrap CIs.** Propagate weight uncertainty all the way to final ratings to attach a ± to each rating. A model that says "7.2 ± 0.15" is honest; one that says "7.2" while the true CI is ±0.6 is overconfident.

**Specific must-do:** bootstrap the MCD-PCA step itself. With `support_fraction=0.98` and ~30–50 rows (1.6.3), the eigenvectors are likely unstable across resamples — if PC1's loadings flip sign or reorder across bootstraps, the "PCA-derived weights" are noise and the philosophy prior is (correctly) carrying the model. That result would settle the 1.6 debate definitively.

*Citations:* Efron, B. & Tibshirani, R.J. (1993), *An Introduction to the Bootstrap*, Chapman & Hall — the foundational text. For bootstrap stability of PCA loadings specifically, Jolliffe, I.T. (2002), *Principal Component Analysis* (2nd ed.), Springer, Ch. 10 (sample variation / stability of PCs). For the MCD robust covariance whose stability you're testing, Rousseeuw, P.J. & Van Driessen, K. (1999), "A Fast Algorithm for the Minimum Covariance Determinant Estimator", *Technometrics* 41(3):212–223.

## 3.7 Construct validity and the composite-index / psychometrics lens

**What it tests.** Stepping back from agreement and stability: **is the single number measuring the construct it claims to ("match performance")?** This is a *validity* question (am I measuring the right thing) distinct from *reliability* (am I measuring it consistently). Psychometrics and the composite-indicator literature have a mature framework for exactly this problem — collapsing many standardised indicators into one defensible scalar — and it maps cleanly onto a player rating.

**How to apply it to this model.**
- **Content validity:** do the 17 features + bonuses cover the construct without major gaps? The obvious gap (Part 2) is progression/threat — the `xt_bonus` is the only coverage and it's weak. Content validity would flag that the "creation/build-up" facet of performance is under-represented relative to "end product".
- **Convergent validity:** does the rating correlate with things it *should*? The honest answer for now is **untested for the rating-vs-rating case** (no external rating exists). But two convergent checks need no external rater: (i) within-match, do ratings correlate sensibly with the obvious positives (goals, assists) and negatives (possession lost, conceding)? and (ii) **predictive convergence** — does *team-average* rating track the *match result* (a real external signal that is in the data and is not itself a rating)? A model whose team-average rating doesn't separate wins from losses has a validity problem; one that does has earned a genuine, target-free piece of convergent evidence. This is the most valuable validity check currently runnable and should be elevated.
- **Internal consistency:** in classical test theory you'd ask whether the features cohere. But a player rating is a **formative** index, not a **reflective** one — the features *cause* the rating, they aren't interchangeable indicators of a latent trait. This matters: **Cronbach's α and McDonald's ω are the *wrong* tools here** and you should *not* report them, because they assume reflective measurement (high inter-item correlation = good), whereas for a formative performance index you *want* the indicators to be somewhat independent (goals and tackles shouldn't correlate). This is a subtle but important point the whitepaper should get right — it's a common error to slap Cronbach's α on a composite index. Cite the formative-vs-reflective distinction explicitly and explain why you're *not* using internal-consistency coefficients.
- **Known-groups / discriminant validity:** does the model separate groups it should (rate goalscorers above anonymous cameos, dominant defenders above sieved ones)? The stress tests are informal known-groups checks (Masterclass ST 9.8 ≫ Nightmare CB 4.1) and they pass. Formalise with a held-out set of "obviously good" vs "obviously bad" games and confirm separation.

**The composite-index discipline to import:** the OECD/JRC Handbook's ten-step process (theoretical framework → indicator selection → normalisation → weighting → aggregation → uncertainty/sensitivity → back-to-the-data → links to other measures → visualisation → dissemination). Steps 6–8 (uncertainty/sensitivity, robustness, and *de-construction* — checking which indicators drive the index) are exactly 3.5/3.6 above, and the Handbook's insistence that **weighting and aggregation choices must be made explicit and tested** is the formal version of Part 1's "the philosophy dict is the real model, say so".

*Citations:* Messick, S. (1995), "Validity of psychological assessment: Validation of inferences from persons' responses and performances as scientific inquiry into score meaning", *American Psychologist* 50(9):741–749 — the unified validity framework (content/convergent/discriminant as facets of construct validity). Cronbach, L.J. (1951), "Coefficient alpha and the internal structure of tests", *Psychometrika* 16:297–334, and McDonald, R.P. (1999), *Test Theory: A Unified Treatment*, Erlbaum (coefficient ω) — cited here specifically as the tools you should **not** apply, with the formative/reflective distinction from Bollen, K.A. & Lennox, R. (1991), "Conventional wisdom on measurement: A structural equation perspective", *Psychological Bulletin* 110(2):305–314 **[verify exact pages]**. Composite indices: Nardo et al. / OECD-JRC (2008), *Handbook on Constructing Composite Indicators*, OECD Publishing.

## 3.8 Football-specific rating-validation precedents (what the academic literature actually does)

**What it tests / why it's here.** You don't have to invent the evaluation protocol — there's a small academic literature on *exactly* this (turning football events into a single player rating) and it establishes the conventional validation moves, which are worth mirroring so the whitepaper sits in a recognised tradition.

- **EA SPORTS Player Performance Index** (McHale, I.G., Scarf, P.A., Folker, D.E., 2012, "On the Development of a Soccer Player Performance Rating System for the English Premier League", *Interfaces* 42(4):339–351). This is the closest published analogue to what Gaffer's Clipboard does — a weighted index built from match statistics, explicitly designed to be interpretable, validated partly by **face validity** (do the top-rated players match consensus) and **predictive checks** (does the index predict future team success / match outcomes). Mirror their validation: check that your season-aggregated ratings rank players sensibly and that team-average rating tracks results. This is a strong precedent to cite because it legitimises the *weighted-composite-from-box-score* approach against the "you must use VAEP" critique.
- **VAEP** (Decroos, T., Bransen, L., Van Haaren, J., Davis, J., 2019, "Actions Speak Louder than Goals: Valuing Player Actions in Soccer", *KDD '19*) — cite as the paradigm you're *not* using (Part 2.3). If you ever obtain VAEP/OBV-style ratings for comparable players, correlating against them would be a *convergent-validity* check — but note this would need an external dataset you don't have. Also Decroos & Davis's comparison work on xT vs VAEP (the `xt_vs_vaep` report referenced in your own research doc) for honestly situating your proxy.
- **PlayeRank** (Pappalardo, L., Cintia, P., Ferragina, P., Massucco, E., Pedreschi, D., Giannotti, F., 2019, "PlayeRank: Data-driven Performance Evaluation and Player Ranking in Soccer", *ACM Transactions on Intelligent Systems and Technology* 10(5)) — validates a role-aware rating largely through **ranking quality** and **expert agreement**; their role-clustering is a more data-driven cousin of your positional weighting and a good reference for the "evaluate by ranking, not by absolute value" stance (which is the right framing for 3.2 once you have a reference to rank against).
- **Expected Threat** (Singh, K., 2018/2019, "Introducing Expected Threat (xT)", karun.in blog) — the actual definition of xT, cited so the whitepaper can explicitly state how its `xt_bonus` differs (Part 2.3). This is a blog, not peer-reviewed, but it is *the* canonical xT reference and is cited as such throughout the literature.
- **[verify]** I believe there is work by **Robberechts & Davis** on the *reliability/calibration* of soccer ratings and probabilities (e.g. around well-calibrated match outcome and rating models), which would be directly relevant to 3.4/3.7, but I'm not certain of the exact title/venue — flag and check before citing. Similarly, **Brefeld, Lasek, or Van Roy/Decroos** have follow-on action-valuation papers worth a literature scan, but cite specific titles only after verification.

**How to use this section:** the literature converges on two headline validation moves — **(1) ranking quality against an independent reference** and **(2) face/known-groups validity**. For Gaffer's Clipboard *today*, only (2) is runnable (3.7), supported by **predictive validity against match outcomes** (the one external-criterion check available without a rating target) and the internal stability/sensitivity machinery (3.4–3.6). Move (1) — and the GLMM-agreement and Bland–Altman analyses (3.2/3.3) — become available only once you **acquire an independent reference** (3.0). The whitepaper should present the validation story in exactly that order: "here is the internal, known-groups, and predictive evidence we can produce now; here is the external-agreement evidence we will produce once a reference dataset is built, and why the previous-version ratings cannot serve as that reference." McHale et al. and Pappalardo et al. leaned heavily on face validity and expert/consensus references precisely because, like you, they had no ground truth — that is the tradition to sit in.

## 3.9 Recommended validation sequence (practical ordering)

For the whitepaper, run and report in this order. The split is deliberate: the first block needs **no external reference** and is runnable today; the second block is **blocked until you build one** (3.0).

**Runnable now (no external target):**
1. **Known-groups / face validity** (3.7) — formalise the designed stress tests into a held-out battery of "obviously good" vs "obviously bad" games and confirm separation. *Cheapest, and the most honest current evidence that the model means something.*
2. **Output-distribution diagnostics** (3.3, alternative form) — plot rating vs minutes, rating vs supremacy deduction, and the overall histogram. *Establishes the central-compression behaviour directly from the model's own outputs.*
3. **Half-length and perturbation ICC** (3.4) — formalise the stress-test stability you already see, and specifically test half-length invariance (a user setting must not move ratings). *Confirms reliability.*
4. **Predictive validity vs match outcomes** (3.7/3.8) — does team-average rating separate wins from losses/draws? *The one external-criterion check available now.*
5. **Sensitivity sweep on the hand-set parameters** (3.5), led by the impact-scalar floor → rating-vs-minutes test. *Proves the Part 1 compression diagnosis and finds the levers.*
6. **Bootstrap the calibration pipeline** (3.6), especially PCA-loading stability and derived-position propagation. *Settles the prior-vs-PCA question and attaches honest CIs to derived positions.*
7. **GLMM variance partition on the model's own ratings** (3.1) — once you have ≥ 30 matches; compare the model's context-ICC to the commercial ≈ 0.26. *Tests whether the supremacy scalar is over- or under-contextualising.*

**Blocked until an external reference exists (3.0):**
8. **Per-match Spearman/Kendall** against the reference (3.2) — *confirms ordering against something other than yourself.*
9. **Bland–Altman agreement** against the reference (3.3) — *localises scale-dependent disagreement.*

The previous-version `match_rating`/`Expected` values may be used **only** as a release-time **regression test** (did a code change reorder players or shift the distribution?), never folded into steps 8–9 or any accuracy claim.

The thread tying Part 3 back to Part 1: the model's *internal* behaviour is already legible — the designed stress tests behave as intended (known-groups separation looks right), and its central compression (cameos → ~5.6, dominant-team performances → a near-constant deduction) is visible directly in its own outputs and traceable to the impact scalar (1.10) and supremacy scalar (1.12). What is **not** yet established is *accuracy*, because there is no external reference and the prior-version ratings cannot supply one. Validation now is therefore about (i) proving the compression diagnosis rigorously from the model's own outputs, (ii) attaching honest uncertainty to the prior-dominated weights and zero-data positions, (iii) disciplining the free parameters Part 1 shows are doing the real work, and (iv) building the reference dataset that everything else is waiting on.

---

*End of review. This document is a companion to the Quantitative Design whitepaper; where the two disagree, the live `match_ratings_service.py` is treated as ground truth and the discrepancy is flagged in the relevant section above. The `match_rating`/`Expected` fields in the data and notebook are outputs of a previous version of this algorithm and are deliberately excluded from all analysis here.*
