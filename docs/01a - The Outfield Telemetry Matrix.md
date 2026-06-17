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

**Note on shots:** The native telemetry records total shots. Before the 17-element vector enters the scoring pipeline, shots are decomposed into `non_goal_shots_p90` — shots minus goals, clipped to zero. This isolates pure chance creation from goal-scoring output, so a striker who scored twice from two shots is not rewarded twice for the same events.
### 3. The 17th Dimension: Synthetic Expected Threat (xT)
Because the native 16-element array completely lacks spatial progression metrics (e.g., the difference between a safe sideways pass and a line-breaking through ball), the engine generates a 17th synthetic feature: **Expected Threat (`xt_bonus_p90`)**.

This derived metric acts as a mathematical proxy for ball progression and spatial dominance. The engine constructs it from three components: the player's sprint ratio (the proportion of total distance covered at high intensity, capturing physical intent and line-breaking runs), their passing volume and accuracy (capturing technical execution and distribution quality), and a possession control ratio (which filters out defensive recovery sprints from genuine attacking build-up play, by comparing possession won against possession lost).

The positional scalar applied to the formula also varies by role — attackers and attacking midfielders receive a higher base multiplier than defensive midfielders and centre-backs, reflecting the different degree to which each position is expected to generate progressive threat. Full mathematical derivation and calibration details are in [[03a - Expected Threat Synthesis]].

This finalised 17-element array ($T_{17}$​) serves as the sole input vector for the downstream PCA eigen-decomposition and positional heuristic pipelines.