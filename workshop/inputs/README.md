# Fit inputs

Real-world reference data that `workshop/lib/fit.py` reads on every refit. It comes from the calibration
repository and is not refitted here:

- `anchored_means_stds.json`: per-position means and stds for the stats anchored to real-world data (about a
  third of each position's stats).
- `pos_shares.json`: the share of goals and assists scored by each position, used as the prior mean for the
  goals and assists stats.
