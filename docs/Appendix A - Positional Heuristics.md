This appendix serves as the complete technical glossary and tuning manual for all outfield roles.

(Note: Unless otherwise specified, an "Efficiency Floor" is applied universally to `tackle_success_rate`, `pass_accuracy`, `dribble_success_rate`, and `shot_accuracy`, capping negative variance strictly at $-0.75\sigma$.)

**1. Attackers (ST, RW, LW)**

- **Striker (ST):**
    
    - _Ghosting Forgiveness:_ Goals, assists, and shots are floored at $-2.0\sigma$.
        
    - _Offside Leniency:_ Offsides are floored at $-1.5\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+1.2$, and assists by $+0.6$.
        
    - _Complete Forward Bonuses:_ Elite passing ($>2.0\sigma$) yields $+0.20$ per $\sigma$ over the threshold. Elite dribbling ($>2.0\sigma$) yields $+0.20$ per $\sigma$.
        
    - _Wasteful Finisher Penalty:_ Assigns $0.20$ xG per shot. If a striker takes $>3$ shots and generates a finishing deficit $>0.75$, a penalty of $0.25 \times \text{Deficit}$ is applied (capped at $-0.8$).
        
    - _Black Hole Penalty:_ If possession is lost $>4$ times with a turnover-to-involvement ratio $>1.5$, a penalty of $0.08 \times \text{Excess Losses}$ is applied (capped at $-0.6$).
        
    - _Target Man Bonus:_ If positive involvements are $\geq 15$ and retention ratio is $>4.0$, a bonus of $0.02 \times \text{Excess Retention}$ is applied (capped at $+0.4$).
        
- **Wingers (RW/LW):**
    
    - _Defensive Absolution:_ Tackles, tackle success, and possession won are floored at $-0.5\sigma$.
        
    - _Detriment Floors:_ Fouls committed floored at $-1.5\sigma$; offsides floored at $-2.0\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.8$, assists by $+0.6$.
        
    - _Elite Outlier Bonuses:_ Dribbles $>2.0\sigma$ yield $+0.25$ per $\sigma$ . xT $>2.0\sigma$ yields $+0.20$ per $\sigma$. Passes $>2.0\sigma$ yield $+0.20$ per $\sigma$.
        
    - _High Press Bonus:_ Tackles $>1.5\sigma$ yield $+0.10$ per $\sigma$.
        
    - _Wastefulness Penalty:_ If a winger registers $\geq 3$ shots and $0$ goals, a penalty of $-0.10$ per shot over 2 is applied.
        

**2. Midfielders (CAM, CM, CDM, WM)**

- **Central Attacking Midfielder (CAM):**
    
    - _Defensive Exemption:_ Tackles, tackle success, and possession won floored at $-0.5\sigma$.
        
    - _Passenger Floor:_ Passes, dribbles, shots, distance covered, sprint distance, and xT floored at $-1.0\sigma$.
        
    - _Detriment Floor:_ Fouls, possession lost, and offsides floored at $-1.5\sigma$.
        
    - _Z-Score Capping:_ Standardized goals and assists cannot exceed $+2.0\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.7$, assists by $+0.9$.
        
    - _Maestro Bonus:_ Passes $>1.0\sigma$ AND xT $>1.5\sigma$ yield a flat $+0.40$.
        
    - _Shadow Striker Bonus:_ Shots $>1.5\sigma$ yield $+0.10$ per $\sigma$.
        
    - _Risky Creator Bonus:_ Pass accuracy $>1.0\sigma$ AND possession lost $>1.0\sigma$ yield a flat $+0.15$.
        
    - _Modern 10 Bonus:_ Tackles $>1.0\sigma$ AND possession won $>1.0\sigma$ yield a flat $+0.50$.
        
- **Central Midfielder (CM):**
    
    - _Attacking Floor:_ Goals, assists, shots, and shot accuracy floored at $0.0\sigma$.
        
    - _Z-Score Capping:_ Standardized goals and assists cannot exceed $+1.5\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.8$, assists by $+0.6$.
        
    - _Box-to-Box Scaling:_ Tackles $>2.0\sigma$ yield $+0.20$ per $\sigma$. Possession won $>2.0\sigma$ yields $+0.40$ per $\sigma$. Passes $>2.0\sigma$ yield $+0.40$ per $\sigma$. Dribbles $>2.0\sigma$ yield $+0.20$ per $\sigma$.
        
    - _Clean Sheet Bonus:_ Flat $+0.15$ if the team concedes $0$ goals and the player logged $\geq 60$ minutes.
        
- **Central Defensive Midfielder (CDM):**
    
    - _Attacking Floor:_ Goals, assists, shots, and shot accuracy floored at $0.0\sigma$.
        
    - _Detriment Floor:_ Fouls committed floored at $-1.0\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.5$, assists by $+0.4$.
        
    - _Defensive Dominance:_ Tackles $>2.0\sigma$ yield $+0.25$ per $\sigma$. Possession won $>2.0\sigma$ yields $+0.25$ per $\sigma$.
        
    - _Passing Prowess:_ Passes $>2.0\sigma$ yield $+0.35$ per $\sigma$.
        
    - _Reliable Shift:_ If minutes $\geq 60$ AND possession lost is $0$, yields a flat $+0.20$.
        
    - _Clean Sheet Bonus:_ Flat $+0.20$ if minutes $\geq 60$ AND $0$ goals conceded.
        
- **Wide Midfielder (RM/LM):**
    
    - _Attacking Floor:_ Goals, assists, shots, and shot accuracy floored at $-0.5\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.6$, assists by $+0.8$.
        
    - _Two-Way Engine Bonus:_ Passes $>1.0\sigma$ AND tackles $>1.0\sigma$ yield a flat $+0.40$.
        
    - _Wide Progression Bonus:_ xT $>1.5\sigma$ yields $+0.15$ per $\sigma$.
        

**3. Defenders (CB, FB/WB, LWB/RWB)**

- **Center Back (CB):**
    
    - _Attacking Floor:_ Goals, assists, shots, and shot accuracy floored at $0.0\sigma$.
        
    - _Professional Foul Leniency:_ Fouls committed floored at $-2.0\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.6$, assists by $+0.4$.
        
    - _Dominance Bonus:_ Tackles $>2.0\sigma$ yield $+0.25$ per $\sigma$. Possession won $>2.0\sigma$ yields $+0.25$ per $\sigma$. Passes $>1.5\sigma$ yield $+0.30$ per $\sigma$.
        
    - _Dynamic Clean Sheet:_ Bonus scales inversely with opponent xG. Max bonus ($+0.5$) for $\leq 1.0$ xG. Min bonus ($+0.15$) for $\geq 2.0$ xG. Standard bonus ($+0.35$) for all other clean sheets.
        
    - _Collapse Penalty:_ Flat $-0.3$ penalty if the team concedes $\geq 3$ goals and the player logged $\geq 60$ minutes.
        
- **Fullback (LB/RB):**
    
    - _Attacking Floor:_ Goals, assists, shots, and shot accuracy floored at $0.0\sigma$.
        
    - _Tactical Instruction Floor:_ Dribbles, xT, distance covered, and sprint distance floored at $-0.50\sigma$.
        
    - _Foul Leniency:_ Fouls committed floored at $-1.5\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.4$, assists by $+0.6$.
        
    - _The "Third CB" Archetype:_ Tackles $>1.5\sigma$ yield $+0.15$ per $\sigma$. Possession won $>1.5\sigma$ yields $+0.15$ per $\sigma$.
        
    - _The "Express Train" Archetype:_ Distance covered $>1.5\sigma$ yields $+0.10$ per $\sigma$. Sprint distance $>1.5\sigma$ yields $+0.10$ per $\sigma$ . xT $>1.5\sigma$ yields $+0.15$ per $\sigma$.
        
    - _Creativity Bonus:_ Passes $>2.0\sigma$ yield $+0.15$ per $\sigma$. Dribbles $>1.5\sigma$ yield $+0.15$ per $\sigma$.
        
    - _Clean Sheet / Collapse:_ Identical to CB logic.
        
- **Wingback (LWB/RWB):**
    
    - _Attacking Floor:_ Goals, assists, shots, and shot accuracy floored at $0.0\sigma$.
        
    - _Active Detriment Cap:_ Fouls and possession lost floored at $-1.5\sigma$.
        
    - _Passenger Cap:_ Passes, dribbles, tackles, possession won, distance covered, sprint distance, and xT floored at $-1.0\sigma$.
        
    - _Direct Output Multipliers:_ Raw goals are multiplied by $+0.6$, assists by $+0.8$.
        
    - _Physical / Progression Bonuses:_ Distance covered $>1.5\sigma$ yields $+0.15$ per $\sigma$. Sprint distance $>1.5\sigma$ yields $+0.15$ per $\sigma$ . xT $>1.5\sigma$ yields $+0.20$ per $\sigma$.
        
    - _Two-Way Synergy:_ Tackles $>1.0\sigma$ AND possession won $>1.0\sigma$ yield a flat $+0.35$.
        
    - _Clean Sheet:_ Identical to CB logic.