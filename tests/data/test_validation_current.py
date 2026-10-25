"""Check the validation notebooks ran cleanly and are not behind the config.

A notebook that was never run, or has an error cell, fails. One that ran against an
older config or older data only warns (re-run ``scripts/run_validation.py``), as a
config behind the datasets does: stale results are a nudge, broken ones are a bug.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import nbformat
import pytest
from workshop.lib import datasets, fit
from workshop.lib.report import HEADER_MARKER

_DIR = Path(__file__).resolve().parents[2] / "workshop" / "validation"
_NOTEBOOKS = sorted(_DIR.glob("*.ipynb"))


def _header_text(path: Path) -> str:
    notebook = nbformat.read(str(path), as_version=4)
    for cell in notebook.cells:
        for output in cell.get("outputs", []):
            text = output.get("data", {}).get("text/markdown", "")
            if HEADER_MARKER in text:
                return text
    return ""


def test_the_validation_suite_exists() -> None:
    """The seven validation notebooks are present."""
    assert [p.name[:2] for p in _NOTEBOOKS] == [
        "00",
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
    ]


@pytest.mark.parametrize("path", _NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_was_executed_without_errors(path: Path) -> None:
    """Every code cell has run and none left an error."""
    notebook = nbformat.read(str(path), as_version=4)
    code = [c for c in notebook.cells if c.cell_type == "code"]
    assert all(c.execution_count is not None for c in code), "unexecuted cell"
    errors = [
        o.get("ename")
        for c in code
        for o in c.get("outputs", [])
        if o.get("output_type") == "error"
    ]
    assert not errors


@pytest.mark.parametrize("path", _NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_ran_on_the_live_config_and_current_data(path: Path) -> None:
    """Warn when a notebook's header names another config or different data."""
    header = _header_text(path)
    assert header, "notebook has no provenance header"
    ran_on = re.search(rf"{HEADER_MARKER}: `([0-9a-f]{{8}})`", header)
    assert ran_on, "header has no config hash"
    problems = []
    if ran_on.group(1) != fit.config_hash()[:8]:
        problems.append(
            f"ran on config {ran_on.group(1)}, live is {fit.config_hash()[:8]}"
        )
    data_line = next(
        (line for line in header.splitlines() if "Data analysed" in line), ""
    )
    seen = {name: int(n) for name, n in re.findall(r"(\w+) \((\d+)\)", data_line)}
    now = {
        name: len(datasets.load_career(name).matches)
        for name in datasets.career_names()
    }
    if seen != now:
        problems.append(f"ran on {seen}, datasets now hold {now}")
    if problems:
        warnings.warn(
            f"{path.name} is stale ({'; '.join(problems)}): "
            "run scripts/run_validation.py",
            stacklevel=1,
        )
