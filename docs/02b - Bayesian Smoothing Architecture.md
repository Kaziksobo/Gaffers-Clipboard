### 1. The Mathematical Hazard of Small Samples
As outlined in the theoretical methodology, extrapolating small-sample simulation data (such as 1 shot in 2 minutes) into a "per 90" rate relies on a linear assumption that fundamentally breaks at such extremes. The danger of this is not just the inflated number itself, but how it interacts with downstream calculations. When an unanchored, mathematically absurd extrapolation — such as 45.0 shots per 90 — enters a standard deviation (Z-score) matrix, it registers as a multi-sigma outlier. This artificially warps the player's dimensional weight and completely bypasses positional constraints, mathematically guaranteeing a maximum match rating of 10.0 for a brief cameo with very little impact on the actual game.

### 2. The Metric-Calibrated Shrinkage Anchor
To resolve this, the engine utilises Bayesian smoothing: a statistical shrinkage technique that pulls low-confidence observations (those with small sample sizes) toward a high-confidence prior (historical averages).

The conceptual blending formula is as follows:

$$r_{smoothed} = \frac{M}{M + d} \cdot r_{obs} + \frac{d}{M + d} \cdot r_{prior}$$

- **$M$:** Minutes actually played.
- **$r_{obs}$:** The observed statistical rate.
- **$d$ (Dummy Anchor):** A metric-specific constant representing the weight of historical expectation, calibrated to each metric's stabilisation rate (see three-tier system below).
- **$r_{prior}$:** The historical expected rate for that specific position.

The constant $d$ dictates the critical "pivot point" — the exact minute mark where the weight of a player's live observed performance equals the weight of the historical expectation. Rather than applying a single universal anchor to every stat, the engine assigns $d$ based on how quickly each metric's true rate stabilises. This produces three tiers:

- **High-Frequency Metrics ($d = 15.0$)**
  *Passes, distance covered, distance sprinted, possession won, possession lost.*
  These statistics accumulate continuously. After 15 minutes of football, a player has interacted with the ball and covered ground often enough that their observed rate is already a reasonable estimate. The pivot point falls at exactly 15 minutes — equal weight to live data and prior from the first quarter-hour. A full 90-minute match yields a live-data weight of $\frac{90}{90+15} \approx 85.7\%$, making the prior a marginal residual for complete matches.

- **Medium-Frequency Metrics ($d = 30.0$)**
  *Dribbles, tackles, fouls committed, offsides.*
  These occur regularly but not continuously. A 10-minute cameo may contain only one or two tackles, offering little statistical confidence. The pivot point falls at 30 minutes — the classic "impact sub" window, considered the minimum for meaningful tactical integration. A full match yields a live-data weight of $\frac{90}{90+30} = 75\%$.

- **Rare Events ($d = 45.0$)**
  *Goals, assists, shots.*
  These are discrete, high-stakes events that remain genuinely volatile even over a full match. A striker who scores twice in the first 10 minutes of their cameo should not be projected as an 18-goals-per-game phenomenon. The pivot point falls at 45 minutes, so only players who have seen substantial game time begin to earn real trust in their goal-threat rate. A full match still retains $\frac{90}{90+45} \approx 66.7\%$ live-data weight, acknowledging that even complete matches carry meaningful match-to-match variance for these events.

### 3. The Logic of Priors ($r_{prior}$)
For Bayesian smoothing to function logically, the algorithm cannot use a blanket prior for all statistics. The engine bifurcates the prior based on the fundamental nature of the telemetry being evaluated.

**Rare, Discrete Events ($r_{prior} = 0.0$)**
Metrics such as goals, assists, and shots represent highly valuable, discrete, and inherently rare events. For these `rare_cols`, the prior must be strictly set to $0.0$. If the algorithm used a historical average — for example, if a striker historically averages $0.6$ goals per game — the blending formula would falsely inject fractional "ambient" goals into a substitute's baseline rate simply for stepping onto the pitch. In a mathematically rigorous engine, decisive match-altering actions cannot be assumed; they must be earned entirely from scratch through live telemetry.

**Continuous, Volume Events ($r_{prior} = \mu_{historical}$)**
Conversely, cumulative metrics such as passes, tackles, and distance covered represent continuous tactical execution. Even when a player is not actively on the ball, they are occupying space, pressing, and moving within a system. For these `volume_cols`, the prior dynamically queries the offline `means_stds` dictionary to fetch the exact historical mean ($\mu$) for the active positional role.

Using a $0.0$ prior for these continuous events would incorrectly assume an 80th-minute defensive midfielder actively refused to pass or tackle, artificially dragging their efficiency scores toward zero. By anchoring volume metrics to the historical positional mean, the engine gives the player the "tactical benefit of the doubt" — assuming they are fulfilling the baseline responsibilities of their role at an average rate, until their live telemetry proves they are over- or under-performing.

### 4. Algorithmic Implementation (`_apply_bayesian_smoothing`)
Within the `MatchRatingsService`, this mathematical foundation is executed with a focus on application stability, efficient memory allocation, and defensive programming. The engine relies entirely on native Python dictionaries, avoiding heavy data-science libraries.

The anchor values are stored as a class-level immutable constant, mapping each metric to its calibrated tier:

```python
DUMMY_WEIGHTS: Final = MappingProxyType(
    {
        # High-Frequency (Fast stabilization)
        "passes": 15.0,
        "distance_covered": 15.0,
        "distance_sprinted": 15.0,
        "possession_won": 15.0,
        "possession_lost": 15.0,
        # Medium-Frequency (Moderate stabilization)
        "dribbles": 30.0,
        "tackles": 30.0,
        "fouls_committed": 30.0,
        "offsides": 30.0,
        # Low-Frequency / Rare Events (Slow stabilization, high volatility)
        "goals": 45.0,
        "assists": 45.0,
        "shots": 45.0,
    }
)
```

The engine receives a dictionary of `normalized_metrics` (stats already adjusted for half-length) and routes them through a bifurcated pipeline.

#### The Rare Events Matrix
For discrete events (`rare_cols`: goals, assists, shots), the prior is $0.0$ and the anchor is $d = 45.0$. Because the prior is zero, the right side of the blending formula is neutralised entirely. The engine evaluates these using a rapid dictionary comprehension, fetching $d$ from `DUMMY_WEIGHTS`:

$$X_{p90} = \left( \frac{X}{M + d} \right) \times 90.0$$

The heavy $d = 45.0$ anchor suppresses extreme extrapolations from short appearances without requiring any positional database queries.

#### The Volume Matrix and Log-Mean Back-Conversion
For continuous tactical events (`volume_cols`: passes, tackles, distance, etc.), the engine fetches the historical mean ($\mu$) for the player's position and applies the appropriate per-metric $d$:

```python
d = self.DUMMY_WEIGHTS.get(col, self.DEFAULT_DUMMY)

col_stats = self.means_stds.get(pos, {}).get(
    f"{col}_p90",
    {"mean": 0.0, "std": 1.0}
)
league_average_p90: float = col_stats.get("mean", 0.0)
```

A critical detail applies to four volume statistics: `possession_won`, `possession_lost`, `fouls_committed`, and `offsides`. These are log-transformed before their means are computed in the offline calibration notebooks (as part of the log-normalisation pipeline described in Section III). This means the value stored in `means_stds` for these columns is $\mu\bigl(\ln(x+1)\bigr)$ — a mean in log-space — rather than a raw per-90 rate. Before it can serve as a Bayesian prior, it must be back-converted to the original statistical space:

```python
if col in {"possession_won", "possession_lost", "fouls_committed", "offsides"}:
    league_average_p90 = float(np.expm1(league_average_p90))
```

`np.expm1(x)` computes $e^x - 1$, exactly reversing the $\ln(x + 1)$ transformation. Without this step, the prior would systematically underestimate these rates, dragging smoothed values toward an artificially compressed baseline.

Once the prior is correctly retrieved, the `dummy_stat` is computed — the literal anchor weight dropped onto the scales:

$$\text{dummy\_stat} = r_{prior} \times \left(\frac{d}{90}\right)$$

$$X_{p90} = \left[ \frac{X + \text{dummy\_stat}}{M + d} \right] \times 90$$

#### Absolute Stability and Divide-by-Zero Safety
By executing the algebraically reduced formula above, the engine never divides by $M$. Because the denominator is strictly $(M + d)$ and every $d$ is at least $15.0$, the denominator can never equal zero — regardless of telemetry edge cases such as a player logged with 0 minutes played.

> [!example]- Mathematical Proof: Equivalence of the Reduced Formula
> To prove that the optimised Python implementation mathematically matches the conceptual Bayesian formula, we map the variables as follows: $X$ = raw volume, $M$ = minutes played, $d$ = metric-specific anchor (15.0, 30.0, or 45.0).
>
> **Step 1: The Conceptual Formula**
> $$r_{smoothed} = \left(\frac{M}{M + d}\right) r_{obs} + \left(\frac{d}{M + d}\right) r_{prior}$$
>
> **Step 2: Substitute $r_{obs}$ for its raw mathematical components**
>
> The observed per-90 rate ($r_{obs}$) is calculated as $\frac{X}{M} \times 90$. Substituting this in:
> $$r_{smoothed} = \left(\frac{M}{M + d}\right) \left(\frac{X}{M} \times 90\right) + \left(\frac{d}{M + d}\right) r_{prior}$$
>
> **Step 3: Cross-Cancel and Align Denominators**
>
> In the first term, the $M$ in the numerator and the $M$ in the denominator cancel each other out:
> $$r_{smoothed} = \frac{X \times 90}{M + d} + \frac{d \times r_{prior}}{M + d}$$
>
> Because both terms share the same denominator $(M + d)$, they combine into a single fraction:
> $$r_{smoothed} = \frac{90X + d \cdot r_{prior}}{M + d}$$
>
> **Step 4: Align with the Python Implementation**
>
> The Python code structures the formula to multiply by $90$ at the very end to format the output as a per-90 rate:
> $$X_{p90} = \left[ \frac{X + r_{prior} \times \left(\frac{d}{90}\right)}{M + d} \right] \times 90$$
>
> Distributing the $\times 90$ into the numerator:
> $$X_{p90} = \frac{90X + \left(r_{prior} \times \frac{d}{90} \times 90\right)}{M + d}$$
>
> The $90$ and $\div 90$ on the right side of the numerator cancel, leaving:
> $$X_{p90} = \frac{90X + d \cdot r_{prior}}{M + d}$$
>
> **Conclusion:** The formulas are algebraically identical. The proof holds regardless of whether $d$ is 15.0, 30.0, or 45.0 — the reduced formula is a universal representation of the conceptual Bayesian blend for any metric-specific anchor value. The $X_{p90}$ reduction safely calculates the exact same shrinkage rate without ever dividing by $M$.