### 1. The Asymmetric Logistic Function
To map the unbounded continuous variable $S_{final} \in (-\infty, \infty)$ to the recognised $0.0$–$10.0$ continuum, the engine uses a scaled logistic function with a steepness parameter that branches on the sign of the input:

$$R_{raw} = 10 \times \frac{1}{1 + e^{-k\,(S_{final} - S_0)}}$$

$$k = \begin{cases} 0.85 & \text{if } S_{final} \geq 0 \\ 0.45 & \text{if } S_{final} < 0 \end{cases}$$

- **$R_{raw}$:** The resulting $0$–$10$ match rating, before supremacy scaling.
- **$S_{final}$:** The impact-scaled raw score from the positional modifier pipeline.
- **$k$:** The steepness parameter, controlling the slope of the S-curve on each side of the baseline.
- **$S_0$:** The translation parameter, derived from $k$ to lock the median at exactly 6.0.

The asymmetry is deliberate: the positive side climbs steeply to differentiate between good, great, and elite performances, while the negative side descends more gently to reflect the psychological reality that football ratings below 4.0 are reserved for genuinely catastrophic matches rather than merely below-average ones.

### 2. Anchoring the Baseline ($S_0$ and the 6.0 Median)
In a pure mathematical model mapped from 0 to 10, the median defaults to 5.0. However, the Analytics Engine explicitly rejects a 5.0 median because it violates the psychological reality of football ratings.

In established industry frameworks (e.g., *L'Equipe*, WhoScored), ratings possess a natural positive skew. A player who performs terribly rarely receives below a 4.0, whereas excellent players frequently receive 8.0+. To account for this asymmetric headroom, the engine locks an entirely average, $0.0$ standard deviation performance to exactly **6.0**.

The derivation of $S_0$ is identical regardless of which value of $k$ is active. Setting $S_{final} = 0$ and solving for $R_{raw} = 6.0$:

$$6.0 = 10 \times \frac{1}{1 + e^{k \cdot S_0}}$$

$$1 + e^{k \cdot S_0} = \frac{10}{6} \implies e^{k \cdot S_0} = \frac{2}{3}$$

$$k \cdot S_0 = \ln\!\left(\frac{2}{3}\right) \approx -0.405$$

$$S_0 = \frac{\ln(2/3)}{k}$$

Because $S_0$ is a function of $k$, both steepness values produce curves that pass through exactly 6.0 at $S_{final} = 0$. The 6.0 baseline is guaranteed regardless of which side of zero the input falls on.

### 3. Calibrating the Steepness Parameters

#### The Positive Side ($k = 0.85$)
Above the 6.0 baseline, $k$ governs how quickly an excellent performance climbs toward a perfect 10.0.

If $k$ is set too high (e.g., $k = 1.5$), the curve is too steep: a standard great game at $+2.5\sigma$ would immediately hit 10.0, making the perfect rating far too common and eliminating the distinction between very good and genuinely exceptional. If $k$ is too low (e.g., $k = 0.4$), the curve is too flat: a historic, multi-goal performance at $+4.0\sigma$ would struggle to surpass 8.5, unfairly punishing genuine brilliance.

$k = 0.85$ is the calibrated equilibrium. Under this slope, a strongly anomalous $+3\sigma$ performance organically approaches 9.5. Reaching a true 10.0 requires pushing beyond the normal limits of the statistical distribution — possible, but demanding. The corresponding translation parameter is:

$$S_0 = \frac{\ln(2/3)}{0.85} \approx -0.477$$

#### The Negative Side ($k = 0.45$)
Below the 6.0 baseline, a symmetric $k = 0.85$ would map a $-2.5\sigma$ performance to approximately 3.3 — a rating psychologically reserved for catastrophic collapses: goalkeepers conceding five, defenders scoring own goals, strikers invisible for 90 minutes. A player who simply had a poor but unremarkable statistical match should settle in the 4.5 to 5.5 range, not plunge toward the floor.

$k = 0.45$ produces this gentler descent. Under this slope, a $-2.5\sigma$ performance maps to approximately 4.3 and a $-3\sigma$ performance to approximately 3.9. The floor remains reachable for genuinely extreme negative output, but ordinary bad games are treated proportionately. The corresponding translation parameter is:

$$S_0 = \frac{\ln(2/3)}{0.45} \approx -0.900$$

### 4. Algorithmic Implementation
The Python implementation explicitly calculates $S_0$ at runtime from $k$ using `np.log`, preventing floating-point rounding errors that could shift the 6.0 baseline over thousands of iterations. The asymmetric branch is resolved first, so every evaluation uses a self-consistent $(k, S_0)$ pair:

```python
def _apply_sigmoid_transformation(self, raw_score: float) -> float:
    k = 0.85 if raw_score >= 0 else 0.45
    s_0: float = np.log(2 / 3) / k
    return 10 * (1 / (1 + np.exp(-k * (raw_score - s_0))))
```

The result is a 6.0-anchored curve that climbs steeply through the positive range while descending gently through the negative — matching the psychological distribution of football ratings as understood by fans, managers, and analysts alike.