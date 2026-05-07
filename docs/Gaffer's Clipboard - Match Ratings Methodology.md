
> [!info] Executive Summary
> The Quantification of a football performance into one number from 0.0 - 10.0 has long been a complex and controversial process, and is an exercise dimensionality reduction - reducing a web of complex and often inter-connected stats down to a single number. Industry standard algorithms like those used by Sofascore and Fotmob have made great progress in this, but are still viewed quite critically by fans, have inherent biases of their own, and operate like a black box with little transparency as to what they are actually analysing.
> 
> The Gaffer's Clipboard's Analytics Engine attempts to overcome these flaws with a transparent, mathematically rigorous 0.0 - 10.0 scale. While it has limitations of its own (being based on stats extracted from EA FC/FIFA screens), it operates completely offline to process match telemetry through a strict pre-processing pipeline with standardisations, dimensionality reduction and contextual heuristics to evaluate player performances exactly based on what unfolds on the pitch. This gives the user the best, most unbiased insights into how their players are performing

---

## I. Introduction and Philosophy
[Insert 3 paragraphs. Discuss the quantification of human athletic performance. Contrast commercial algorithms with your offline, NumPy-based approach. Explain the overarching goal: 0.0 - 10.0 scale.]

## II. Data Pre-Processing & Normalization
[Insert 1-2 paragraphs. Explain that raw OCR data is biased by match length and playing time.]

### Volume Masking and Temporal Standardization
[Insert 2 paragraphs. Explain the $H_{base} = 10.0$ baseline. Explain Volume Masking.]

### Handling Substitute Volatility (Bayesian Smoothing)
[Insert 2 paragraphs. Detail the "Substitute Problem." Introduce Bayesian Smoothing as the philosophical fix.]

> [!abstract]- 📐 Deep Dive: Bayesian Smoothing Architecture
> ![[02a - Bayesian Smoothing Architecture]]

## III. Live Feature Engineering & Standardization
[Insert 1-2 paragraphs. Explain deriving contextually aware features *before* applying weights.]

### The Expected Threat (xT) Proxy
[Insert 2 paragraphs. Explain engineering a dynamic proxy using verticality and distribution efficiency without XY data.]

### Live Z-Score Standardization
[Insert 2 paragraphs. Explain converting smoothed metrics into Z-Scores and inverting negative stats.]

## IV. Offline Weight Generation: Dimensionality Reduction
[Insert 2 paragraphs. Delineate the Offline Phase. We need historical data to know mathematically why a goal is worth more than a pass.]

### The Tangled Stats Problem
[Insert 2 paragraphs. Explain "Improper Linear Models" (e.g., clearances falsely correlating with wins). State that stats are grouped into tactical blocks to find their true value.]

> [!abstract]- 📐 Deep Dive: Offline Weight Generation & PCA
> ![[04a - Offline Weight Generation and PCA]]

## V. The Scoring Algorithm
[Insert 1-2 paragraphs outlining the `MatchRatingsService`. Explain how the live Z-scores from Section III finally meet the offline positional weights from Section IV via a dot product calculation.]

### Positional Modifiers and "Do No Harm" Floors
[Insert 3-4 paragraphs. This is pure football logic. Detail the "Do No Harm" floors for defenders. Explain your specific philosophical role protections (e.g., "Ghosting Forgiveness," "Third CB" bonus, "Black Hole Penalty").]

### Logistic Mapping
[Insert 2 paragraphs. Explain why the raw score cannot just be printed. Detail the necessity of the inverse Sigmoid function to elegantly squeeze an unbounded score onto a 0.0 - 10.0 scale.]

> [!abstract]- 📐 Deep Dive: Logistic Mapping Mathematics
> ![[05a - Logistic Mapping Mathematics]]

## VI. Macro-Context, Hybridization & Goalkeepers
[Insert 1-2 paragraphs. Address the final layers of the engine: team context, handling players who shift tactical roles mid-match, and the isolated goalkeeper heuristics.]

### The Match Supremacy Scalar
[Insert 2 paragraphs. Discuss the hierarchical variance of football (team dominance accounting for ~26% of variance). Explain the $\Delta_{xG}$ adjustment concept, and how it is applied to the logistic score.]

> [!abstract]- 📐 Deep Dive: The Match Supremacy Scalar
> ![[06a - The Match Supremacy Scalar]]

### Multi-Positional Hybridization
[Insert 2 paragraphs. Explain that modern players often change roles mid-game. State that the engine evaluates their entire match data through the lens of *every* position they played, generating a distinct final rating for each role. Explain why you blend these final ratings rather than just taking the highest one or a simple average.]

> [!abstract]- 📐 Deep Dive: The Alpha Drag Coefficient
> ![[06b - Multi-Position Alpha Drag]]

### Goalkeeper Isolation Heuristics
[Insert 2 paragraphs. Explain why goalkeepers bypass the PCA matrix entirely. Introduce the Expected Goals Prevented (xGP) heuristic.]

> [!abstract]- 📐 Deep Dive: Goalkeeper Heuristics
> ![[06c - Goalkeeper Heuristics]]