### 1. The Telemetry Constraint (Blind Aggregation)
When a player plays multiple tactical roles in a single match, the engine receives an unpartitioned telemetry array ($T_{match}$). Because the system lacks temporal parsing (minutes played per position) and spatial parsing (event locations), it cannot isolate which specific statistics belong to which tactical role. 

To bypass this blind aggregation, the algorithm executes Parallel Matrix Evaluation. It processes $T_{match}$ through $n$ distinct Positional Weight Vectors corresponding to the user's input, generating a set of positional ratings $R = \{r_1, r_2, \dots, r_n\}$.

### 2. The Alpha Drag Formula
To synthesise the set $R$ into a single scalar without falling victim to maximum-value loopholes or punitive averaging, the engine identifies the maximum rating ($R_{max}$) and the arithmetic mean of all ratings ($R_{mean}$).

It then applies the Alpha Drag Coefficient ($\alpha$):

$$
R_{hybrid} = R_{max} - \alpha (R_{max} - R_{mean})
$$

### 3. Calibrating the Alpha Coefficient ($\alpha = 0.25$)
The engine hardcodes the drag coefficient at $\alpha = 0.25$. 

This specific constant acts as a weighted centre of gravity. By subtracting exactly 25% of the distance between the maximum and mean ratings, the algorithm effectively assigns a **75% confidence weight** to the player's highest tactical alignment. The underlying mathematical assumption is that the highest rating naturally correlates with the position where the player spent the vast majority of their minutes and accumulated the bulk of their statistics.

```python
r_max: float = max(calculated_ratings)
r_mean = np.mean(calculated_ratings)

# Apply a 25% drag toward the mean
alpha = 0.25
hybrid_rating = r_max - (alpha * (r_max - r_mean))
```

The remaining 25% "drag" serves as a mathematical tax for statistical bleed. If a Centre Back (CB) plays a fraction of the match at Right Back (RB), their aggregate passing and tackling stats are evaluated through the RB matrix, which expects crosses and high progressive distance. This inevitably generates a lower secondary rating. The $\alpha = 0.25$ parameter ensures this secondary rating slightly anchors the $R_{max}$, creating a realistic, synthesised representation of a fragmented tactical performance without triggering an unrecoverable plunge in the final match rating.