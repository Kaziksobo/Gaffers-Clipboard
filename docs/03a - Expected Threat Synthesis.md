### 1. The Algebraic Foundation
To synthesise a proxy for Expected Threat (xT) without spatial coordinate data, the `MatchRatingsService` uses a heuristic formula that combines a player's positional role, physical intent, possession quality, and technical execution into a single progressive threat score:

$$xT_{bonus} = S_{pos} \times C_{ctrl} \times \left( \frac{D_{sprint}}{D_{total}} \right) \times \ln\!\left( A_{pass} \times V_{pass} + 1 \right)$$

- **$S_{pos}$:** Positional base scalar — calibrated to the role's progression responsibility.
- **$C_{ctrl}$:** Possession control ratio — a noise filter distinguishing attacking intent from defensive recovery.
- **$D_{sprint}$:** Distance sprinted per 90.
- **$D_{total}$:** Total distance covered per 90.
- **$A_{pass}$:** Pass completion percentage, expressed proportionally (0.0–1.0).
- **$V_{pass}$:** Total passes attempted per 90.

### 2. The Positional Scalar ($S_{pos}$)
The base scalar is not a fixed constant. It is drawn from a position-keyed lookup at runtime, reflecting the degree to which each tactical role is expected to generate progressive attacking threat:

| Tier | Positions | $S_{pos}$ |
|---|---|---|
| Attacking | ST, RW, LW, CAM, CF | 0.35 |
| Mid | CM, RM, LM, RWB, LWB, RB, LB | 0.25 |
| Defensive | CDM, CB | 0.10 |

The rationale is directly tied to positional responsibility for ball progression. Attackers and attacking midfielders are the primary drivers of progressive threat — they are expected to receive the ball in advanced areas and create danger. A winger covering a high sprint ratio with elite passing volume is doing exactly what the position demands, so the bonus is scaled generously. Conversely, a CDM or CB who sprints frequently is most likely doing so in a defensive recovery context rather than driving an attack; suppressing their scalar to 0.10 ensures the xT proxy does not misrepresent defensive activity as progressive threat. The mid-tier 0.25 was calibrated to act as a tiebreaker rather than a primary driver: if two central midfielders produce identical core statistical contributions, the engine correctly awards the marginally higher rating to the one who combined more intense physical running with higher passing volume.

For any position not found in the lookup, the engine falls back to the mid-tier default of 0.25.

### 3. The Physicality Multiplier and Possession Filter
The first ratio in the formula, $\frac{D_{sprint}}{D_{total}}$, establishes a player's physical intent. By expressing sprint distance as a proportion of total distance covered, the engine isolates players who spend a high fraction of their match running at intensity — a hallmark of line-breaking runs and box-to-box dynamism — from those who cover similar total distances at a jog.

However, a high sprint ratio alone does not confirm attacking intent. A centre-back being pinned back by a sustained press may sprint aggressively and repeatedly without ever advancing the ball into a dangerous area. To filter out this defensive noise, the formula applies a possession control ratio:

$$C_{ctrl} = \min\!\left( \frac{P_{won} + 1}{P_{lost} + 1},\ 2.5 \right)$$

Where $P_{won}$ is possession won per 90 and $P_{lost}$ is possession lost per 90. The $+1$ Laplace smoothing in both the numerator and denominator prevents division by zero in extreme cases. The ratio is hard-capped at $2.5$ to prevent an elite ball-winner from generating a disproportionate bonus purely through defensive interceptions.

A player who sprints aggressively while consistently winning the ball and rarely losing it produces a high $C_{ctrl}$, correctly amplifying their xT proxy. A player who sprints just as much but repeatedly turns the ball over produces a low $C_{ctrl}$, suppressing the bonus — their physical intensity is reflecting defensive pressure, not progressive threat.

### 4. The Technical Base and Logarithmic Restraint
The second half of the formula evaluates technical execution. Multiplying $A_{pass}$ by $V_{pass}$ calculates the exact volume of successful passes completed per 90. This product is wrapped in a natural logarithm:

$$\ln\!\left( A_{pass} \times V_{pass} + 1 \right)$$

This applies strict mathematical diminishing returns. A player who completes 30 passes receives a significant spike, reflecting meaningful match involvement and distribution. A player who completes 90 passes receives a severely diminished marginal return, preventing sterile recycling possession around the backline from generating outsized xT. The difference between 10 and 30 successful passes is treated as far more significant than the difference between 70 and 90 — which accurately reflects the reality that the latter is more likely to represent safe, non-progressive passing.

The $+1$ constant is a structural necessity. If a player completes zero passes, $\ln(0)$ evaluates to $-\infty$, which would corrupt the rating matrix. The constant guarantees that the absolute minimum return is $\ln(1) = 0.0$, safely resolving to a zero contribution rather than an undefined value.

### 5. Algorithmic Implementation and Safety

```python
def _calculate_xt_bonus(
    self,
    pos: str,
    pass_accuracy: float,
    passes_p90: float,
    distance_sprinted_p90: float,
    distance_covered_p90: float,
    possession_won_p90: float,
    possession_lost_p90: float,
) -> float:
    if distance_covered_p90 == 0:
        return 0.0

    base_scalar: float = self.XT_POSITION_SCALARS.get(pos, 0.25)

    # Defensive noise filter (Laplace-smoothed, bounded at 2.5)
    control_ratio: float = min(
        (possession_won_p90 + 1.0) / (possession_lost_p90 + 1.0), 2.5
    )
    return (
        base_scalar
        * control_ratio
        * (distance_sprinted_p90 / distance_covered_p90)
        * float(np.log((pass_accuracy * passes_p90) + 1.0))
    )
```

The function is called only after the full Bayesian smoothing and per-90 conversion pipeline has run, ensuring that the inputs are statistically stable before the proxy is computed. Two safety guards are in place: the explicit `if distance_covered_p90 == 0` check intercepts telemetry glitches that would otherwise cause a `ZeroDivisionError` in the sprint ratio, and the $+1$ inside the logarithm ensures a zero-pass performance returns $0.0$ rather than crashing. Both return a clean $0.0$ bonus rather than propagating an undefined value into the downstream Z-score matrix.