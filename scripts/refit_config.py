"""Refit the rating config from every career in ``datasets/`` in one step.

Overview
--------
The weights, means and stds in ``config/`` are fitted from the career data in
``datasets/`` (see ``workshop/lib/fit.py``). When you collect more matches, this script
takes you from the new export to a refreshed config in one command: it imports the
export (validating it and stripping stale ratings), refits every position on all
careers, checks the result, and reports how far the config moved and what that does to
ratings. Nothing in ``config/`` changes unless you pass ``--promote``.

Quick Start
-----------
Preview a refit of the data already in ``datasets/`` (changes nothing in ``config/``):

        uv run python scripts/refit_config.py

Import a newer export of a career (or a new career), then preview:

        uv run python scripts/refit_config.py --import C:/path/to/ipswich_3

Apply it (backs up the old config, writes the new one and its manifest, refreshes
the golden rating anchors and records the change):

        uv run python scripts/refit_config.py --import C:/path/to/ipswich_3 --promote

After promoting, run ``uv run pytest`` and refresh the validation notebooks with
``uv run python scripts/run_validation.py`` (or pass ``--validate`` to do it in one go).

What gets refitted
------------------
The six positions with enough data (CB, CDM, CM, Fullback, ST, Winger) are fitted on
every match of every career tagged ``pool``, with the rare-event floor
(``fit.RareEventPolicy``) so a stat with a handful of events cannot produce extreme
z-scores. The wing-back, wide-midfielder and CAM sections are derived from their
fitted proxies. The goalkeeper means/stds are carried over unchanged. The hand-set
bonus values (goal alpha, assist gamma, wasteful-finisher scale) live in the service
and are not touched.

Flags
-----
--import SOURCE
        Folder holding ``matches.json``, ``players.json`` and ``metadata.json``. Added
        as a new career, or applied as an update when the career already exists.

--careers
        Fit only these careers (default: every career tagged ``pool``).

--promote
        Apply the refit to ``config/`` (after validation), with a backup.

--validate
        With ``--promote``, re-run the validation notebooks against the new config
        afterwards (takes several minutes).

--no-rare-event-policy
        Fit without the rare-event floor (not recommended).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
for entry in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import json  # noqa: E402

import import_career  # noqa: E402
import regen_rating_anchors  # noqa: E402
import run_validation  # noqa: E402
from workshop.lib import fit, refit  # noqa: E402

CANDIDATE_DIR = refit.CANDIDATES_DIR / "latest"


def import_data(source: Path) -> int:
    """Import an export into ``datasets/`` as a new career or an update.

    Args:
        source (Path): Folder with the three career JSON files.

    Returns:
        int: Exit code from ``import_career`` (0 on success).
    """
    metadata = import_career.read_object(source / "metadata.json")
    name = str(metadata.get("folder_name", ""))
    exists = (PROJECT_ROOT / "datasets" / "careers" / name).is_dir()
    return import_career.main([str(source), *(["--update"] if exists else [])])


def floored_stats(result: fit.FitResult, candidate_dir: Path) -> list[str]:
    """List rare-event stats whose std was raised to the floor.

    Args:
        result (fit.FitResult): The fit.
        candidate_dir (Path): Directory holding the written candidate config.

    Returns:
        list[str]: One line per floored stat.
    """
    if result.policy is None:
        return []
    policy = fit.RareEventPolicy(**result.policy)
    means = json.loads((candidate_dir / fit.MEANS_STDS_FILE).read_text("utf-8"))
    lines = []
    for section, counts in sorted(result.rare_events.items()):
        for stat, events in counts.items():
            std = means[section][stat]["std"]
            if events > 0 and std == policy.floor_for(events):
                lines.append(
                    f"{section}.{stat}: {events} events, std held at {std:.4f}"
                )
    return lines


def main(argv: list[str] | None = None) -> int:
    """Run the import, refit, report and (optionally) promote steps.

    Args:
        argv (list[str] | None): Argument list, or None to use ``sys.argv``.

    Returns:
        int: 0 on success, 1 on any failure.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument(
        "--import", dest="source", type=Path, help="Export folder to import."
    )
    parser.add_argument(
        "--careers", nargs="+", help="Careers to fit (default: all pool)."
    )
    parser.add_argument("--promote", action="store_true", help="Apply to config/.")
    parser.add_argument(
        "--validate", action="store_true", help="Re-run the validation notebooks."
    )
    parser.add_argument("--no-rare-event-policy", action="store_true")
    args = parser.parse_args(argv)
    if args.validate and not args.promote:
        parser.error("--validate needs --promote (it validates the new config)")

    if args.source is not None and import_data(args.source.resolve()) != 0:
        print("Import failed; nothing was refitted.")
        return 1

    policy = None if args.no_rare_event_policy else refit.DEFAULT_POLICY
    result = refit.fit_all(args.careers, policy)
    fit.write_candidate(
        CANDIDATE_DIR, result, note="Refit from scripts/refit_config.py."
    )

    print("Fitted on:")
    for career, info in result.sources.items():
        ids = info["match_ids"]
        print(f"  {career}: matches {ids[0]}-{ids[1]} ({info['n_matches']})")
    print("Rows per position:", result.rows)
    floored = floored_stats(result, CANDIDATE_DIR)
    if floored:
        print("Rare-event stats held at the floor:\n  " + "\n  ".join(floored))

    print("\nMovement vs the live config:")
    print(refit.movement(refit.LIVE_DIR, CANDIDATE_DIR).round(4).to_string())
    print("\nEffect on outfield ratings (candidate minus live):")
    print(refit.rating_effect(refit.LIVE_DIR, CANDIDATE_DIR).round(3).to_string())

    problems = refit.validate_config(CANDIDATE_DIR)
    if problems:
        print("\nCANDIDATE NOT SOUND:\n  " + "\n  ".join(problems))
        return 1
    print(f"\nCandidate is sound and written to {CANDIDATE_DIR}.")
    if not args.promote:
        print("Preview only: config/ is unchanged. Re-run with --promote to apply it.")
        return 0

    info = refit.promote(CANDIDATE_DIR)
    record = refit.write_record(info, result)
    print(f"\nPromoted: {info['previous_hash'][:8]} -> {info['new_hash'][:8]}")
    print(f"Backup of the previous config: {info['backup']}")
    print(f"Record: {record}")
    print("\nRefreshing the golden rating anchors:")
    regen_rating_anchors.main([])
    if args.validate:
        print("\nRe-running the validation notebooks:")
        return run_validation.main([])
    print("\nNext: run `uv run pytest` and `uv run python scripts/run_validation.py`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
