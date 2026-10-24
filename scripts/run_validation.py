"""Run the validation notebooks against the live config and data, saving their outputs.

Overview
--------
The notebooks in ``workshop/validation/`` validate the whole rating algorithm: that
the fit generalises, that ratings track results, what the output looks like, whether
goals distort it, whether it is stable, and which constants matter. Each starts with a
header stating the config hash and data it ran on, and its narrative is computed from
the results, so a re-run after new data or a refit replaces every number and sentence.
Nothing from an earlier config is kept.

Quick Start
-----------
Run the whole suite (in order, saving outputs into the notebooks):

        uv run python scripts/run_validation.py

Run a subset by name prefix:

        uv run python scripts/run_validation.py --only 01 03

The exit code is non-zero if any notebook has an error cell.
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

import nbformat
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALIDATION_DIR = PROJECT_ROOT / "workshop" / "validation"
DEFAULT_TIMEOUT = 1800


def run_notebook(path: Path, timeout: int) -> tuple[float, list[tuple[int, str, str]]]:
    """Execute one notebook in place.

    Args:
        path (Path): Notebook to execute (cell outputs are replaced and saved).
        timeout (int): Per-cell timeout in seconds.

    Returns:
        tuple[float, list[tuple[int, str, str]]]: Elapsed seconds and the error cells
            as ``(cell index, error name, message)``.
    """
    notebook = nbformat.read(str(path), as_version=4)
    started = time.time()
    client = NotebookClient(
        notebook,
        timeout=timeout,
        allow_errors=True,
        resources={"metadata": {"path": str(path.parent)}},
    )
    client.execute()
    errors = [
        (index, output["ename"], output["evalue"][:160])
        for index, cell in enumerate(notebook.cells)
        if cell.cell_type == "code"
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    nbformat.write(notebook, str(path))
    return time.time() - started, errors


def main(argv: list[str] | None = None) -> int:
    """Run the selected validation notebooks.

    Args:
        argv (list[str] | None): Argument list, or None to use ``sys.argv``.

    Returns:
        int: 0 if every notebook ran without an error cell, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--only", nargs="+", help="Name prefixes to run (e.g. 01 03).")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    warnings.filterwarnings("ignore")
    paths = sorted(VALIDATION_DIR.glob("*.ipynb"))
    if args.only:
        paths = [p for p in paths if any(p.name.startswith(x) for x in args.only)]
    if not paths:
        print("No validation notebooks selected.")
        return 1

    failed = 0
    for path in paths:
        print(f"Running {path.name} ...", flush=True)
        seconds, errors = run_notebook(path, args.timeout)
        status = "ok" if not errors else f"{len(errors)} ERROR CELL(S)"
        print(f"  {status} in {seconds:.0f}s", flush=True)
        for index, name, message in errors[:3]:
            print(f"    cell {index}: {name}: {message}")
        failed += bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
