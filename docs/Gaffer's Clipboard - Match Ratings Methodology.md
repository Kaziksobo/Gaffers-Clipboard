
> [!info] Executive Summary
> The native rating systems in modern football simulations are often volatile, occasionally punishing players for specific tactical instructions or inflating the scores of short substitute cameos. 
> 
> The Gaffer's Clipboard Analytics Engine circumvents this by calculating a bespoke, purely data-driven $0.0 - 10.0$ match rating based on raw performance data extracted via OCR. This document outlines the mathematical pipeline—from raw data normalization to dimensionality reduction and logistic scaling—used to evaluate player performances.

---

## Table of Contents & Modules

This whitepaper is modular by design. Read straight through for the high-level football philosophy, or explore the linked modules for the underlying mathematical proofs and Python architecture.

### I. Introduction and Philosophy
The limitations of native match ratings and the architectural constraints of building a lightweight, `numpy`-only analytics engine for offline execution.
![[01 - Introduction and Philosophy]]

### II. Data Pre-Processing & Normalization
How raw telemetry is cleaned before scoring. This includes volume masking for percentage stats, half-length standardization, and how [[Bayesian Smoothing]] safely handles substitute appearances.
![[02 - Data Pre-Processing and Normalization]]

### III. Contextual Adjustments
Adjusting raw volume metrics to reflect the reality of the match, including Possession Taxes and engineering an Expected Threat (xT) proxy without spatial tracking data.
![[03 - Contextual Adjustments]]

### IV. Dimensionality Reduction & Weighting
Why Min-Max scaling fails in football, the shift to Z-Score Standardization, and how [[PCA Block Scaling]] is used to derive fair, positional weight matrices without allowing attacking stats to dominate.
![[04 - Dimensionality Reduction]]

### V. The Scoring Algorithm
The core `MatchRatingsService` logic. How the dot product is calculated, the application of positional "Do No Harm" floors, and the [[Sigmoid Mapping]] function that compresses unbounded variance into a strict $0.0 - 10.0$ scale.
![[05 - The Scoring Algorithm]]

### VI. Macro-Context & Goalkeeper Isolation
Adjusting the final rating using the Match Supremacy Scalar ($\Delta_{xG}$) to account for team dominance, and why goalkeepers bypass the PCA matrix entirely.
![[06 - Macro-Context and Goalkeepers]]