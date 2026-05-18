### 1. The Inverse Logistic Function
To map the unbounded continuous variable $S_{raw} \in (-\infty, \infty)$ to the recognised $0.0 - 10.0$ continuum, the engine utilises a scaled inverse logistic function:

$$
R_{raw} = 10 \times \left( \frac{1}{1 + e^{-k(S_{raw} - S_0)}} \right)
$$

* **$R_{raw}$:** The resulting $0-10$ match rating.
* **$S_{raw}$:** The input unbounded $Z$-score sum.
* **$k$:** The steepness parameter (controlling the slope of the S-curve).
* **$S_0$:** The translation parameter (shifting the curve to align the median).

### 2. Anchoring the Baseline ($S_0$ and the 6.0 Median)
In a pure mathematical model mapped from 0 to 10, the median would default to 5.0. However, the Analytics Engine explicitly rejects a 5.0 median because it violates the psychological reality of football ratings. 

In established industry frameworks (e.g., *L'Equipe*, WhoScored), ratings possess a natural positive skew. A player who performs terribly rarely receives below a 4.0, whereas excellent players frequently receive 8.0+. To account for this asymmetric headroom, the engine sets the baseline for an entirely average, $0.0$ standard deviation performance to exactly **6.0**. 

To achieve this, the engine mathematically solves for the translation parameter $S_0$:
$$
6.0 = 10 \times \left( \frac{1}{1 + e^{k \cdot S_0}} \right)
$$
$$
1 + e^{k \cdot S_0} = \frac{10}{6.0} \approx 1.666 \implies e^{k \cdot S_0} = \frac{2}{3}
$$
$$
k \cdot S_0 = \ln\left(\frac{2}{3}\right) \approx -0.405
$$

### 3. Calibrating the Steepness Parameter ($k = 0.85$)
With the translation baseline established, the developer must calibrate the steepness parameter ($k$). This constant dictates how aggressively the rating climbs or falls as standard deviations accumulate. 

If $k$ is set too high (e.g., $k=1.5$), the S-curve is too vertical; a standard great game ($+2.5\sigma$) would instantly hit a 10.0, making the perfect rating far too common. If $k$ is set too low (e.g., $k=0.4$), the curve is too flat; a historic, multi-goal anomaly ($+4.0\sigma$) would mathematically struggle to surpass an 8.5, unfairly punishing the user for a world-class performance.

The engine hardcodes the steepness parameter at $k = 0.85$ as the optimal "Goldilocks" threshold. This specific slope mathematically protects the mythical 10.0 rating while providing accurate scalar rewards. Under $k=0.85$, highly anomalous $+3\sigma$ events organically approach a $9.5$ rating. To achieve a true $10.0$, a player must push the absolute limits of the statistical distribution without hitting a rigid mathematical ceiling too early.

Solving for $S_0$ with $k=0.85$ yields $S_0 \approx -0.477$. Thus, the final algebraic formula embedded in the engine is:

$$
R_{raw} = 10 \times \left( \frac{1}{1 + e^{-0.85(S_{raw} + 0.477)}} \right)
$$

### 4. Algorithmic Implementation
The Python implementation explicitly calculates $S_0$ at runtime using `np.log`, preventing floating-point rounding errors that could shift the $6.0$ baseline over thousands of iterations.

```python
def _apply_sigmoid_transformation(self, raw_score: float) -> float:
    # Steepness parameter calibrated for 3-sigma events hitting ~9.5
    k: float = 0.85
    
    # Calculate the exact translation parameter for a 6.0 median
    s_0: float = np.log(2 / 3) / k  
    
    return 10 * (1 / (1 + np.exp(-k * (raw_score - s_0))))