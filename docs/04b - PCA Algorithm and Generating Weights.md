### 1. Dataset Preprocessing
Before any PCA mechanics run, the historical dataset undergoes three preprocessing steps specific to the offline calibration pipeline. These steps do not occur in the live scoring engine — they are applied once during development to ensure the weight derivation reflects clean, context-adjusted football performance rather than raw counting artefacts.
##### Possession Adjustment
A consistent bias exists in any dataset drawn from a single team: a possession-dominant side will see their players accumulate higher passing and dribbling counts simply because the team holds the ball more, not because any individual is performing better. Conversely, defensive stats like tackles and possession won are naturally suppressed for high-possession teams because the opposition rarely has the ball long enough to lose it. Left unadjusted, PCA would derive weights that systematically over-reward the ball-dominant actions of possession-heavy teams and under-reward the defensive actions that define lower-block football.

To neutralise this bias, every volume stat is adjusted to a 50% possession baseline before Bayesian smoothing is applied:

$$X_{padj} = X_{raw} \times \sqrt{\frac{50}{P_{team}}} \quad \text{(attacking stats)}$$

$$X_{padj} = X_{raw} \times \sqrt{\frac{50}{100 - P_{team}}} \quad \text{(defensive stats)}$$
Where $P_{team}$​ is the team's possession percentage in that match. Attacking stats adjusted include passes, dribbles, shots, and possession lost; defensive stats adjusted include tackles, possession won, and fouls committed. The square root softens the correction so that genuinely exceptional performances on possession-extreme teams are not over-penalised — only the systemic possession bias is dampened, not the individual quality signal.
##### Non-Goal Shots Derivation
Before the per-90 metrics enter the Z-score and PCA pipeline, a 17th column is derived from the shot data. Rather than using total shots per 90, the engine isolates non-goal shots:

$$non\_goal\_shots\_p90 = \max(shots\_p90 - goals\_p90, 0)$$

This separates pure chance creation from goal-scoring output. Without this split, a striker who scored twice from two shots would receive a high Z-score for both goals and shots — double-counting the same two events. The separation ensures goals are evaluated as goals and the shot metric captures only the chance-generation component.
##### Log-Normal Transformation
Several statistics have heavily right-skewed distributions: goals, assists, shots, and certain defensive counting stats are zero in the majority of match observations, with rare extreme values. Applying Z-scores directly to these raw values would allow outlier performances to exert disproportionate influence over the PCA covariance structure — a player scoring four goals in a single match could warp the entire weight derivation for a position.

To compress these distributions before standardisation, a $\ln(x + 1)$ transform is applied to the following columns in the offline notebook:

```
goals_p90, assists_p90, non_goal_shots_p90, offsides_p90, fouls_committed_p90, possession_won_p90, possession_lost_p90
```

The means and standard deviations stored for these columns — used both to Z-score the PCA inputs and as reference baselines for live scoring — are computed from the log-transformed values. This is why the live engine applies a matching $\ln(x + 1)$compression before Z-scoring these same stats at inference time, and why their stored means must be back-converted via `expm1` before use as Bayesian priors (as described in Section II).

### 2. Tactical Block Scaling
With the preprocessed dataset ready, the engine must structure it to account for two distinct architectural hazards before the covariance matrix is computed: structural size bias and blind variance optimisation.

The 17 metrics are grouped into tactical blocks. Without scaling, blocks with more features (e.g., _Attacking_ has 4 stats) artificially inject more variance into the dataset than smaller blocks (e.g., _Safety_ has 1 stat), biasing the PCA to favour large blocks regardless of tactical importance. Furthermore, if standard PCA is left entirely unguided, it will blindly extract whichever metrics hold the highest variance. A CDM dataset may show high variance in shooting simply because in some matches they are pinned back while in others they roam forward — standard PCA would assign shooting a high weight not because it matters for a CDM, but because it happens to fluctuate.

To resolve both hazards, the engine applies a **Guided Variance Transformation**. The developer defines a macro-philosophy dictionary assigning a structural multiplier to each block based on the positional mandate. The standard block schema shared by most positions is:

```python
blocks = {
    "Attacking": [
        "goals_p90_z", "assists_p90_z", "non_goal_shots_p90_z", "shot_accuracy_z"
    ],
    "Passing": [
        "passes_p90_z", "pass_accuracy_z"
    ],
    "Dribbling": [
        "dribbles_p90_z", "dribble_success_rate_z"
    ],
    "Safety": [
        "possession_lost_p90_z"
    ],
    "Defending": [
        "tackles_p90_z", "tackle_success_rate_z", "possession_won_p90_z"
    ],
    "Workrate_and_Threat": [
        "distance_covered_p90_z", "distance_sprinted_p90_z", "xt_bonus_p90_z"
    ],
    "Tactical_Discipline": [
        "offsides_p90_z", "fouls_committed_p90_z"
    ],
}
```

Each position then defines its own philosophy dictionary. Two examples — the CDM as a specialist position and the CM as the near-neutral baseline:

```python
# CDM: heavily emphasises defending and passing, suppresses dribbling, mildly reduces workrate
cdm_philosophy = {
    "Attacking": 1.0,
    "Passing": 2.7,
    "Dribbling": 0.6,
    "Safety": 1.4,
    "Defending": 2.5,
    "Workrate_and_Threat": 0.8,
    "Tactical_Discipline": 1.0,
}

# CM: all football blocks equal; Tactical Discipline mildly suppressed
cm_philosophy = {
    "Attacking": 1.0,
    "Passing": 1.0,
    "Dribbling": 1.0,
    "Safety": 1.0,
    "Defending": 1.0,
    "Workrate_and_Threat": 1.0,
    "Tactical_Discipline": 0.5,
}
```

The Tactical Discipline suppression for CM reflects a calibration finding: fouling rate has high natural variance in the training data but is a weak differentiator between CM performances in practice. Leaving it at 1.0 allows noise to over-influence the PCA output.

When iterating through the Z-scores, the engine identifies the number of stats within each block ($k$) and queries the philosophy dictionary for the assigned multiplier $W_{block}$. Every stat in the block is scaled by:

$$X_{scaled} = X_z \times \frac{W_{block}}{\sqrt{k}}$$​​

Dividing by $\sqrt{k}$​ establishes a neutral size baseline — the 4-stat *Attacking* block does not mathematically overpower the 1-stat *Safety* block simply by having more columns. Multiplying by $W_{block}$​ then artificially dilates or compresses the variance of specific tactical zones before the PCA analyses the matrix, steering the eigen-decomposition toward the intended positional priorities.

### 3. Robust Covariance Estimation and the MCD Algorithm
Standard PCA relies on a traditional sample covariance matrix. However, the standard formula is highly sensitive to extreme outliers because it calculates variance using the arithmetic mean of the entire dataset — a single anomalous performance (a goalkeeper playing outfield, a red card in the third minute) can warp the covariance structure and produce weight vectors that do not generalise to typical matches.

To establish algorithmic stability, the engine explicitly rejects the standard sample covariance in favour of the **Minimum Covariance Determinant (MCD)** estimator.

Visualise the dataset as a matrix where every row is a single match performance. Standard covariance uses every row. The MCD algorithm, configured with `support_fraction=0.98`, is instructed to deliberately discard 2% of rows to find the cleanest possible core dataset. Mathematically, $H$ denotes this clean subset. Because the algorithm does not know in advance which rows are anomalies, it searches by evaluating thousands of different combinations of 98% subsets. For every candidate $H$, it computes the determinant of the associated covariance matrix $C_H$​. Geometrically, a lower determinant means the data points are packed more tightly together:

$$\min_{H} \det(C_H)$$

The combination that yields the smallest determinant is the tightest, most consistent cluster of match performances — the 2% of rows causing the data ellipsoid to stretch are the anomalies and are discarded. The robust covariance matrix is then computed exclusively from the surviving rows:

$$C_{MCD} = \frac{1}{h - 1} \sum_{i \in H} (x_i - \mu_{MCD})(x_i - \mu_{MCD})^T$$

```python
mcd = MinCovDet(random_state=42, support_fraction=0.98).fit(scaled_pca_df)
cov = mcd.covariance_
```

Substituting $C_{MCD}$ in place of the standard covariance ensures the downstream eigen-decomposition is built strictly on sustainable, repeatable football logic rather than being warped by statistical anomalies.

### 4. Eigen-Decomposition and Dimensional Truncation
With the robust covariance matrix established, the algorithm executes eigen-decomposition — a linear algebra operation that rotates the coordinate system to align exactly with the axes of maximum variance in the dataset:

$$C_{MCD} \mathbf{v}_i = \lambda_i \mathbf{v}_i$$

For a 17×1717 \times 17 17×17 covariance matrix, this extracts 17 pairs:

- **Eigenvectors ($\mathbf{v}_i$):** Directional vectors. In football terms, each represents a distinct tactical profile — e.g., "Defensive Dominance" or "Passing Range." The values inside dictate the recipe of stats that define that profile.
- **Eigenvalues ($\lambda_i$​):** Magnitudes. Each eigenvalue defines exactly how much variance its corresponding tactical profile explains in the dataset.

The engine sorts components in descending order by eigenvalue and applies dimensional truncation, retaining only the top $k=9$ components. These account for approximately 85% of the dataset's total tactical variance. The remaining components are discarded because they represent statistical noise — highly specific, mathematically unstable correlations that do not consistently define player performance across different matches and conditions.

### 5. Vector Reassembly, Scale Correction, and Normalisation
At this stage the engine holds a $17 \times 9$ matrix of eigenvectors across 9 retained components. It must collapse this back into a single 1D positional weight vector.

For every stat $j$, the engine aggregates its loading across all retained components, scaling each loading by the square root of the corresponding eigenvalue:

$$w_{raw, j} = \sum_{i=1}^{k} |v_{j,i}| \sqrt{\lambda_i}$$

Two mathematical decisions here are paramount:

1. **Absolute Values ($|v|$):** The sign of an eigenvector is mathematically arbitrary — it only indicates direction along the axis, not importance. Taking the absolute value ensures the algorithm captures the true magnitude of each stat's influence on the tactical profile regardless of sign.
2. **Square Root Scaling ($\sqrt{\lambda}$):** Eigenvalues represent variance. Taking the square root converts them to standard deviation, which accurately reflects the component's physical spread in the data space and gives proportionally more weight to the components that explain the most variance.

```python
weighted_loadings = np.abs(top_eigenvectors) * np.sqrt(top_variances)
raw_weights = np.sum(weighted_loadings, axis=1)
```

##### Post-Hoc Scale Correction
The block scaling in Section 2 transformed the input space: each stat was divided by `scale_factor = sqrt(k) / W_block` before the PCA ran. This means the eigenvectors live in the scaled space, not the raw Z-score space — they were calibrated against amplified or suppressed stats, not the original standardised values. At inference time the live engine applies weights to raw Z-scores, so a correction is required.

For each stat, the raw weight is divided by the same scale factor that was applied during preprocessing, then the full vector is renormalised:

$$w_{corrected, j} = \frac{w_{raw, j}}{s_j} \quad \text{where } s_j = \frac{\sqrt{k_{block(j)}}}{W_{block(j)}}$$

$$w_{final, j} = \frac{w_{corrected, j}}{\sum_j w_{corrected, j}}$$

```python
# Build scale factor array matching column order
col_order = scaled_pca_df.columns.tolist()
scale_factors_arr = np.ones(len(col_order))
for block_name, stats in blocks.items():
    k = len(stats)
    sf = np.sqrt(k) / philosophy[block_name]
    for stat in stats:
        scale_factors_arr[col_order.index(stat)] = sf

corrected_weights = raw_weights / scale_factors_arr
final_weights = corrected_weights / corrected_weights.sum()
```

The intuition: a stat in a heavily inflated block (e.g., Defending for a CB at $W_{block} = 3.0$) has a small `scale_factor` ≈ 0.577, meaning it was amplified roughly 1.73× before PCA. The raw weights from PCA reflect this amplification. Dividing by the small scale factor increases the corrected weight proportionally, correctly restoring the intended tactical emphasis in the raw Z-score space. Without this step, the final weights would be miscalibrated — they would appear to reflect the tactical philosophy but would under-deliver it when applied to unscaled live data.

The final normalised weight vector sums to 1.0 and accurately reflects the multidimensional tactical philosophy for the position without double-counting the underlying telemetry.

### 6. Derived Position Weights
Three positions — Wingbacks (LWB/RWB), Wide Midfielders (RM/LM), and Central Attacking Midfielders (CAM) — had insufficient match data in the historical dataset to support a reliable standalone PCA run. Running PCA on a small or unrepresentative sample risks producing unstable components whose loadings shift dramatically with minor dataset changes, making the derived weights unreliable. Introducing synthetic data carries its own calibration risks. Instead, these positions use a principled inheritance approach.

Each borrows the final weight vector of its closest tactical relative as a starting point:

|Derived Position|Proxy Base|
|---|---|
|Wingback (LWB/RWB)|Fullback (RB)|
|Wide Midfielder (RM/LM)|Winger (RW)|
|Central Attacking Midfielder (CAM)|Central Midfielder (CM)|

A set of per-stat multipliers is then applied to shift the emphasis toward the unique demands of the derived role. For example, Wingbacks inherit from Fullbacks but are expected to contribute far more in the final third — so their attacking and dribbling weights are scaled up, their defensive weights scaled down, and their sprint and xT weights scaled up to reflect higher physical and progressive involvement. Wide Midfielders inherit from Wingers but with heavier defensive duties, so tackling and possession won are upweighted. CAMs inherit from CMs with elevated attacking contribution and suppressed defensive involvement.

The full set of multipliers for each derived position is defined in the offline calibration notebook. After multipliers are applied, the weight vector is renormalised to sum to 1.0:

```python
derived_weights = {}
for stat, base_weight in proxy_weights.items():
    multiplier = position_multipliers.get(stat, 1.0)
    derived_weights[stat] = base_weight * multiplier

total = sum(derived_weights.values())
derived_weights = {k: v / total for k, v in derived_weights.items()}
```

The means and standard deviations used for Z-scoring these positions at inference time are derived from the proxy position's calibration data, adjusted using the same scaling assumptions. This is a deliberate approximation — the true positional distribution for these roles would ideally come from a dedicated dataset, but the tactical proximity of the base positions makes the inherited baselines a reasonable and stable substitute.