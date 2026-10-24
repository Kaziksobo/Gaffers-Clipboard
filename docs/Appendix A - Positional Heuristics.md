This appendix is the complete technical reference for all outfield positional modifiers as implemented in `match_ratings_service.py`. Values are sourced directly from the live code; no values are estimated or approximated.

### Universal Mechanisms
**Bottleneck Synergy** Every scaling bonus in the engine uses a bottleneck architecture. A bonus activates only when a player simultaneously exceeds a threshold across two paired metrics, and the scaling rate is driven by the weaker of the two:

$$\text{bonus} = R \times \bigl(\min(Z_A,\ Z_B) - T\bigr) \quad \text{when } \min(Z_A,\ Z_B) > T$$

A player who is elite in one metric but average in its pair receives no bonus until both are above the threshold. This prevents a single extraordinary stat from generating a reward while masking a deficiency in the complementary skill.

**Goal and Assist Multipliers** Goal bonuses are efficiency-adjusted rather than flat. The engine computes an _above-expected_ component using a crude 0.20 xG-per-shot estimate, with a per-goal floor ensuring scoring always contributes positively regardless of shot volume:
$$\text{above\_expected} = \max(\text{goals} - \text{shots} \times 0.20, \text{goals} \times 0.40)$$

$$\text{goal\_contribution} = \text{above\_expected} \times G_{pos}$$
Assist bonuses remain a flat multiplier: $\text{assist\_contribution} = \text{assists} \times A_{pos}$.

The **tactical isolation multiplier** derived in Phase III (Section V) is applied to goal and assist bonuses for all midfield and attacking positions (CDM, CM, CAM, WM, Winger, ST). If the player's average build-up Z-score falls below $-1.0$, this multiplier decays exponentially between 0 and 1, reducing bonuses for players statistically absent from the build-up phase. Defensive positions (CB, Fullback, Wingback) are not subject to the isolation multiplier.

**Efficiency Metrics** Percentage-based metrics (pass accuracy, shot accuracy, dribble success rate, tackle success rate) are regulated by the continuous logistic volume masking system described in Section III. They are not subject to universal hard floors in the positional modifier layer; only position-specific floors explicitly coded in the modifier are listed below.

---

### 1. Attackers

#### Striker (ST)

**Z-Score Floors**

|Metric|Floor|
|---|---|
|`tackles_p90_z`|$-0.50$|
|`tackle_success_rate_z`|$-0.50$|
|`possession_won_p90_z`|$-0.50$|
|`goals_p90_z`|$-2.00$ — Ghosting Forgiveness|
|`assists_p90_z`|$-2.00$ — Ghosting Forgiveness|
|`non_goal_shots_p90_z`|$-2.00$ — Ghosting Forgiveness|
|`offsides_p90_z`|$-1.50$ — Offside Forgiveness|

**Output Multipliers** Goal coefficient $G_{pos} = 1.5$, Assists $\times\ 1.1$ (both scaled by isolation multiplier).

**Complete Forward Bonus** Activates when $\min(\text{passes\_z},\ \text{dribbles\_z}) > 1.5$; scales at $+0.25$ per $\sigma$ above threshold.

**Wasteful Finisher Penalty** Assigns $0.20$ xG per shot. If shots $> 3$ and finishing deficit $> 0.75$: penalty $= \text{deficit} \times 0.25$, capped at $-0.80$.

**Black Hole Penalty** If possession lost $> 4$ and turnover ratio $> 1.5$: penalty $= \text{excess losses} \times 0.08$, capped at $-0.60$.

_Positive involvements = passes + dribbles + shots. Excess losses = possession lost − positive involvements._

**Target Man Bonus** If positive involvements $\geq 15$ and retention ratio $> 4.0$: bonus $= \text{excess retention} \times 0.02$, capped at $+0.40$.

_Excess retention = positive involvements − (possession lost $\times\ 3.0$)._

---

#### Winger (RW / LW)

**Z-Score Floors**

|Metric|Floor|
|---|---|
|`tackles_p90_z`|$-0.50$ — Defensive Absolution|
|`tackle_success_rate_z`|$-0.50$ — Defensive Absolution|
|`possession_won_p90_z`|$-0.50$ — Defensive Absolution|
|`fouls_committed_p90_z`|$-1.50$|
|`possession_lost_p90_z`|$-1.50$|
|`offsides_p90_z`|$-2.00$ — Offside Forgiveness|

**Output Multipliers** Goal coefficient $G_{pos} = 1.3$, Assists $\times\ 1.0$ (both scaled by isolation multiplier).

**Direct Threat Bonus** Activates when $\min(\text{dribbles\_z},\ \text{xt\_z}) > 1.5$; scales at $+0.25$ per $\sigma$ above threshold.

**Wide Playmaker Bonus** Activates when $\min(\text{passes\_z},\ \text{xt\_z}) > 1.5$; scales at $+0.20$ per $\sigma$ above threshold.

**High Press Bonus** Activates when $\min(\text{tackles\_z},\ \text{poss\_won\_z}) > 1.0$; scales at $+0.15$ per $\sigma$ above threshold.

**Wastefulness Penalty** If shots $\geq 3$ and goals $= 0$: penalty $= (\text{shots} - 2) \times 0.10$.

---

### 2. Midfielders

#### Central Attacking Midfielder (CAM)

**Z-Score Floors**

|Category|Metrics|Floor|
|---|---|---|
|Defensive|`tackles_p90_z`, `tackle_success_rate_z`, `possession_won_p90_z`|$-0.50$|
|Passenger|`passes_p90_z`, `dribbles_p90_z`, `non_goal_shots_p90_z`, `distance_covered_p90_z`, `distance_sprinted_p90_z`, `xt_bonus_p90_z`|$-1.00$|
|Detriment|`fouls_committed_p90_z`, `possession_lost_p90_z`, `offsides_p90_z`|$-1.50$|

**Output Multipliers** Goal coefficient $G_{pos} = 0.9$, Assists $\times\ 0.75$ (both scaled by isolation multiplier).

**Maestro Bonus** Activates when $\min(\text{passes\_z},\ \text{xt\_z}) > 1.5$; scales at $+0.25$ per $\sigma$ above threshold.

**Shadow Striker Bonus** Activates when $\min(\text{non\_goal\_shots\_z},\ \text{xt\_z}) > 1.5$; scales at $+0.20$ per $\sigma$ above threshold.

**Modern 10 Bonus** Activates when $\min(\text{tackles\_z},\ \text{poss\_won\_z}) > 1.0$; scales at $+0.25$ per $\sigma$ above threshold.

---

#### Central Midfielder (CM)

**Z-Score Floors** None applied in the positional modifier.

**Output Multipliers** Goal coefficient $G_{pos} = 1.0$, Assists $\times\ 0.75$ (both scaled by isolation multiplier).

**Enforcer Bonus** Activates when $\min(\text{tackles\_z},\ \text{poss\_won\_z}) > 1.5$; scales at $+0.25$ per $\sigma$ above threshold.

**Progression Engine Bonus** Activates when $\min(\text{passes\_z},\ \text{dribbles\_z}) > 1.2$; scales at $+0.25$ per $\sigma$ above threshold.

**Clean Sheet Bonus** Flat $+0.15$ if opponent goals $= 0$ and minutes $\geq 60$.

---

#### Central Defensive Midfielder (CDM)

**Z-Score Floors**

|Metric|Floor|
|---|---|
|`fouls_committed_p90_z`|$-1.00$ — Dark Arts Leniency|

**Output Multipliers** Goal coefficient $G_{pos} = 0.6$, Assists $\times\ 0.45$ (both scaled by isolation multiplier).

**Deep-Lying Playmaker Bonus** Mastery on $\min(\text{passes\_z},\ \text{dribbles\_z}) > 1.2$: $\min(\text{excess}, 2.0) \times 0.15 \times$ impact scalar, at most $+0.30$.

**Reliable Pivot** _(requires minutes $\geq 45$, pass accuracy $\geq 88\%$ and at least 15 passes)_

|Condition|Bonus|
|---|---|
|Possession lost $= 0$|$+0.30$ — Perfect Metronome|
|Possession lost $\leq 2$|$+0.20$ — Reliable Shift|

**Defensive Quality Bonus** _(replaces the old Destroyer mastery)_ Rewards an elite defensive game whatever the scoreline. A quality score $Q \in [0, 1]$ is the fitted-weight average of the position's defensive $z$-scores (tackles, tackle success, possession won, possession lost, passes, pass accuracy), mapped linearly from $0.28$ ($Q = 0$) to $0.84$ ($Q = 1$), and $Q = 0$ below 30 minutes. The bonus is $Q \times \text{impact scalar} \times 1.0 \times \text{retention}$, where retention depends on goals conceded:

|Goals conceded|0|1|2|3|4+|
|---|---|---|---|---|---|
|Retention|$1.0$|$1.0$|$0.6$|$0.2$|$0$|

Goals from low-quality chances (opponent xG at most half the goals conceded) retain a further $+0.1$. At most $+1.0$.

**Dynamic Clean Sheet Bonus** Opponent goals $= 0$, scaled by $\min(\text{minutes}, 60)/60$ and the position ratio (CDM $0.65$, so at most $+0.39$). The tiers deliberately pay more for clean sheets against weak attacks:

|Opponent xG|CB tier value (CDM pays $0.65\times$)|
|---|---|
|$\leq 1.0$|$+0.60$ — Defensive Dominance|
|$1.0$ to $2.0$|$+0.48$ — Standard|
|$\geq 2.0$|$+0.36$ — Held Under Siege|

**Collapse Penalty** Flat $-0.30$ if opponent goals $\geq 3$ and minutes $\geq 60$. Quality does not soften it.

---

#### Wide Midfielder (RM / LM)

**Z-Score Floors**

|Metric|Floor|
|---|---|
|`fouls_committed_p90_z`|$-1.50$|
|`possession_lost_p90_z`|$-1.50$|
|`offsides_p90_z`|$-1.50$|

**Output Multipliers** Goal coefficient $G_{pos} = 0.75$, Assists $\times\ 0.55$ (both scaled by isolation multiplier).

**Two-Way Engine Bonus** Activates when $\min(\text{passes\_z},\ \text{tackles\_z}) > 1.0$; scales at $+0.25$ per $\sigma$ above threshold.

**Wide Progressor Bonus** Activates when $\min(\text{xt\_z},\ \text{dribbles\_z}) > 1.0$; scales at $+0.20$ per $\sigma$ above threshold.

**Clean Sheet Bonus** Flat $+0.15$ if opponent goals $= 0$ and minutes $\geq 60$.

---

### 3. Defenders

#### Centre Back (CB)

**Z-Score Floors** None applied in the positional modifier.

**Output Multipliers** Goal coefficient $G_{pos} = 0.75$, Assists $\times\ 0.55$.

**Ball-Playing Defender Bonus** Mastery on $\min(\text{passes\_z},\ \text{dribbles\_z}) > 1.0$: $\min(\text{excess}, 2.0) \times 0.15 \times$ impact scalar, at most $+0.30$.

**Defensive Quality Bonus** _(replaces the old tackles-and-possession-won mastery)_ Rewards an elite defensive game whatever the scoreline. A quality score $Q \in [0, 1]$ is the fitted-weight average of the position's defensive $z$-scores (tackles, tackle success, possession won, possession lost), mapped linearly from $0.27$ ($Q = 0$) to $1.21$ ($Q = 1$), and $Q = 0$ below 30 minutes. The bonus is $Q \times \text{impact scalar} \times 1.0 \times \text{retention}$, where retention depends on goals conceded:

|Goals conceded|0|1|2|3|4+|
|---|---|---|---|---|---|
|Retention|$1.0$|$1.0$|$0.6$|$0.2$|$0$|

Goals from low-quality chances (opponent xG at most half the goals conceded) retain a further $+0.1$. At most $+1.0$.

**Dynamic Clean Sheet Bonus** Opponent goals $= 0$, scaled by $\min(\text{minutes}, 60)/60$ and the position ratio (CB $1.0$). The tiers deliberately pay more for clean sheets against weak attacks:

|Opponent xG|CB bonus|
|---|---|
|$\leq 1.0$|$+0.60$ — Defensive Dominance|
|$1.0$ to $2.0$|$+0.48$ — Standard|
|$\geq 2.0$|$+0.36$ — Held Under Siege|

**Collapse Penalty** Flat $-0.30$ if opponent goals $\geq 3$ and minutes $\geq 60$. Quality does not soften it.

---

#### Fullback (LB / RB)

**Conditional Z-Score Floors** The Tactical Instruction Floor is conditional on whether the Third CB archetype is active. The archetype is active when $\min(\text{tackles\_z},\ \text{poss\_won\_z}) > 1.0$.

|Metric|Third CB Active|Third CB Inactive|
|---|---|---|
|`dribbles_p90_z`|$0.00$ (lifted to neutral)|$-0.50$|
|`xt_bonus_p90_z`|$0.00$ (lifted to neutral)|$-0.50$|

**Output Multipliers** Goal coefficient $G_{pos} = 0.5$, Assists $\times\ 0.4$.

**Third CB Bonus** Activates when $\min(\text{tackles\_z},\ \text{poss\_won\_z}) > 1.0$; scales at $+0.25$ per $\sigma$ above threshold.

**Express Train Bonus** Activates when $\min(\text{sprint\_z},\ \text{xt\_z}) > 1.0$; scales at $+0.20$ per $\sigma$ above threshold.

**Wide Playmaker Bonus** Activates when $\min(\text{passes\_z},\ \text{dribbles\_z}) > 1.0$; scales at $+0.15$ per $\sigma$ above threshold.

**Dynamic Clean Sheet Bonus** Identical to CB logic.

**Collapse Penalty** Flat $-0.30$ if opponent goals $\geq 3$ and minutes $\geq 60$.

---

#### Wingback (LWB / RWB)

**Z-Score Floors** None applied in the positional modifier.

**Output Multipliers** Goal coefficient $G_{pos} = 0.75$, Assists $\times\ 0.55$.

**Relentless Engine Bonus** Activates when $\min(\text{sprint\_z},\ \text{xt\_z}) > 1.5$; scales at $+0.20$ per $\sigma$ above threshold.

**Two-Way Flank Bonus** Activates when $\min(\text{tackles\_z},\ \text{poss\_won\_z}) > 1.0$; scales at $+0.25$ per $\sigma$ above threshold.

**Dynamic Clean Sheet Bonus** Identical to CB logic. No collapse penalty.