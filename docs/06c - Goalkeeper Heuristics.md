### 1. Matrix Dimensionality Mismatch
Outfield ratings are computed as a 17-element linear combination (dot product) of standardised Z-scores, mapped against a $17 \times 9$ PCA weight matrix. Goalkeeper telemetry is fundamentally incompatible with this architecture, as the engine receives a structurally distinct 11-element array restricted entirely to reactive metrics (`shots_against`, `shots_on_target`, `saves`, `goals_conceded`, `save_success_rate`, `punch_saves`, `rush_saves`, `penalty_saves`, `penalty_goals_conceded`, `shoot_out_saves`, `shoot_out_goals_conceded`).

To resolve this dimensionality mismatch, the Analytics Engine routes goalkeepers to a dedicated `calculate_gk_rating` method. This method derives a standalone mathematical heuristic ($H_{GK}$), standardises it against historical goalkeeper distributions, and applies specific reactive floors.

### 2. The Core Heuristic Formulation
The base performance of a goalkeeper is captured via a custom synthetic formula heavily weighted toward Expected Goals Prevented ($xGP$), where $xGP = \text{Opponent xG} - \text{Goals Conceded}$.

$$
H_{GK} = (xGP \times 1.5) + \left( \ln(\text{Saves} + 1) \times \frac{\text{Save\%}}{100} \right)
$$

**Mathematical Justifications:**
* **xGP Weighting (1.5):** By anchoring the formula to $xGP$, the engine prioritises shot quality over shot volume.
* **Logarithmic Volume Dampening:** By passing the raw save count through a natural logarithm $\ln(\text{Saves} + 1)$, the algorithm mathematically dampens the impact of facing a high volume of low-quality shots. 
* **Efficiency Scaling:** The logarithmic volume is multiplied by the save percentage, heavily punishing goalkeepers who make numerous saves but still concede highly preventable goals.

Once $H_{GK}$ is calculated, it is standardised into a familiar Z-score using a pre-calculated, historical Goalkeeper mean and standard deviation:
$$
S_{raw} = \frac{H_{GK} - \mu_{GK}}{\sigma_{GK}}
$$

### 3. Contextual Bounding & Low-Volume Forgiveness
Because goalkeeper stats are prone to extreme small-sample-size anomalies, the engine applies rigorous pre-synthesis bounding to $S_{raw}$. 

* **The Spectator Exemption:** If a goalkeeper faces $0$ shots on target and concedes $0$ goals, their raw score defaults to exactly $0.0$ (resulting in the $6.0$ baseline rating). 
* **Low-Volume Forgiveness:** In football, a goalkeeper may face only $1$ shot all game and concede $1$ goal, resulting in a mathematically catastrophic $0\%$ save rate. To prevent the rating from plummeting to a 3.0 or 4.0, the engine applies the "Match 69 Fix." If a keeper faces $\leq 3$ shots and concedes $\leq 1$ goal, their raw Z-score is rigidly floored at $-0.5$, mitigating the small-sample penalty.

### 4. The Inverted Clean Sheet Bonus
While defenders are rewarded most for clean sheets against *low* xG (indicating defensive control), goalkeepers are rewarded most for clean sheets against *high* xG (indicating a goaltending bailout). The engine implements this through conditional branching:

```python
# 1. Passenger: Low threat, keeper didn't have to do much
if xg_against <= 1.0 and xgp < 0.95:
    return raw_score + 0.30

# 2. Bailout: High threat, keeper made a ton of saves
elif xg_against > 2.0 and saves >= 5:
    return raw_score + 0.80

# 3. Standard: Any other clean sheet scenario
else:
    return raw_score + 0.50
```

By inverting the contextual logic from the outfield algorithms, applying absolute bonuses for penalty saves ($+0.5\sigma$ per save), and finally applying the Match Supremacy Scalar, the engine finalises a highly accurate, context-aware 1-to-10 rating for the goalkeeper.