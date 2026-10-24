"""Small helpers for validation notebooks: a provenance header and computed prose.

Every validation notebook starts with ``report.header()``, which states which config and
which data the run used. Narrative text in the notebooks is computed from the results with
``report.say`` rather than typed in, so re-running a notebook after a refit refreshes both the
numbers and the sentences describing them; nothing from an earlier config is stored.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from IPython.display import Markdown, display

from workshop.lib import datasets, fit

HEADER_MARKER = "Validated config"


def config_summary(config_dir: Path | None = None) -> dict[str, Any]:
    """Describe a config: hash, what it was fitted on, and the data now available."""
    directory = config_dir or fit.LIVE_CONFIG_DIR
    manifest = json.loads((directory / fit.MANIFEST_FILE).read_text("utf-8"))
    fitted = next(iter(manifest["fitted_sections"].values()))["sources"]
    available = {
        name: len(datasets.load_career(name).matches)
        for name in datasets.career_names()
    }
    return {
        "hash": fit.config_hash(directory),
        "fitted_on": {c: tuple(v["match_ids"]) for c, v in fitted.items()},
        "available": available,
        "stale": any(
            available.get(c, 0) > ids[1] for c, ids in ((c, tuple(v["match_ids"])) for c, v in fitted.items())
        ),
        "policy": manifest.get("rare_event_policy"),
    }


def say(text: str) -> None:
    """Render ``text`` as Markdown in the notebook output."""
    display(Markdown(text))


def header(config_dir: Path | None = None) -> dict[str, Any]:
    """Render the provenance header and return the summary it was built from."""
    info = config_summary(config_dir)
    fitted = ", ".join(f"{c} {lo}-{hi}" for c, (lo, hi) in info["fitted_on"].items())
    data = ", ".join(f"{c} ({n})" for c, n in info["available"].items())
    lines = [
        f"**{HEADER_MARKER}: `{info['hash'][:8]}`** | run {datetime.date.today().isoformat()}",
        "",
        f"- Config fitted on: {fitted}",
        f"- Data analysed (matches per career): {data}",
    ]
    if info["stale"]:
        lines.append(
            "- **Warning:** the datasets hold matches the config was not fitted on "
            "(run `scripts/refit_config.py`)."
        )
    say("\n".join(lines))
    return info


def ci(estimate: Any, digits: int = 3) -> str:  # noqa: ANN401
    """Format an ``inference.Estimate`` as ``0.123 [0.045, 0.201]``."""
    return (
        f"{estimate.estimate:.{digits}f} "
        f"[{estimate.ci_low:.{digits}f}, {estimate.ci_high:.{digits}f}]"
    )


def span(low: float, high: float, digits: int = 3) -> str:
    """Format a range like ``0.123 to 0.201``."""
    return f"{low:.{digits}f} to {high:.{digits}f}"
