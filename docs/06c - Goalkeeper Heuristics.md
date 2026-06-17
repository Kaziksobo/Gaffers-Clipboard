### 1. Matrix Dimensionality Mismatch
Outfield ratings are computed as a 17-element linear combination (dot product) of standardised Z-scores, mapped against a $17 \times 9$ PCA weight matrix. Goalkeeper telemetry is fundamentally incompatible with this architecture, as the engine receives a structurally distinct 11-element array restricted entirely to reactive metrics (`shots_against`, `shots_on_target`, `saves`, `goals_conceded`, `save_success_rate`, `punch_saves`, `rush_saves`, `penalty_saves`, `penalty_goals_conceded`, `shoot_out_saves`, `shoot_out_goals_conceded`).

To resolve this dimensionality mismatch, the Analytics Engine routes goalkeepers to a dedicated `calculate_gk_rating` method. This method bypasses the Bayesian smoothing and Z-score standardisation pipeline used for outfield players entirely — only a small number of volume metrics receive temporal scaling — and instead derives a standalone mathematical heuristic ($H_{GK}$), standardises it against historical goalkeeper distributions, and passes the result through a multi-layer adjustment pipeline.

### 2. The Core Heuristic Formulation
The base performance of a goalkeeper is captured via a custom synthetic formula, heavily weighted toward Expected Goals Prevented ($xGP$), where $xGP = \text{Opponent xG} - \text{Goals Conceded}$:

$$H_{GK} = (xGP \times 1.5) + \left( \ln(\text{Saves} + 1) \times \frac{\text{Save\%}}{100} \right)$$

**Mathematical justifications:**

- **xGP Weighting (1.5):** Anchoring the formula to $xGP$ prioritises shot quality over shot volume. A goalkeeper who faces $3.0$ xG and concedes one goal prevented $2.0$ expected goals; one who faces $3.0$ xG and concedes three prevented nothing. The 1.5 multiplier ensures this distinction dominates the heuristic.
- **Logarithmic Volume Dampening:** Passing the raw save count through $\ln(\text{Saves} + 1)$ dampens the impact of facing a high volume of low-quality shots. Facing 12 routine long-range efforts is not equivalent to facing 12 dangerous close-range attempts; the logarithm prevents shot volume alone from inflating the score.
- **Efficiency Scaling:** The logarithmic volume is multiplied by the save percentage, heavily penalising goalkeepers who make numerous saves but still concede highly preventable goals.

Once $H_{GK}$ is calculated, it is standardised into a Z-score using pre-calculated historical goalkeeper mean and standard deviation:

$$S_{raw} = \frac{H_{GK} - \mu_{GK}}{\sigma_{GK}}$$

### 3. Pre-Sigmoid Score Stabilisation
The heuristic formula contains a save term — $\ln(\text{Saves} + 1) \times \text{Save\%}/100$ — that is structurally unreliable at low shot volumes. A goalkeeper who faces one routine shot and saves it generates a disproportionately high save contribution that does not reflect a genuinely demanding performance. Rather than patching this with a series of conditional floor overrides, the engine stabilises the raw score through two sequential steps before any additive bonuses are applied.

#### Step 1 — Volume Confidence Shrinkage
At low shot volumes the save term cannot be trusted, so the engine blends the full heuristic Z-score toward a reduced signal that contains only the xGP component — the one part of the formula that remains meaningful regardless of shot count. This anchor is:

$$\text{anchor} = \frac{xGP \times 1.5}{\sigma_{GK}}$$

The blend is governed by a continuous shrink factor derived from shot volume:

$$\text{shrink} = \min \left( 1.0, \sqrt{\frac{\text{shots\_against}}{K}} \right), \quad K = 5.0$$

The stabilised score is:

$$S_{raw} \leftarrow \text{anchor} \times (1 - \text{shrink}) + S_{raw} \times \text{shrink}$$

At zero shots the shrink factor is 0 and $S_{raw}$ collapses entirely to the anchor — a goalkeeper who faced nothing is evaluated purely on the gap between expected and actual concessions. At $K = 5.0$ normalised shots the factor reaches 1.0 and the full heuristic score passes through unchanged. In between the two signals blend continuously: a goalkeeper who faced three shots contributes approximately $\sqrt{3/5} \approx 0.77$ of their heuristic score and $0.23$ of the xGP anchor.

Crucially, the anchor is non-negative for any positive xGP, so a goalkeeper who prevented goals in a quiet match is not penalised by this step — the unreliable save term is simply replaced with a signal that can be trusted at low volumes.

```python
shrink = min(1.0, np.sqrt(shots_against / self.GK_SHOTS_CONFIDENCE_K))  # K = 5.0
xgp_anchor = (xgp * 1.5) / gk_std if gk_std > 0 else 0.0
raw_score = xgp_anchor * (1 - shrink) + raw_score * shrink
```

#### Step 2 — Absolute Final Floor
An unconditional floor at $-1.25$ is applied after shrinkage, regardless of circumstances. No goalkeeper can enter the additive bonus stage with a raw score below this value. This is the mathematical backstop — it ensures that even genuinely catastrophic performances produce a minimum post-sigmoid rating rather than a potentially undefined edge case.

```python
raw_score = max(raw_score, -1.25)
```

### 4. Pre-Sigmoid Bonus Adjustments
After the stabilisation steps, two sets of additive bonuses are applied to $S_{raw}$ before the sigmoid runs.

#### Additive Performance Bonuses
- **Penalty Heroics:** $+0.50$ per penalty save and $+0.50$ per shootout save. These are combined into a single operation (`total_penalty_saves = penalty_saves + shoot_out_saves`). Each save represents an absolute, match-defining moment of individual excellence that the heuristic formula cannot adequately capture.
- **Reliable Shift:** If `goals_conceded == 1`, `xgp > 0`, and `save_success_rate >= 80%`, the keeper receives $+0.25$. Conceding one goal while saving more xG than was conceded and maintaining a high save rate is a quietly excellent performance that deserves recognition above the narrow-miss floor.

#### The Inverted Clean Sheet Bonus
A clean sheet is registered only when `goals_conceded == 0`, `penalty_goals_conceded == 0`, and `shoot_out_goals_conceded == 0`. When this condition is met, a further bonus is applied to $S_{raw}$. While defenders are rewarded most for clean sheets against _low_ xG (indicating defensive control), goalkeepers are rewarded most for clean sheets against _high_ xG (indicating a goaltending performance that single-handedly preserved the result):

```python
# 1. Passenger: Low threat, keeper had little to do
if xg_against <= 1.0 and xgp < 0.95:
    return raw_score + 0.30

# 2. Bailout: High threat, keeper made multiple crucial saves
elif xg_against > 2.0 and saves >= 5:
    return raw_score + 0.80

# 3. Standard: Any other clean sheet scenario
else:
    return raw_score + 0.50
```

Once all pre-sigmoid adjustments are complete, the sigmoid transformation is applied to the final $S_{raw}$. The Match Supremacy Scalar is then subtracted from the post-sigmoid rating — identical in application to the outfield pipeline — and the result is clamped to $[0.0,\ 10.0]$.