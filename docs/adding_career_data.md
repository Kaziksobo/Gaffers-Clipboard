# Adding career data and refitting the config

How to take new matches from a career (for example 20 more Ipswich matches) through to a refreshed rating
config. Everything runs from the repository root. Nothing here reads or writes the app's live `data/` folder:
you work from a **copy** of a career folder.

## What you need

A full export of the career folder, copied somewhere outside the repo, containing:

- `matches.json`: **all** matches, including the ones already in the repo (not only the new ones);
- `players.json`;
- `metadata.json` (its `folder_name` names the career, e.g. `ipswich_3`).

For an update, the matches already in `datasets/careers/<career>/` must be unchanged and come first. The import
checks this (ignoring stored `match_rating`, which is stripped anyway).

## Steps

### 1. Dry-run the import (optional but cheap)

```powershell
uv run python scripts/import_career.py "C:\path\to\ipswich_3" --update --dry-run
```

Validates every file against the Pydantic models and the prefix rule above, and reports what would change.
Nothing is written.

### 2. Import and preview the refit

```powershell
uv run python scripts/refit_config.py --import "C:\path\to\ipswich_3"
```

- The **import is real**: it overwrites `datasets/careers/ipswich_3/*`, updates the match count in
  `datasets/careers.toml`, and strips stale stored ratings. `git diff` shows it.
- The **refit is a preview**: it fits every position on all matches of all careers into
  `workshop/calibration/candidates/latest/` and prints a report. `config/` is not touched.

### 3. Read the report

| Section | Look for |
|---|---|
| Fitted on | the career's range now ends at the new last match |
| Rows per position | wide midfielder, CAM and wing-back rows: from 85 rows a derived position starts blending in its own fit (and your philosophies in `fit.DIRECT_SPECS`) |
| Rare-event stats at the floor | stats still held at the std floor; the floor relaxes as events accumulate |
| Movement vs live config | weights, means (in live stds) and std ratios per section; large jumps deserve a look |
| Effect on ratings | mean and share of ratings that change, by career and position |

### 4. Promote

```powershell
uv run python scripts/refit_config.py --promote
```

Backs up the old config to `workshop/calibration/candidates/previous_<hash>/`, writes the new
`config/performance_weights.json`, `performance_means_stds.json` and `fit_manifest.json`, regenerates the golden
anchors (`tests/fixtures/golden/rating_anchors.json`, it prints how many changed) and writes a record to
`workshop/calibration/records/`.

Steps 2 to 5 in one command (import, promote, re-run the validation notebooks):

```powershell
uv run python scripts/refit_config.py --import "C:\path\to\ipswich_3" --promote --validate
```

### 5. Run the tests

```powershell
uv run pytest
```

Warnings to expect: sklearn's "covariance matrix is not full rank" (constant stats; harmless) and the OCR fixture
mismatch. Two warnings you should act on:

- "config is behind the datasets": a career has matches the config was not fitted on (promote, or run the refit).
- "validation notebook is stale": run step 6.

### 6. Refresh the validation notebooks

```powershell
uv run python scripts/run_validation.py          # about 8 to 10 minutes
uv run python scripts/run_validation.py --only 01 03   # or a subset
```

Each notebook starts with a header giving the config hash and data it ran on, and its narrative is computed from
the results, so nothing from the old config survives.

### 7. Commit

Suggested split:

1. the dataset files (`datasets/careers/<career>/*`, `datasets/careers.toml`);
2. the config (`config/*`, `tests/fixtures/golden/rating_anchors.json`, the new record in
   `workshop/calibration/records/`);
3. the refreshed notebooks in `workshop/validation/`.

## Rolling back

Copy `performance_weights.json`, `performance_means_stds.json` and `fit_manifest.json` from the
`previous_<hash>` backup over `config/` (or `git checkout` them), then:

```powershell
uv run python scripts/regen_rating_anchors.py
```

The dataset change is separate: `git checkout datasets/` undoes the import.

## A brand-new career

Leave out `--update`; the import detects a new `folder_name` and adds it with tags `ood` and `pool`
(override with `--tags`). Tags: `calibration` fits weights and anchors, `ood` is for out-of-distribution
checks, `pool` is eligible for the pooled fit. A career needs `pool` to be included in the refit.

## If the import fails

| Message | Meaning |
|---|---|
| a model validation error | the export doesn't match the app's schemas (wrong version or hand-edited) |
| existing matches differ | the first N matches of the export aren't the ones already in the repo; check you exported the same save |
| career exists | you left out `--update` (`refit_config.py --import` adds it for you) |

## Reference

| Script | Does |
|---|---|
| `scripts/import_career.py` | validate and import or update a career in `datasets/` |
| `scripts/refit_config.py` | import (optional), refit, report, promote |
| `scripts/regen_rating_anchors.py` | regenerate the golden anchors from the live config |
| `scripts/run_validation.py` | execute the validation notebooks |

More on how the fit works: `workshop/README.md`.
