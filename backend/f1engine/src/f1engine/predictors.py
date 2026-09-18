"""Lap-time and finish-time predictor Components (P2, P3): wrap
prediction_math's pure functions in real f1core Values. See
docs/plan/phase-2.md T4.

NOT RUNNABLE in this dev environment — see f1models/tyre.py's module
docstring for why (constructing f1core.Value needs Python >= 3.11 here).
The math these wrap lives in prediction_math.py, which has no such
dependency and is tested directly.
"""

from __future__ import annotations

from f1core.snapshot import Snapshot
from f1core.values import Kind, Value
from f1engine.prediction_math import predict_finish_time_s, predict_lap_time_s
from f1models.tyre import GENERIC_PRIOR_K1_S_PER_LAP

# Additive combination of the input values' own uncertainties: a simple
# upper bound, not a real error-propagation model. Calibrating this
# properly is docs/backlog.md.
_DEFAULT_UNCERTAINTY_S = 1.0


def _resolve_deg_rate(ctx: Snapshot, scope_id: str) -> tuple[float, float]:
    """Returns (deg_rate_s_per_lap, uncertainty), falling back to the same
    generic prior f1models.tyre.TyreDegEstimator itself falls back to."""
    value = ctx.get("car.tyre.deg_rate", scope_id)
    if value is None:
        return GENERIC_PRIOR_K1_S_PER_LAP, _DEFAULT_UNCERTAINTY_S
    return value.data, value.uncertainty or _DEFAULT_UNCERTAINTY_S


class LapTimePredictor:
    name = "lap_time_predictor"
    inputs = ["car.lap.observation", "car.pace.base_s", "car.tyre.deg_rate"]
    outputs = ["car.lap.time_pred"]

    def compute(self, ctx: Snapshot, scope_id: str) -> dict[str, Value]:
        history = ctx.history_for_driver("car.lap.observation", scope_id)
        pace_value = ctx.get("car.pace.base_s", scope_id)
        if not history or pace_value is None:
            return {}

        latest = history[-1]
        next_lap = latest.data["lap"] + 1
        next_tyre_age = latest.data["tyre_age_laps"] + 1
        deg_rate, deg_uncertainty = _resolve_deg_rate(ctx, scope_id)

        predicted = predict_lap_time_s(
            pace_base_s=pace_value.data,
            deg_rate_s_per_lap=deg_rate,
            tyre_age_laps=next_tyre_age,
            lap_number=next_lap,
        )
        uncertainty = (pace_value.uncertainty or _DEFAULT_UNCERTAINTY_S) + deg_uncertainty

        return {
            "car.lap.time_pred": Value(
                var_id="car.lap.time_pred",
                scope_id=scope_id,
                kind=Kind.PREDICTED,
                data=predicted,
                source=self.name,
                ts=latest.ts,
                state_version=ctx.state_version,
                uncertainty=uncertainty,
            )
        }


class DeterministicRacePredictor:
    name = "deterministic_race_predictor"
    inputs = ["car.lap.observation", "car.pace.base_s", "car.tyre.deg_rate", "race.total_laps"]
    outputs = ["car.race.finish_time_pred"]

    def compute(self, ctx: Snapshot, scope_id: str) -> dict[str, Value]:
        history = ctx.history_for_driver("car.lap.observation", scope_id)
        pace_value = ctx.get("car.pace.base_s", scope_id)
        total_laps_value = ctx.get("race.total_laps", "")
        if not history or pace_value is None or total_laps_value is None:
            return {}

        elapsed_time_s = sum(v.data["lap_time_s"] for v in history)
        latest = history[-1]
        deg_rate, deg_uncertainty = _resolve_deg_rate(ctx, scope_id)

        predicted = predict_finish_time_s(
            elapsed_time_s=elapsed_time_s,
            current_lap=latest.data["lap"],
            current_tyre_age_laps=latest.data["tyre_age_laps"],
            total_laps=total_laps_value.data,
            pace_base_s=pace_value.data,
            deg_rate_s_per_lap=deg_rate,
        )
        uncertainty = (pace_value.uncertainty or _DEFAULT_UNCERTAINTY_S) + deg_uncertainty

        return {
            "car.race.finish_time_pred": Value(
                var_id="car.race.finish_time_pred",
                scope_id=scope_id,
                kind=Kind.PREDICTED,
                data=predicted,
                source=self.name,
                ts=latest.ts,
                state_version=ctx.state_version,
                uncertainty=uncertainty,
            )
        }
