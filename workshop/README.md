# Workshop

Calibration and validation of the rating algorithm. Everything here reads career data from `datasets/` and
the rating service from `src/`; nothing in `src/` is modified by the tooling, and nothing reads or writes the
app's live `data/` folder.

## Adding new data and refreshing the config

Full step-by-step guide: [`docs/adding_career_data.md`](../docs/adding_career_data.md). In short:

Collected more matches (say 20 more Ipswich ones)? From the repository root:

```
uv run python scripts/refit_config.py --import C:/path/to/ipswich_3            # preview
uv run python scripts/refit_config.py --import C:/path/to/ipswich_3 --promote  # apply
uv run python scripts/run_validation.py                                         # refresh the validation notebooks
```

`--import` points at the folder the app writes (`matches.json`, `players.json`, `metadata.json`). The script
works out whether it is a new career or an update, validates it (models, ids, club, half length, and that
existing matches are unchanged), strips stale stored ratings, and updates `datasets/careers.toml`. It then refits
**every position on all matches of all careers**, checks the result, and prints:

- the careers and match ranges fitted on, and the rows per position;
- rare-event stats held at the std floor, and how far each derived position is from its own fit;
- how far each section moved from the live config (weights, means in units of the live std, std ratios);
- what that does to ratings by career and position.

Without `--promote` nothing in `config/` changes. With it the script backs up the old config to
`workshop/calibration/candidates/previous_<hash>/`, writes the new weights, means/stds and `config/fit_manifest.json`,
refreshes the golden rating anchors (`tests/fixtures/golden/`), and writes a record to `workshop/calibration/records/`.
Then run `uv run pytest` (a warning reminds you if the config is behind the datasets or the validation notebooks
are behind the config).

To roll back: copy the three files from the backup folder over `config/` (or `git checkout` them), then
`uv run python scripts/regen_rating_anchors.py`.

## What the refit does

- **Fitted** on the pooled data (`lib/fit.py`): CB, CDM, CM, Fullback (RB/LB), ST, Winger (RW/LW), and the goalkeeper
  heuristic's mean and std. `tests/data/test_workshop_fit.py` refits the recorded sources and checks the live config is
  reproduced exactly.
- **Derived, then blended into their own fit as data accumulates:** wing-backs (from Fullback), wide midfielders (from
  Winger) and CAM (from CM) start as their proxy times hand-set multipliers (`fit.DERIVED`). Once a position has
  `DirectFitPolicy.min_rows` (85) rows its own fit blends in, reaching full weight at 250. The own-fit specs and
  philosophies are in `fit.DIRECT_SPECS`; **they are placeholders copied from the proxies**, to be set to the role's own
  values before the blend carries real weight.
- **Anchored inputs** (`inputs/anchored_means_stds.json`, `inputs/pos_shares.json`) come from the calibration repo and are
  not refitted. About a third of each position's stats are anchored; the rest take their mean and std from the pooled rows.
- **Rare-event floor** (`fit.RareEventPolicy`): goals, assists and offsides with few events get a floor under their std
  (0.08 up to 10 events, falling to zero by 50), so one event cannot produce an extreme z-score.
- **Hand-set bonus values** (goal alpha, assist gamma, wasteful-finisher scale, goalkeeper floors and bonuses) are constants in
  `src/services/analytics/match_ratings_service.py` and are changed by hand.

## The validation suite

`uv run python scripts/run_validation.py [--only 01 03]` executes the notebooks in `validation/` against the live config and
current data and saves their outputs. Each starts with a header giving the config hash and data it ran on, and its
narrative is computed from the results, so a re-run replaces every number and sentence; nothing from an earlier config is
kept.

| Notebook | Question |
|---|---|
| `00_fit_stability` | Does the fitting procedure generalise? Leave-one-career-out: how far folds move, how closely out-of-sample ratings agree, non-inferiority at tracking results, how close derived positions are to their own fit |
| `01_construct_validity` | Do ratings track match results, in-sample and out-of-sample, at team, player and position level, and does the supremacy scalar remove xG coupling? |
| `02_distributions` | What does the output look like (minutes, supremacy, by career, goalkeepers), is the scale comparable across positions, what are the ceilings? |
| `03_goal_rescue` | Does a goal paper over a bad performance? |
| `04_reliability` | Is a rating stable under off-by-one input noise (ICC), by position and for goalkeepers? |
| `05_sensitivity` | Which hand-set constants actually move ratings? |

Out-of-sample evidence comes from `lib/crossval.py`: for each career, a config fitted on all the others rates it.

## Layout

| Path | What |
|---|---|
| `validation/` | The validation suite above |
| `lib/datasets.py`, `lib/rating.py` | Load careers as frames; recompute ratings with the live (or a candidate) config |
| `lib/fit.py`, `lib/refit.py`, `lib/crossval.py` | The fit, rare-event and direct-fit policies, promotion, leave-one-career-out |
| `lib/gate.py`, `lib/inference.py`, `lib/reliability.py`, `lib/sweep.py`, `lib/decompose.py`, `lib/variants.py`, `lib/report.py` | Analysis helpers |
| `calibration/` | Candidate configs (not tracked) and records of promotions |
| `inputs/` | The external fit inputs: `anchored_means_stds.json` and `pos_shares.json` (from the calibration repo) |
| `ratings_creation/` | `attribution_lib.py` (used by `scripts/full_attribution_report.py`) and the unused, stale pre-refit `position_*.json` |
