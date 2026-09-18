"""The RaceState view: a queryable, serialisable snapshot of a race in
progress, built by RaceStateBuilder from the domain event stream. See
docs/f1-strategy-design.md §6.

Fields out of scope for M1 (pace_estimate, damage, predicted_strategy) are
omitted — see docs/plan/phase-1.md's M1 scope and docs/backlog.md.
`retired` is present for schema forward-compatibility but is never set by
this M1 builder: reliable retirement detection needs race-control
cross-referencing and a DNF hazard model, which is M5 scope (P8).

Plain dataclasses, not Pydantic: same reasoning as f1core.events — this is
internal, already-validated state, immutable (copy-on-write, via
`with_car`/`dataclasses.replace`) so a car's history can't be corrupted by
a stray in-place mutation, and it keeps this code testable ahead of the
project's real 3.12 toolchain being available. T8's API layer will map this
to its own Pydantic response schema at the boundary, same as any other
internal-model-vs-DTO split.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class PitStopRecord:
    """One completed stop. T9's pit panel needs the actual history (lap,
    lane time, stationary time), not just a count."""

    lap: int
    lane_time_s: float | None
    stationary_time_s: float | None


@dataclass(frozen=True)
class CarState:
    driver: int
    team: str | None = None
    team_colour: str | None = None
    position: int | None = None
    gap_to_leader_s: float | None = None
    interval_s: float | None = None
    compound: str | None = None
    tyre_age_laps: int | None = None
    stint_number: int = 1
    compounds_used: tuple[str, ...] = ()
    pit_stops: int = 0
    pit_history: tuple[PitStopRecord, ...] = ()
    in_pit: bool = False
    retired: bool = False
    last_lap: int | None = None
    last_lap_time_s: float | None = None
    # M2 predictions (docs/plan/phase-2.md T5), mirrored from f1core's
    # resolved Values by RaceStateBuilder.apply_predictions. deg_rate_kind
    # is "prior"/"estimated" (car.tyre.deg_rate's own kind); prediction_kind
    # covers both predicted_* fields together since car.lap.time_pred/
    # car.race.finish_time_pred each allow only kind=predicted in M2 v1 —
    # there's no separate provenance to track per-field yet.
    deg_rate_s_per_lap: float | None = None
    deg_rate_kind: str | None = None
    deg_uncertainty: float | None = None
    predicted_lap_time_s: float | None = None
    predicted_finish_time_s: float | None = None
    prediction_kind: str | None = None


@dataclass(frozen=True)
class RaceState:
    session_key: int
    circuit_id: str | None = None
    lap: int = 0
    total_laps: int | None = None
    track_status: str = "GREEN"
    track_temp_c: float | None = None
    air_temp_c: float | None = None
    rainfall: bool | None = None
    cars: dict[int, CarState] = field(default_factory=dict)
    state_version: int = 0

    def car(self, driver: int) -> CarState:
        return self.cars.get(driver, CarState(driver=driver))

    def with_car(self, car: CarState) -> RaceState:
        """Copy-on-write update: never mutate `self.cars` in place — that
        would silently corrupt any earlier RaceState that shares the same
        dict object by reference."""
        new_cars = dict(self.cars)
        new_cars[car.driver] = car
        return replace(self, cars=new_cars, state_version=self.state_version + 1)
