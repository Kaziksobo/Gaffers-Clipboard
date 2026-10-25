"""Check the shipped reliable-rating constants still agree with a fresh fit.

The constants at the top of ``reliable_rating_service.py`` are pasted in from
``workshop/validation/06_reliable_rating.ipynb``. That notebook's header hash covers
only the ``config/`` files and the data, not hand-set constants in the rating service,
so editing the rating service changes the ratings (and the right constants) without
any warning. This test refits on the current ratings and fails when a shipped
constant falls outside the fresh 95% interval. The interval, rather than an exact
match, keeps it quiet through the small shifts every new match causes; it fires only
when the ratings or data have moved enough that the shipped values are statistically
inconsistent with them.
"""

from __future__ import annotations

import pandas as pd
import pytest
from workshop.lib import reliable_rating

from src.services.analytics.reliable_rating_service import ReliableRatingService

# Service constant -> the fitted component it should agree with.
_CONSTANTS = {
    "PRIOR_MEAN": "mu",
    "PRIOR_VARIANCE": "between_var",
    "OBSERVATION_VARIANCE": "within_var",
}


@pytest.fixture(scope="module")
def fresh_fit() -> pd.DataFrame:
    """Return a fresh REML fit on the pooled careers, with bootstrap intervals."""
    summaries = reliable_rating.player_summaries(
        reliable_rating.appearance_frame("pool")
    )
    fit = reliable_rating.fit_variance_components(summaries)
    draws = reliable_rating.bootstrap_variance_components(summaries, n_resamples=300)
    return reliable_rating.summarise_bootstrap(fit, draws)


@pytest.mark.parametrize(("constant", "component"), list(_CONSTANTS.items()))
def test_shipped_constant_lies_inside_the_fresh_interval(
    fresh_fit: pd.DataFrame, constant: str, component: str
) -> None:
    """Each shipped constant is consistent with a refit on the current ratings."""
    shipped = getattr(ReliableRatingService, constant)
    estimate, low, high = fresh_fit.loc[component, ["estimate", "ci_low", "ci_high"]]

    assert low <= shipped <= high, (
        f"{constant} = {shipped} is outside the fresh 95% interval "
        f"[{low:.3f}, {high:.3f}] (estimate {estimate:.3f}). The ratings or data have "
        "moved: re-run workshop/validation/06_reliable_rating.ipynb and paste the "
        "constants into reliable_rating_service.py."
    )
