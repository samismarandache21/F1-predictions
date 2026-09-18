"""Pure lap-time/finish-time prediction math: no f1core dependency, so
testable ahead of the project's real 3.12 toolchain (see
f1models.degradation_math's module docstring for why that split matters).

`pace_base_s` and `deg_rate_s_per_lap` (from f1models.pace/tyre) are both
defined in "fuel- and tyre-corrected" units — a fresh-tyre,
full-fuel-load-equivalent baseline. Predicting a real future lap time
means undoing both corrections: subtract the fuel-burn benefit for that
lap's race-relative lap number (the car gets faster as fuel burns off),
and add back the tyre-wear penalty for that lap's tyre age.

M2 v1 does not apply deg_cliff_lap's cliff-acceleration term: the fit
(f1models.degradation_math) is deliberately linear-only (see its module
docstring — jointly fitting a cliff from one stint was unstable), so there
is no estimated magnitude for the acceleration beyond the cliff to apply.
Applying the cliff to predictions is docs/backlog.md once a cliff slope is
actually estimated or mined (docs/plan/phase-2.md T4).
"""

from __future__ import annotations

from f1models.degradation_math import FUEL_EFFECT_S_PER_LAP


def predict_lap_time_s(
    pace_base_s: float,
    deg_rate_s_per_lap: float,
    tyre_age_laps: int,
    lap_number: int,
    fuel_effect_s_per_lap: float = FUEL_EFFECT_S_PER_LAP,
) -> float:
    return pace_base_s + deg_rate_s_per_lap * tyre_age_laps - fuel_effect_s_per_lap * lap_number


def predict_finish_time_s(
    elapsed_time_s: float,
    current_lap: int,
    current_tyre_age_laps: int,
    total_laps: int,
    pace_base_s: float,
    deg_rate_s_per_lap: float,
    fuel_effect_s_per_lap: float = FUEL_EFFECT_S_PER_LAP,
) -> float:
    """`elapsed_time_s` is the real, observed time for laps completed so
    far (1..current_lap); every remaining lap (current_lap+1..total_laps)
    is predicted assuming the current tyre stays fitted to the flag (the
    "no further pit stops" M2 simplification, docs/plan/phase-2.md
    Decisions)."""
    total = elapsed_time_s
    for offset, lap_number in enumerate(range(current_lap + 1, total_laps + 1), start=1):
        tyre_age_laps = current_tyre_age_laps + offset
        total += predict_lap_time_s(
            pace_base_s, deg_rate_s_per_lap, tyre_age_laps, lap_number, fuel_effect_s_per_lap
        )
    return total
