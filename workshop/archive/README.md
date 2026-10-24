# Archive: retired notebooks, pending removal

Everything in this folder is retired and nothing depends on it. It is a holding area, not a
record: the files are here only because tooling never deletes anything, so they wait for the
owner to remove them. Their stored outputs and prose describe earlier algorithms, configs
and data, and many no longer run.

To remove it all: `git rm -r workshop/archive`, then delete the leftover untracked files
(`holdout_gate.ipynb`, `holdout_gate_arsenal.json`, and any other untracked notebooks).
Afterwards tidy the four references to it: the docstrings in `scripts/full_attribution_report.py`
and `workshop/ratings_creation/attribution_lib.py`, the layout row in `workshop/README.md`,
and the workshop paragraph in `CLAUDE.md`.

| Archived | Replaced by | Status against the current service |
|---|---|---|
| `rating_predictive_validity` | `validation/01_construct_validity` | Runs (reads ratings via `stamp_current_ratings`); superseded by the pooled, vectorised version. |
| `rating_sensitivity` | `validation/05_sensitivity` | 19 of the first 109 cells fail (the rest were not run): subclasses override `_apply_pos_modifiers` with a pre-Phase 9 signature. The tornado covers class constants only. **Not covered by the tornado and only here:** Bayesian smoothing d, the sigmoid k, the supremacy scalar, the Dirichlet weight perturbation. |
| `rating_output_diagnostics` | `validation/02_distributions` (Part A) | Runs. |
| `rating_scale_comparability` | `validation/02_distributions` (Part B) | Fails: hooks a method whose return type changed in Option A. |
| `rating_ceiling_comparability` | `validation/02_distributions` (Part C) | Fails: capture hook uses a pre-Phase 9 signature. The structural-ceiling method (synthetic P95 z-scores plus hand-copied Phase 8 caps) was retired, not ported. |
| `goal_rescue_investigation` | `validation/03_goal_rescue` | Fails: Phase 7 constants such as `GOAL_FLOOR_RATE` no longer exist. Kept as the Phase 7 evidence behind the goal-bonus redesign. |
| `rating_attribution` | `scripts/full_attribution_report.py` + `ratings_creation/attribution_lib.py` | Walkthrough that the script mirrors; its docstrings point here. |
| `option_a_baseline` | `validation/02_distributions` (Part B, via `lib/decompose.py`) | Fails: subclasses `_apply_pos_modifiers` with a pre-Phase 9 signature. Phase 8 record of the base-rating distribution before any bonus design. |
| `option_a_bonus_calibration` | `lib/sweep.py` + `rating_sensitivity_tornado` | Fails, same cause. The Phase 8 record of how the post-sigmoid bonus parameters were chosen; the bonus formulas have since changed (Phase 9). |
| `goal_rescue_retuning` | `validation/03_goal_rescue` | Fails, same cause. Phase 7 sweep of `coeff_multiplier` and `s_min`, constants of a mechanism that no longer exists in `src/`. |
| `cb`, `cdm`, `cm`, `fullback`, `st`, `winger` `_weights_calculations` | `workshop/lib/fit.py` (`fit_positions`), run by `scripts/refit_config.py` | Run (about 10 s each) and reproduced exactly by `fit.py` from Valencia 1-155. They wrote only the workshop `position_*.json`, never `config/`, and loaded every Valencia match. The CM notebook has the fullest narrative of the method. |
| `unknown_pos_weights_calculations` | `fit.derive_sections` | Runs. The markdown holds the reasoning behind each wing-back, wide-midfielder and CAM multiplier. |
| `gk_ratings_calculations` | `fit.fit_gk` | Runs. Its write step was commented out; the config's GK mean/std turned out to be exactly the heuristic over Valencia's first 100 matches. |
| `compute_ns_quality_stats` | none | Runs, but computed the Phase 7 `NS_QUALITY_STATS`, which no longer exist in `src/`. |
| `ratings_testing` | `tests/data/` (invariants, anchors, compatibility) | Stress tests superseded by the pytest data layer. |
| `rating_construct_validity`, `rating_distributions`, `rating_goal_rescue`, `rating_reliability`, `rating_sensitivity_tornado` (the consolidated pre-refit versions) | `validation/01`, `02`, `03`, `04`, `05` | Hold results from the config and hand-set values before the all-careers refit (config `d9d11fa2`). Superseded; the new suite recomputes everything from the live config. The old construct-validity notebook now fails (it assumes some matches are out-of-sample). Safe to `git rm`. |
| `holdout_gate` and `holdout_gate_arsenal.json` | `validation/00_fit_stability` | The one-off check that fitting on Valencia and Ipswich holds up on Arsenal, run before the final fit (it passed). Its baseline is the pre-refit config; re-running it now would compare against a config that already contains Arsenal. |
