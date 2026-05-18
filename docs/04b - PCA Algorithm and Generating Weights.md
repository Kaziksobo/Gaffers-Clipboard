### 1. Tactical Block Scaling
Before computing the covariance matrix, the engine receives an $N \times 17$ matrix of standardised Z-scores. However, it must restructure this raw data to account for two distinct architectural hazards: structural size bias and blind variance optimisation.

First, the 16 metrics are natively grouped into tactical blocks. Without scaling these blocks at all, blocks with more features (e.g., _Attacking_ has 4 stats) artificially inject more variance into the dataset than smaller blocks (e.g., _Safety_ has 1 stat), biasing the PCA to favour large blocks regardless of tactical importance.

Secondly, if standard PCA is left entirely unguided, it will blindly extract whichever metrics hold the highest variance. For example, there may be a lot of variance in defensive midfielders' shooting: in some matches, they may be pinned back, unable to get forward, whilst against weaker teams, they may have much more license to get forward. Standard PCA would therefore give CDM's shooting a massive weight simply because shooting variance is historically very volatile, even though shooting should not make up a big part of how good a CDM's performance was; aspects like passing and tackling are much more important.

To resolve this, the engine applies a **Guided Variance Transformation**. The developer defines a macro-philosophy dictionary that assigns a structural multiplier to each tactical block based on the specific positional mandate.

```python
# The Baseline Configuration Schema 
blocks = {
	"Attacking": [
		"goals_p90_z", "assists_p90_z", "shots_p90_z", "shot_accuracy_z"
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
# Example: The CDM Macro-Philosophy
cdm_philosophy = {
    "Attacking": 1.0,
    "Passing": 2.5,
    "Dribbling": 0.6,
    "Safety": 1.4,
    "Defending": 2.4,
    "Workrate_and_Threat": 0.4,
    "Tactical_Discipline": 1.0,
}
```

When iterating through the Z-scores DataFrame, the engine identifies the number of stats within the current block ($k$) and queries the philosophy dictionary for the assigned macro-multiplier ($W_{block}$). It then scales every individual stat ($X_z$) within that block using the following formula:

$$X_{scaled} = X_z \times \frac{W_{block}}{\sqrt{k}}$$
By dividing by $\sqrt{k}$, the engine establishes a neutral baseline, ensuring the 4-stat _Attacking_ block does not mathematically overpower the 1-stat _Safety_ block simply by possessing more columns. Simultaneously, multiplying by $W_{block}$ artificially dilates or compresses the variance of specific tactical zones _before_ the PCA analyzes the matrix. For a CDM, artificially inflating the _Defending_ and _Passing_ variance forces the downstream eigen-decomposition to prioritize those exact traits when constructing the principal components.

### 2. Robust Covariance Estimation and the MCD Algorithm
Standard PCA relies on a traditional sample covariance matrix to map the relationships between metrics. However, the standard covariance formula is highly sensitive to extreme outliers because it calculates the variance using the arithmetic mean ($\bar{x}$) of the entire dataset ($n$): $$ C_{j,k} = \frac{1}{n-1} \sum_{i=1}^{n} (x_{ij} - \bar{x}_j)(x_{ik} - \bar{x}_k) $$
In a video game simulation environment, football data frequently contains multi-sigma anomalies - such as a player scoring 4 goals from 0.5 xG, or a glitch in telemetry logging impossible physical stats. Because the standard formula squares the deviations from the mean, these extreme, unrepresentative performances heavily skew the matrix, warping the resulting principal components toward the outliers rather than the sustainable tactical baseline.

To establish algorithmic stability, the engine explicitly rejects the standard sample covariance in favour of the **Minimum Covariance Determinant (MCD)** estimator.

To understand MCD, visualise the dataset as a matrix where every row represents a single match performance. Standard covariance calculates variance using every single row. The MCD algorithm, dictated by the `support_fraction=0.98` parameter, is instructed to deliberately throw away 2% of those rows to find a "clean" core dataset. 
Mathematically, $H$ represents this clean subset of surviving rows. Because the algorithm does not initially know _which_ rows are the anomalies, it must hunt for them. It mathematically evaluates thousands of different combinations of keeping 98% of the rows and discarding 2%. For every potential combination ($H$), it calculates the determinant of its covariance matrix ($C_H$). Geometrically, the determinant measures spatial volume; a lower determinant means the data points are packed more closely together. The algorithm's objective is: $$ \min_{H} \det(C_H) $$In plain English: The algorithm searches for the specific combination of rows ($H$) that yields the lowest possible spatial volume. By minimising the determinant, the algorithm actively isolates the tightest, most consistent 98% cluster of match performances. The 2% of rows that cause the data ellipsoid to stretch or distort significantly are identified as anomalies and discarded.
The robust covariance matrix ($C_{MCD}$) is then computed exclusively from the clean rows inside $H$, ensuring the downstream math is mathematically immunized against telemetry glitches.$$ C_{MCD} = \frac{1}{h-1} \sum_{i \in H} (x_i - \mu_{MCD})(x_i - \mu_{MCD})^T $$
The Python implementation utilizing `scikit-learn`: 
```python 
# support_fraction=0.98 defines subset 'h' as 98% of 'n' 
mcd = MinCovDet(random_state=42, support_fraction=0.98).fit(scaled_pca_df) cov = mcd.covariance_
```
By substituting $C_{MCD}$ in place of standard covariance, the engine ensures that the downstream eigen-decomposition is built strictly on sustainable, repeatable football logic, mathematically immunising the positional weights against telemetry glitches and statistical anomalies.

### 3. Eigen-Decomposition and Dimensional Truncation 
With a robust covariance matrix ($C_{MCD}$) established, the algorithm executes eigen-decomposition. This is a linear algebra operation that rotates the standard coordinate system to align exactly with the axes of maximum variance in the dataset. The fundamental equation of eigen-decomposition is: $$ C_{MCD} \mathbf{v}_i = \lambda_i \mathbf{v}_i $$
For a $17 \times 17$ covariance matrix, this extracts 17 pairs of eigenvalues ($\lambda_i$) and eigenvectors ($\mathbf{v}_i$):
* **The Eigenvectors ($\mathbf{v}_i$):** These are the directional vectors. In football terms, each eigenvector represents a distinct tactical profile (e.g., "Possession Dominance" or "Defensive Action"). The values inside the vector dictate the recipe of stats required to execute that profile. 
* **The Eigenvalues ($\lambda_i$):** These represent magnitude. Specifically, the eigenvalue defines the exact amount of variance that its corresponding tactical profile explains within the dataset.

The engine sorts these components in descending order by eigenvalue, ranking the tactical profiles by statistical importance. It then applies dimensional truncation, deliberately retaining only the top 9 components ($k=9$).
This truncation is a critical filtering mechanism. The top 9 components account for approximately 85% of the dataset's total tactical variance. The remaining 15% is discarded because the lower-ranked components represent statistical noise - highly specific, mathematically unstable correlations that do not consistently define player performance.

### 4. Vector Reassembly and Normalisation 
At this stage, the engine holds a $17 \times 9$ matrix (17 stats distributed across 9 independent tactical profiles). It must collapse this matrix back into a single 1D positional weight vector.
For every stat ($j$), the engine iterates through the 9 retained components. It extracts the stat's internal weight within the component ($v_{j,i}$), and scales it by the square root of the component's eigenvalue ($\sqrt{\lambda_i}$). 

Two mathematical decisions here are paramount: 
1. **Absolute Values ($|v|$):** The sign (positive/negative) of an eigenvector is mathematically arbitrary; it only indicates direction along the axis. Taking the absolute value ensures the algorithm captures the true *magnitude* of the stat's influence on the tactical profile. 
2. **Square Root Scaling ($\sqrt{\lambda}$):** Because eigenvalues ($\lambda$) represent variance, taking the square root converts them to standard deviation. Scaling the weights by standard deviation accurately reflects the component's actual physical spread in the data space. 

The mathematical aggregation to find the raw weight ($w_{raw}$) for a specific stat ($j$) is: $$ w_{raw, j} = \sum_{i=1}^{k} |v_{j,i}| \sqrt{\lambda_i} $$ The exact Python implementation mapping to this logic: 
```python
# Scale absolute eigenvectors by the square root of their explained variance
weighted_loadings = np.abs(top_eigenvectors) * np.sqrt(top_variances)
# Sum across the components to create a 1D vector (length 17) 
raw_weights = np.sum(weighted_loadings, axis=1)
# Normalize the final vector to sum to 1.0 
final_weights = raw_weights / np.sum(raw_weights)
```

Finally, the engine normalises the 17 raw weights by dividing each by the total sum of the array. This yields the final Positional Weight Vector, which sums to $1.0$ and accurately reflects the multidimensional nature of the role without double-counting the underlying telemetry.