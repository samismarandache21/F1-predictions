"""Tyre degradation estimator (P1): the f1core Component wrapping
degradation_math's pure fit. See docs/plan/phase-2.md T2.

NOTE ON LOCAL VERIFICATION: this module constructs real f1core.values.Value
instances, which requires importing f1core — and f1core's __init__.py
eagerly imports Pydantic-based submodules that need Python >= 3.10 to
resolve their type annotations (established in T3 onward). This module
could not be exercised by pytest in this development environment before
the project's real 3.12 toolchain was installed. The actual numerical
logic this wraps lives in degradation_math.py, which has no such
dependency and *was* validated against real data — see its docstring.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from f1core.snapshot import Snapshot
from f1core.values import Kind, Value
from f1models.degradation_math import FUEL_EFFECT_S_PER_LAP, clamp_degradation_rate, fit_linear_degradation

MIN_CLEAN_LAPS_FOR_ESTIMATE = 5

GENERIC_PRIOR_K1_S_PER_LAP = 0.08
GENERIC_PRIOR_CLIFF_LAP = 20
PRIOR_UNCERTAINTY = 0.05
ESTIMATED_UNCERTAINTY = 0.02


@dataclass(frozen=True)
class DegradationPrior:
    k1_s_per_lap: float = GENERIC_PRIOR_K1_S_PER_LAP
    cliff_lap: int = GENERIC_PRIOR_CLIFF_LAP


class TyreDegEstimator:
    name = "tyre_deg_estimator"
    inputs = ["car.lap.observation"]
    outputs = ["car.tyre.deg_rate", "car.tyre.deg_cliff_lap"]

    def __init__(
        self,
        prior: DegradationPrior | None = None,
        min_clean_laps: int = MIN_CLEAN_LAPS_FOR_ESTIMATE,
    ) -> None:
        self.prior = prior or DegradationPrior()
        self.min_clean_laps = min_clean_laps

    def compute(self, ctx: Snapshot, scope_id: str) -> dict[str, Value]:
        history = ctx.history_for_driver("car.lap.observation", scope_id)
        if not history:
            return {}

        latest = history[-1]
        current_stint = latest.data["stint_number"]
        stint_laps = [v for v in history if v.data["stint_number"] == current_stint]
        clean = [v for v in stint_laps if v.data["is_clean_air"]]

        if len(clean) < self.min_clean_laps:
            return self._values(ctx, scope_id, latest.ts, Kind.PRIOR, self.prior.k1_s_per_lap)

        ages = np.array([v.data["tyre_age_laps"] for v in clean], dtype=float)
        lap_numbers = np.array([v.data["lap"] for v in clean], dtype=float)
        raw_times = np.array([v.data["lap_time_s"] for v in clean], dtype=float)
        corrected = raw_times + FUEL_EFFECT_S_PER_LAP * lap_numbers

        k1 = clamp_degradation_rate(fit_linear_degradation(ages, corrected))

        return self._values(ctx, scope_id, latest.ts, Kind.ESTIMATED, k1)

    def _values(
        self, ctx: Snapshot, scope_id: str, ts: object, kind: Kind, k1: float
    ) -> dict[str, Value]:
        return {
            "car.tyre.deg_rate": Value(
                var_id="car.tyre.deg_rate",
                scope_id=scope_id,
                kind=kind,
                data=k1,
                source=self.name,
                ts=ts,  # type: ignore[arg-type]
                state_version=ctx.state_version,
                uncertainty=ESTIMATED_UNCERTAINTY if kind == Kind.ESTIMATED else PRIOR_UNCERTAINTY,
            ),
            # Always the prior, never estimated in M2 v1 — see module docstring.
            "car.tyre.deg_cliff_lap": Value(
                var_id="car.tyre.deg_cliff_lap",
                scope_id=scope_id,
                kind=Kind.PRIOR,
                data=self.prior.cliff_lap,
                source=self.name,
                ts=ts,  # type: ignore[arg-type]
                state_version=ctx.state_version,
                uncertainty=PRIOR_UNCERTAINTY,
            ),
        }
