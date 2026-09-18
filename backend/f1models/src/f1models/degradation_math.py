"""Pure tyre-degradation math: no f1core dependency, so this is testable
ahead of the project's real 3.12 toolchain being available (see
f1core.events' module docstring for why that matters, and this module's
sibling `tyre.py`, which wraps this in the actual f1core `Component`).

Validated live during T2 against the real 2025 Italian GP (Monza,
session_key=9912, driver 1's 37-lap opening stint): the naive, uncorrected
`lap_time ~ tyre_age` slope came out to -0.022 s/lap — tyres apparently
getting *faster* with age, exactly the confounded-fit failure mode
docs/f1-strategy-research.md §3.6/§12#1 describes. Adding back the fuel-burn
correction before fitting flips it to +0.028 s/lap, a physically plausible
value. The same real stint also showed why the tyre cliff is not jointly
fit here: it's a 3-parameter fit over a stint that never actually reaches
its cliff (the driver pitted before any late-stint fall-off), and that fit
came out unstable (a negative base slope offset by a large hinge term).
Fitting a cliff needs either more laps than a typical stint gives or a
mined prior (research.md §3.2) — see docs/plan/phase-2.md's Decisions.
"""

from __future__ import annotations

import numpy as np

# Pitwall's calibrated default (docs/f1-strategy-research.md §3.4/§10.5);
# not yet calibrated per-circuit.
FUEL_EFFECT_S_PER_LAP = 0.05

# research.md §3.6: clamp to what's physically plausible so a noisy fit on a
# short stint can never recommend an impossible negative-wear or absurdly
# high-wear tyre.
MIN_PLAUSIBLE_K1_S_PER_LAP = 0.0
MAX_PLAUSIBLE_K1_S_PER_LAP = 0.22


def fuel_corrected_lap_time(
    lap_time_s: float, lap_number: int, fuel_effect_s_per_lap: float = FUEL_EFFECT_S_PER_LAP
) -> float:
    """Add back the time fuel burn saved so what's left reflects tyre wear
    only. `lap_number` is race-relative (1-indexed), not tyre age — fuel
    burns down over the whole race, independent of which tyre is fitted.
    """
    return lap_time_s + fuel_effect_s_per_lap * lap_number


def fit_linear_degradation(ages: np.ndarray, fuel_corrected_times: np.ndarray) -> float:
    """Ordinary least squares for `t = k0 + k1 * age`, returning k1.
    Deliberately 2-parameter, not linear+cliff — see the module docstring
    for why jointly fitting a cliff from one stint's laps is unreliable.
    """
    design = np.column_stack([np.ones_like(ages), ages])
    coeffs, *_ = np.linalg.lstsq(design, fuel_corrected_times, rcond=None)
    return float(coeffs[1])


def clamp_degradation_rate(k1: float) -> float:
    return float(np.clip(k1, MIN_PLAUSIBLE_K1_S_PER_LAP, MAX_PLAUSIBLE_K1_S_PER_LAP))
