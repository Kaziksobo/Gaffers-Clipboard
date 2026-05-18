### 1. The Native API Constraints
The Analytics Engine operates on a strictly bounded data diet. The native extraction tool captures only 16 base metrics for outfield players. These metrics are heavily biased toward traditional counting stats and lack the granular transition data (e.g., interceptions, progressive carries, key passes, aerial duels) standard in modern data science.

To standardise the evaluation of playing time, all volume-based counting stats are normalised "Per-90" ($\text{p90}$) rate before entering the matrix.

### 2. The 16-Element Native Array
The raw telemetry matrix is partitioned into four distinct tactical categories:

**Attacking & Output:**
1. `goals_p90`
2. `assists_p90`
3. `shots_p90`
4. `shot_accuracy` (%)

**Possession & Distribution:**
5. `passes_p90`
6. `pass_accuracy` (%)
7. `dribbles_p90`
8. `dribble_success_rate` (%)

**Defensive Actions:**
9. `tackles_p90`
10. `tackle_success_rate` (%)
11. `possession_won_p90`
12. `possession_lost_p90`

**Physicality & Discipline:**
13. `distance_covered_p90`
14. `distance_sprinted_p90`
15. `fouls_committed_p90`
16. `offsides_p90`

### 3. The 17th Dimension: Synthetic Expected Threat (xT)
Because the native 16-element array completely lacks spatial progression metrics (e.g., measuring the difference between a safe sideways pass and a line-breaking pass), the engine generates a 17th synthetic feature: **Expected Threat (`xt_bonus_p90`)**.

This derived metric acts as a mathematical proxy for ball progression and spatial dominance. By combining and weighting elite passing volume, dribbling volume, and sprint distance, the engine creates a synthetic indicator of how effectively a player moved the ball into dangerous areas. 

This finalised 17-element array ($T_{17}$) serves as the sole input vector for the downstream PCA eigen-decomposition and positional heuristic pipelines.