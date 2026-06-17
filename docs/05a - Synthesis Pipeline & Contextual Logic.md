### Phase I: Pre-Synthesis Matrix Bounding
Before the engine calculates the baseline match rating, it must conditionally bound the raw Z-score input vector to prevent isolated data points from collapsing the linear algebra.

The engine iterates through the 17-element telemetry array and applies minimum thresholds depending on the player's position:

- **Efficiency Safeguards:** Percentage-based metrics — pass accuracy, shot accuracy, dribble success rate, and tackle success rate — are regulated by the continuous logistic volume masking system applied during Z-score standardisation (Section III). By the time the dot product runs, these Z-scores already carry a confidence weight proportional to the player's attempt volume; a player with near-zero attempts contributes almost nothing to the dot product through their efficiency score regardless of how extreme that score might be on a raw basis. Any position-specific hard floors on individual efficiency metrics are documented in Appendix A.
- **Tactical Instruction Floors:** To protect players from being penalised for following managerial orders, the engine applies contextual forgiveness by role. A Fullback instructed to stay back will naturally log low dribbling volume and low xT — the engine intercepts these specific metrics and floors them at a modest penalty ($-0.50$), ensuring a defensive fullback is not mathematically destroyed for ignoring the final third. Similar absolution is applied to attacking positions for below-average defensive metrics, and to defensive positions for below-average attacking metrics.

### Phase II: Base Synthesis (The Dot Product)
With the input vector safely bounded, the raw foundation of the match rating is calculated using the dot product of the modified Z-scores and the Positional Weight Vector:

$$S_{raw} = \sum_{i=1}^{17} \left( Z_i \times W_i \right)$$

```python
# Fast, vectorized linear combination of the 17 core metrics
return np.dot(
    np.array([z_scores.get(f"{col}_z", 0) for col in col_names]),
    weights,
)
```

### Phase III: Post-Synthesis Contextual Heuristics
Following the dot product, the engine applies non-linear modifiers to $S_{raw}$ to account for complex match context, output rewards, and dynamic player archetypes.

#### Tactical Build-Up Isolation
Before goal and assist bonuses are applied, the engine evaluates whether the player was genuinely involved in the match's build-up phase. It averages the Z-scores across six build-up metrics — passes, pass accuracy, dribbles, dribble success rate, distance covered, and distance sprinted — to form a composite build-up score $z_{build}$.

If $z_{build} < -1.0$, the player's build-up contribution is classified as statistically absent. Rather than a binary cut-off, the engine calculates an exponential decay multiplier:
$$\text{isolation\_multiplier} = \begin{cases} e^{z_{\text{build}}+1.0} & \text{if } z_{\text{build}} < -1.0 \\ 1.0 & \text{otherwise} \end{cases}$$
This multiplier is applied to all goal and assist bonuses in the subsequent step. A player at $z_{build} = -1.5$ receives a multiplier of $e^{-0.5} \approx 0.61$, reducing their bonuses to 61% of face value. A player at $z_{build} = -2.5$ receives $e^{-1.5} \approx 0.22$, effectively stripping most of the bonus for a player who was almost entirely absent from the game. The multiplier only decays when build-up involvement is meaningfully negative — a mildly quiet game at $z_{build} = -0.9$ leaves the full bonus intact.

#### Bottleneck Synergy Bonuses
Rather than forcing players into a single rigid positional mould, the engine dynamically rewards distinct archetypes within the same position based on statistical output. These bonuses activate and scale continuously rather than applying a flat reward at a binary threshold.

The core mechanic is **bottleneck synergy**: a bonus only activates when a player simultaneously exceeds a threshold across two related metrics, and the bonus rate is driven by the weaker of the two. This prevents one extraordinary stat from generating a bonus while masking a deficiency in the paired metric. For example:

- **Fullback "Third CB" Archetype:** Activates when both `tackles_z` and `possession_won_z` exceed 1.0. The bonus scales with $\min(tackles\_z, poss\_won\_z) - 1.0$.
- **Fullback "Express Train" Archetype:** Activates when both `distance_sprinted_z` and `xt_bonus_z` exceed 1.0. The bonus scales with $\min(sprint\_z, xt\_z) - 1.0.$.

Analogous bottleneck bonuses exist for every outfield position — a CDM "Destroyer" archetype gated on tackles and possession won, a CM "Progression Engine" gated on passes and dribbles, a CAM "Maestro" gated on passes and xT, and so on — each reflecting the paired tactical requirements of the role.

#### Absolute Output Multipliers

Goal contributions are applied as efficiency-adjusted bonuses, modulated by the isolation multiplier calculated above. Rather than a flat reward per goal, the engine calculates an _above-expected_ component: the number of goals minus a crude estimated xG based on shot volume (0.20 xG per shot). A floor of 40% of the position-specific coefficient per goal ensures scoring always contributes positively, even for a high-volume shooter:
$$\text{above\_expected} = \max(\text{goals} - \text{shots} \times 0.20, \text{goals} \times 0.40)$$

$$\text{event\_bonus} = (\text{above\_expected} \times G_{pos} + \text{assists} \times A_{pos}) \times \text{isolation\_multiplier}$$
Where $G_{pos}$ and $A_{pos}$ are the position-specific goal and assist coefficients. These vary by role — a Striker's goal carries a coefficient of 1.5, a Centre Back's 0.75, and a CDM's 0.6 — reflecting how central scoring is to each position's mandate. The complete per-position values are in Appendix A.

This `event_bonus` is computed here but held separately from $S_{raw}$; it is not folded into the base score until after the impact scalar in Phase IV.

#### Contextual Performance Gates

The engine applies additional macro-contextual rewards and penalties specific to each position. Examples across the pipeline:

- **Dynamic Clean Sheet Bonus (Defenders):** Scaled by opponent xG. A clean sheet against ${\leq}1.0$ xG yields a maximum $+0.50$ reward, reflecting genuine defensive dominance. Against ${\geq}2.0$ xG it yields a minimal $+0.15$, acknowledging the result may owe as much to poor opponent finishing or exceptional goalkeeping as to outfield defending.
- **Collapse Penalty (Defenders):** A flat $-0.30$ is applied if the team concedes three or more goals and the player was on the pitch for at least 60 minutes.
- **Wasteful Finisher Penalty (Striker):** Assigns 0.20 xG per shot. If a striker takes more than 3 shots and generates a finishing deficit above 0.75, a scaling penalty capped at $-0.80$ is applied.
- **Reliable Pivot Bonus (CDM):** If 60+ minutes are played with pass accuracy $\geq 92\%$ and elite passing volume, a tiered bonus rewards near-perfect ball retention: $+0.35$ for zero possession lost ("Perfect Metronome"), $+0.20$ for at most one loss ("Reliable Shift").
- **Clean Sheet Bonus (Midfielders):** Central and defensive midfielders who complete 60+ minutes with zero goals conceded receive a flat $+0.15$, reflecting their role in screening the defensive line.

### Phase IV: Impact Scaling

After all positional modifiers and heuristics have been applied to the base score, the engine scales it and combines it with the goal contribution to form the final pre-sigmoid input:
$$S_{final} = S_{raw} \times \sqrt{\frac{\min(M, 90)}{90}} + \text{event\_bonus}$$
Where $S_{raw}$ is the accumulated dot-product score including all archetype bonuses, contextual heuristics, and positional penalties from Phase III, and $\text{event\_bonus}$ is the goal and assist contribution computed in Phase III. Only $S_{raw}$ passes through the scaling step; the event bonus is added unscaled afterwards.

This separation is a deliberate design decision. Compressing a goal bonus by the fraction of the match a substitute played would undervalue an absolute, match-defining contribution — a player who comes on and scores should receive the full credit for that goal. The impact scalar instead compresses the base statistical performance toward zero, correctly reflecting that a brief appearance does not provide sufficient evidence to award the same base rating as a full-match performance, while leaving the factual output intact.

Where $M$ is the player's actual minutes played. A full 90-minute match yields a multiplier of exactly 1.0 and $S_{raw}$ passes through unchanged. A player with 45 minutes receives $\approx 0.71$; a player with 22 minutes receives $\approx 0.49$.

The rationale is distinct from Bayesian smoothing. Smoothing (Section II) constrains the per-90 rates fed into the Z-score calculation — it operates at the input stage and affects how each individual metric is evaluated. The impact scalar operates at the output stage, compressing the entire synthesised base score toward zero regardless of which individual metrics drove it. A 22-minute substitute who generated a strong $+2.0$ base score has it compressed to roughly $+0.99$ before the event bonus is added and the sigmoid runs, producing a final rating comfortably above average but well short of what a full-match performer with the same statistical intensity would earn.