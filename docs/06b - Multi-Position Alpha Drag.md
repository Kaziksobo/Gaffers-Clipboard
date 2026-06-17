### 1. The Telemetry Constraint (Blind Aggregation)
When a player plays multiple tactical roles in a single match, the engine receives an unpartitioned telemetry array ($T_{match}$). Because the system lacks temporal parsing (minutes played per position) and spatial parsing (event locations), it cannot isolate which specific statistics belong to which tactical role.

To bypass this blind aggregation, the algorithm executes Parallel Matrix Evaluation. It processes $T_{match}$ through $n$ distinct Positional Weight Vectors corresponding to the user's input, generating a set of positional ratings $R = {r_1, r_2, \dots, r_n}$.

### 2. Pre-Calculation: Mirror Pair Deduplication
Before the hybrid formula runs, the engine collapses lateral mirror pairs from the position list. The four bilateral pairs — LB/RB, LWB/RWB, LM/RM, and LW/RW — describe the same tactical role on opposite flanks. When both sides of a pair appear in the input, the lower-rated entry is dropped and only the higher-rated is retained.

This step prevents bilateral listings from artificially inflating the position count or distorting the drag calculation. A user who enters "CB, RB, LB" intends to describe a centre-back who covered both fullback positions, not a three-way hybrid; after deduplication the engine treats it as "CB, RB" (or whichever fullback side scored higher), which is the architecturally correct interpretation.

If the deduplication leaves only a single position, the hybrid formula is skipped entirely and that rating is returned directly as the final score.

### 3. The Alpha Drag Formula
To synthesise the deduplicated set $R$ into a single scalar without falling victim to maximum-value loopholes or punitive averaging, the engine identifies the maximum rating ($R_{max}$), the arithmetic mean ($R_{mean}$), and the minimum ($R_{min}$) across all retained positions.

The final hybrid score is:

$$R_{hybrid} = R_{max} - \underbrace{\alpha,(R_{max} - R_{mean})}_{\text{drag}} + \underbrace{\beta \times \max!\left(0,\ R_{min} - \tau\right)}_{\text{versatility bonus}}$$

**Drag term:** $\alpha$ is the dynamic drag coefficient (derived in Section 4). It pulls the final score from $R_{max}$ toward $R_{mean}$, holding the player partially accountable for weaker performances in secondary roles without collapsing to a punitive average.

**Versatility bonus:** $\beta = 0.15$ and $\tau = 6.5$. If the player's _worst_ positional rating exceeds the threshold, a small additive bonus fires proportional to the surplus above it. A player who is genuinely above average in every listed role demonstrates authentic positional intelligence — the engine rewards this rather than neutralising it through drag alone. The threshold is set above the 6.0 psychological baseline by half a point, so the bonus only activates when the player is credibly above average even at their weakest position.

### 4. The Dynamic Alpha Coefficient
Rather than hardcoding a fixed drag weight, the engine calibrates $\alpha$ dynamically based on the tactical relationship between the positions being hybridised.

Positional similarity is measured using **cosine similarity** between the z-scored historical stat mean profiles of the highest-rated position and each secondary position. Each position is represented by its mean stat values from the offline calibration data, centred and scaled against the cross-position distribution — capturing how each role's typical statistical footprint _deviates from the positional average_ rather than reflecting the raw magnitudes. This approach is independent of the weighting choices made during PCA and focuses purely on the characteristic statistical differences between tactical roles.

$$\cos(\theta) = \frac{\mathbf{z}_1 \cdot \mathbf{z}_2}{|\mathbf{z}_1|,|\mathbf{z}_2|}$$

where $\mathbf{z}_p$ is the z-scored stat mean profile for position $p$. Negative cosine values — produced by anti-correlated roles such as CB and ST — are clamped to zero: orthogonal or opposite positions generate no drag at all, leaving the hybrid rating at $R_{max}$.

The mean cosine similarity across all secondary positions scales the base drag coefficient:

$$\alpha = 0.50 \times \bar{\cos}(\theta)$$

```python
max_idx: int = int(np.argmax(calculated_ratings))
max_pos: str = positions_played[max_idx]
other_positions: list[str] = [
    p for i, p in enumerate(positions_played) if i != max_idx
]

mean_similarity: float = float(np.mean([
    self._positional_cosine_similarity(max_pos, p)
    for p in other_positions
]))
alpha: float = 0.50 * mean_similarity  # ALPHA_BASE = 0.50

r_max: float = max(calculated_ratings)
r_mean: float = float(np.mean(calculated_ratings))
r_min: float = min(calculated_ratings)

drag: float = alpha * (r_max - r_mean)
bonus: float = 0.15 * max(0.0, r_min - 6.5)
hybrid_rating: float = r_max - drag + bonus
```

**Why this matters — two contrasting cases:**

_Case A — Tactically Related Positions (e.g., CB and RB):_ Both stat profiles are characterised by high defensive output and modest attacking figures relative to the cross-position average. The profiles are closely aligned, producing a high cosine similarity (e.g., $\approx 0.80$). Alpha is therefore $0.50 \times 0.80 \approx 0.40$. The secondary RB rating exerts meaningful drag because it is a legitimate signal — the player's aggregate stats genuinely reflect how well they fulfilled the duties of both roles.

_Case B — Tactically Orthogonal Positions (e.g., CB and ST):_ The CB profile deviates from the cross-position average in the direction of high tackles and possession won but low goals and shots; the ST profile deviates in the opposite direction. The profiles are anti-correlated, producing a cosine value near zero (clamped to $0.0$). Alpha collapses to $0.50 \times 0.00 = 0.00$. The secondary ST rating contributes nothing to the hybrid. This is correct — the unpartitioned CB statistics are guaranteed to generate a poor ST rating not because the player performed badly as a striker, but because the aggregate telemetry was never designed to be evaluated through a striker's weight matrix. Allowing that artefact rating to drag the true CB performance would be a mathematical injustice.

The dynamic calibration therefore ensures that the Alpha Drag system rewards genuine positional intelligence — correctly penalising a player who was tactically responsible for a closely related secondary role while protecting players from phantom drag generated by an orthogonal position assignment they spent minimal time fulfilling.