"""Pace estimator (part of P2): the f1core Component wrapping pace_math's
EWMA. See docs/plan/phase-2.md T3.

NOT RUNNABLE in this dev environment — see tyre.py's module docstring for
why (constructing f1core.Value needs Python >= 3.11 here). The pure math
this wraps lives in pace_math.py, which has no such dependency and is
tested directly.
"""

from __future__ import annotations

from f1core.snapshot import Snapshot
from f1core.values import Kind, Value
from f1models.degradation_math import fuel_corrected_lap_time
from f1models.pace_math import DEFAULT_EWMA_ALPHA, ewma, tyre_corrected_lap_time
from f1models.tyre import GENERIC_PRIOR_K1_S_PER_LAP

MIN_CLEAN_LAPS_FOR_ESTIMATE = 3
PRIOR_UNCERTAINTY_S = 2.0
ESTIMATED_UNCERTAINTY_S = 0.3


class PaceEstimator:
    name = "pace_estimator"
    inputs = ["car.lap.observation", "car.tyre.deg_rate"]
    outputs = ["car.pace.base_s"]

    def __init__(
        self, alpha: float = DEFAULT_EWMA_ALPHA, min_clean_laps: int = MIN_CLEAN_LAPS_FOR_ESTIMATE
    ) -> None:
        self.alpha = alpha
        self.min_clean_laps = min_clean_laps

    def compute(self, ctx: Snapshot, scope_id: str) -> dict[str, Value]:
        history = ctx.history_for_driver("car.lap.observation", scope_id)
        clean = [v for v in history if v.data["is_clean_air"]]
        if not clean:
            return {}

        # Same current-stint estimate applied across the driver's whole
        # history — see predictions.yaml's car.pace.base_s description for
        # why this is a deliberate M2 v1 simplification.
        deg_rate_value = ctx.get("car.tyre.deg_rate", scope_id)
        deg_rate = deg_rate_value.data if deg_rate_value is not None else GENERIC_PRIOR_K1_S_PER_LAP

        corrected = [
            tyre_corrected_lap_time(
                fuel_corrected_lap_time(v.data["lap_time_s"], v.data["lap"]),
                v.data["tyre_age_laps"],
                deg_rate,
            )
            for v in clean
        ]
        pace = ewma(corrected, self.alpha)
        kind = Kind.ESTIMATED if len(clean) >= self.min_clean_laps else Kind.PRIOR
        uncertainty = ESTIMATED_UNCERTAINTY_S if kind == Kind.ESTIMATED else PRIOR_UNCERTAINTY_S

        return {
            "car.pace.base_s": Value(
                var_id="car.pace.base_s",
                scope_id=scope_id,
                kind=kind,
                data=pace,
                source=self.name,
                ts=clean[-1].ts,
                state_version=ctx.state_version,
                uncertainty=uncertainty,
            )
        }
