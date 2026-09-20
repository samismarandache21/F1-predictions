"""Pure pace-estimation math: no f1core dependency, testable ahead of the
project's real 3.12 toolchain (see degradation_math.py's module docstring
for why that split matters, and this module's sibling `pace.py`, which
wraps this in the actual f1core `Component`).
"""

from __future__ import annotations

from collections.abc import Sequence

DEFAULT_EWMA_ALPHA = 0.3

# PaceEstimator's minimum-clean-laps gate and uncertainty levels
# (docs/plan/phase-2.md T3). Defined here, not in pace.py, so both the
# Component and anything doing the same math without f1core (the T8
# backtest) share one source of truth.
MIN_CLEAN_LAPS_FOR_ESTIMATE = 3
PRIOR_UNCERTAINTY_S = 2.0
ESTIMATED_UNCERTAINTY_S = 0.3


def tyre_corrected_lap_time(
    fuel_corrected_time_s: float, tyre_age_laps: int, deg_rate_s_per_lap: float
) -> float:
    """Remove the estimated tyre-wear contribution, leaving what the lap
    would have taken on a fresh tyre. `fuel_corrected_time_s` should
    already have degradation_math.fuel_corrected_lap_time applied."""
    return fuel_corrected_time_s - deg_rate_s_per_lap * tyre_age_laps


def ewma(values: Sequence[float], alpha: float = DEFAULT_EWMA_ALPHA) -> float:
    """Exponentially-weighted moving average, seeded by the first value
    itself (a flat, weak prior per docs/plan/phase-2.md's Decisions — every
    driver starts equal, with no fabricated circuit-specific baseline)."""
    if not values:
        raise ValueError("ewma requires at least one value")
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result
