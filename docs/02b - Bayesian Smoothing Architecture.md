### 1. The Mathematical Hazard of Small Samples
As outlined in the theoretical methodology, extrapolating small-sample simulation data (such as 1 shot in 2 minutes) into a "per 90" rate relies on a linear assumption that fundamentally breaks at such extremes. The danger of this is not just the inflated number itself, but how it interacts with downstream calculations. When an unanchored, mathematically absurd extrapolation - such as 45.0 shots per 90 - enters a standard deviation (Z-score) matrix, it registers as a multi-sigma outlier. This artificially warps the player's dimensional weight and completely bypasses positional constraints, mathematically guaranteeing a maximum match rating of 10.0 for a brief cameo with very little impact on the actual game.

### 2. The Shrinkage Anchor 
To resolve this, the engine utilises Bayesian smoothing. In this context, it operates as a statistical shrinkage technique that pulls low-confidence observations (those with small sample sizes) toward a high-confidence prior (historical averages).

The conceptual blending formula is as follows:
$$
r_{smoothed} = \frac{M}{M + d} r_{obs} + \frac{d}{M+d} r_{prior}
$$

* **$M$:** Minutes actually played.
* **$r_{obs}$:** The observed statistical rate.
* **$d$ (Dummy Anchor):** A constant representing the weight of historical expectation ($d=30.0$).
* **$r_{prior}$:** The historical expected rate for that specific position.

The constant $d$ dictates the critical "pivot point" of the algorithm - the exact minute mark where the mathematical weight of a player's live observed performance ($M$) equals the weight of the historical expectation ($d$). During development, this constant was rigorously calibrated against alternative thresholds to find the optimal balance between variance protection and statistical freedom.

* **The Reactive Trap ($d = 20.0$):** 
	If the anchor is set too low, the engine releases its grip on the prior too quickly. At $d=20$, a player substituted on in the 70th minute reaches the 50/50 pivot point by the final whistle. This allows late-game variance to dictate their rating heavily. A single lucky bounce or a brief five-minute spell of dominance would mathematically outweigh the anchor, resulting in wildly inflated ratings for players who barely influenced the match's overarching narrative.
* **The Suffocation Trap ($d = 45.0$):** 
	Conversely, setting the anchor too high mathematically suffocates legitimate performances. At $d=45$, the 50/50 pivot point is not reached until a player completes a full half of football. If a manager brings on a substitute at half-time, and that player delivers 45 minutes of elite tactical execution, a $d=45$ anchor would brutally drag their rating back toward a baseline 6.0, refusing to reward a genuinely match-altering performance.
* **The Impact Sub Equilibrium ($d = 30.0$):** 
	Setting $d=30.0$ establishes a perfect mathematical equilibrium. In football analytics, 30 minutes represents the classic "impact sub" window (a 60th-minute substitution) and is widely considered the minimum threshold required to gauge tactical integration. By hardcoding $d=30.0$, the algorithm enforces a highly accurate sliding scale of trust: 
	* **The Cameo ($M=5$):** The anchor holds firm, heavily trusting the historical prior ($\sim 86\%$) to prevent extreme variance from a few isolated touches. 
	* **The Equilibrium ($M=30$):** The live data and the historical prior carry an exact $50/50$ weight, demanding that an impact sub sustains their performance to earn an elite rating. 
	* **The Full Match ($M=90$):** The player fully overpowers the anchor, with the algorithm trusting their live observed data ($75\%$) while retaining a minor $25\%$ shrinkage to account for standard match-to-match simulation variance.

### 3. The Logic of Priors ($r_{prior}$)
For Bayesian smoothing to function logically, the algorithm cannot use a blanket prior for all statistics. The engine must bifurcate the prior ($r_{prior}$) based on the fundamental nature of the telemetry being evaluated. 

**Rare, Discrete Events ($r_{prior} = 0.0$)** 
Metrics such as goals, assists, and shots represent highly valuable, discrete, and inherently rare events. For these  `rare_cols`, the prior must be strictly set to $0.0$. If the algorithm used a historical average - for example, if a striker historically averages $0.6$ goals per game - the blending formula would falsely inject "ambient" fractional goals into a substitute's baseline rate simply for stepping onto the pitch. In a mathematically rigorous engine, decisive match-altering actions cannot be assumed; they must be earned entirely from scratch through live telemetry.

**Continuous, Volume Events ($r_{prior} = \mu_{historical}$)** 
Conversely, cumulative metrics such as passes, tackles, and distance covered represent continuous tactical execution. Even when a player is not actively on the ball, they are occupying space, pressing, and moving within a system. For these `volume_cols`, the prior dynamically queries the offline `means_stds` dictionary to fetch the exact historical mean ($\mu$) for the active positional role. 

If we used a $0.0$ prior for these continuous events, the algorithm would incorrectly assume an 80th-minute defensive midfielder actively refused to pass or tackle, artificially dragging their efficiency scores toward zero. By anchoring volume metrics to the historical positional mean, the engine gives the player the "tactical benefit of the doubt"—assuming they are fulfilling the baseline responsibilities of their role at an average rate, until their active telemetry proves they are over- or under-performing.

### 4. Algorithmic Implementation (`_apply_bayesian_smoothing`)
Within the `MatchRatingsService`, this mathematical foundation is executed with a strict focus on application stability, efficient memory allocation, and defensive programming. Because this engine is designed to run locally on a user's desktop without heavy data-science libraries like `pandas`, the implementation relies entirely on highly optimized native Python dictionaries. Working through the algorithm, the engine receives a dictionary of `normalized_metrics` (stats already adjusted for half-length) and routes them through a bifurcated processing pipeline.

#### The Rare Events Matrix (Dictionary Comprehension)
For discrete match-altering events (`rare_cols` such as goals, assists, and shots), the prior is mathematically mandated to be $0.0$. Because the prior is zero, the entire right side of the conceptual blending formula is neutralized. 

To maximize runtime efficiency, the engine evaluates these metrics using a rapid dictionary comprehension. The algebraic reduction is simplified even further, requiring no database queries:

$$
X_{p90} = \left( \frac{X}{M + d} \right) \times 90.0
$$

This elegantly applies the heavy shrinkage anchor to low-minute players without the computational overhead of querying positional averages.

#### The Volume Matrix and Safe Dictionary Traversals
For continuous tactical events (`volume_cols` such as passes, tackles, and distance covered), the engine must fetch the exact historical mean ($\mu$) for the player's specific tactical role. 

In a live application environment, querying external datasets is a common point of failure (e.g., a newly introduced tactical role might be missing from the database). To guarantee uninterrupted execution, the engine utilizes a defensive, nested `.get()` traversal of the offline `means_stds` dictionary:

```python
col_stats = self.means_stds.get(pos, {}).get(
	f"{col}_p90", 
	{"mean": 0.0, "std": 1.0}
)
league_average_p90: float = col_stats.get("mean", 0.0)
```

This architecture ensures that if a position or metric is missing, the application defaults safely to a $0.0$ mean rather than throwing a `KeyError` and crashing the analysis.

Once the prior is safely retrieved, the algorithm computes the `dummy_stat`. This is the literal Python representation of $r_{prior} \times (d/90)$, calculating exactly how many actions a statistically average player _should_ have completed in 30 minutes. This fractional volume acts as the literal anchor weight dropped onto the scales before executing the final reduction.

#### Absolute Stability and Divide-by-Zero Safety

Executing the standard conceptual Bayesian formula requires the engine to first calculate the observed rate ($r_{obs}$) by dividing raw volume by actual minutes played ($X / M$).

However, calculating $X / M$ introduces a critical systemic hazard. If the EA FC telemetry glitches, or if a user accidentally logs a player with $0$ minutes played, executing $X / 0$ will immediately crash the application with a `ZeroDivisionError`.

By executing the algebraically reduced formula:

$$X_{p90} = \left[ \frac{X + \text{dummy\_stat}}{M + d} \right] \times 90$$

The engine never divides by $M$. Because the denominator is strictly $(M + d)$, and $d$ is hardcoded to $30.0$, the denominator can never equal zero. This mathematically identical reduction achieves two things simultaneously: it calculates highly stable, small-sample-proof metrics, and it structurally guarantees a crash-proof runtime function.

> [!example]- Mathematical Proof: Equivalence of the Reduced Formula
> To prove that the optimized Python implementation mathematically matches the conceptual Bayesian formula, we map the variables as follows: $X$ = raw volume, $M$ = minutes played, $d = 30.0$.
> 
> **Step 1: The Conceptual Formula**
> $$r_{smoothed} = \left(\frac{M}{M + d}\right) r_{obs} + \left(\frac{d}{M + d}\right) r_{prior}$$
> 
> **Step 2: Substitute $r_{obs}$ for its raw mathematical components**
> The observed per-90 rate ($r_{obs}$) is calculated as $(X / M) \times 90$. Substituting this in:
> $$r_{smoothed} = \left(\frac{M}{M + d}\right) \left(\frac{X}{M} \times 90\right) + \left(\frac{d}{M + d}\right) r_{prior}$$
> 
> **Step 3: Cross-Cancel and Align Denominators**
> In the first term, the $M$ in the numerator and the $M$ in the denominator cancel each other out:
> $$r_{smoothed} = \frac{X \times 90}{M + d} + \frac{d \times r_{prior}}{M + d}$$
> 
> Because both terms now share the exact same denominator ($M + d$), they can be combined into a single fraction:
> $$r_{smoothed} = \frac{90X + d \cdot r_{prior}}{M + d}$$
> 
> **Step 4: Align with the Python Implementation**
> The Python code structures the formula to multiply by $90$ at the very end to format the rate:
> $$X_{p90} = \left[ \frac{X + r_{prior} \times \left(\frac{d}{90}\right)}{M + d} \right] \times 90$$
> 
> Distributing the $\times 90$ into the numerator yields:
> $$X_{p90} = \frac{90X + \left(r_{prior} \times \frac{d}{90} \times 90\right)}{M + d}$$
> 
> The $90$ and $/ 90$ on the right side cancel out, leaving the final equation:
> $$X_{p90} = \frac{90X + d \cdot r_{prior}}{M + d}$$
> 
> **Conclusion:** The formulas are algebraically identical. The $X_{p90}$ reduction safely calculates the exact same shrinkage rate without ever dividing by $M$.