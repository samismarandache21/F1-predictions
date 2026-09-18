"""RaceStateBuilder: applies domain events to produce a new RaceState, plus
notification triggers (lap_completed, critical_event) for whatever's
listening (T8's WebSocket layer, eventually). See
docs/f1-strategy-design.md §4.1/§6 and docs/plan/phase-1.md T6.

Dispatches on `event.type` and reads only duck-typed attributes, rather
than importing the concrete f1core.events classes at runtime: this module
never constructs a DomainEvent, only reads one, so it doesn't need
f1core's Pydantic-based package init to be importable here (see
f1core.events' module docstring, and the T5/T6 summaries for why that
matters ahead of the project's real 3.12 toolchain being installed).
`DomainEvent` itself is imported only under TYPE_CHECKING, for annotations.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Union

from f1state.state import RaceState

if TYPE_CHECKING:
    from f1core.events import DomainEvent

_FLAG_TO_STATUS = {
    "GREEN": "GREEN",
    "CLEAR": "GREEN",
    "YELLOW": "YELLOW",
    "DOUBLE YELLOW": "YELLOW",
    "RED": "RED",
    "CHEQUERED": "GREEN",
}


@dataclass(frozen=True)
class LapCompletedTrigger:
    driver: int
    lap: int


@dataclass(frozen=True)
class CriticalEventTrigger:
    reason: str
    detail: str


Trigger = Union[LapCompletedTrigger, CriticalEventTrigger]  # noqa: UP007 (see f1core/events.py)


def _interpret_race_control(
    category: str | None, flag: str | None, message: str | None
) -> str | None:
    """Same heuristic as f1ingest.pipeline._track_status_timeline, kept as
    an independent copy rather than a shared import: it's small and already
    flagged as approximate (only exercised end-to-end once a wet/SC-
    affected fixture race is ingested — see docs/backlog.md), and sharing
    it would mean f1state importing f1ingest, which runs backward for this
    architecture (state consumes what ingestion produces, not the reverse).
    """
    category_u = (category or "").upper()
    message_u = (message or "").upper()
    flag_u = (flag or "").upper()
    if category_u == "SAFETYCAR" or "SAFETY CAR" in message_u:
        ending = "ENDING" in message_u or "IN THIS LAP" in message_u
        if "VIRTUAL" in message_u:
            return "GREEN" if ending else "VSC"
        return "GREEN" if ending else "SC"
    return _FLAG_TO_STATUS.get(flag_u)


class RaceStateBuilder:
    def __init__(self, team_by_driver_number: dict[int, str] | None = None) -> None:
        self._team_by_driver_number = team_by_driver_number or {}

    def apply(self, state: RaceState, event: DomainEvent) -> tuple[RaceState, list[Trigger]]:
        handler = getattr(self, f"_apply_{event.type}", None)
        if handler is None:
            return state, []  # unknown event type: degrade gracefully, never crash the pipeline
        return handler(state, event)  # type: ignore[no-any-return]

    def _apply_lap_completed(
        self, state: RaceState, event: DomainEvent
    ) -> tuple[RaceState, list[Trigger]]:
        car = state.car(event.driver)
        if car.last_lap is not None and event.lap <= car.last_lap:
            return state, []  # stale/duplicate/out-of-order: idempotent no-op (CLAUDE.md rule 8)

        compounds_used = car.compounds_used
        if event.compound and event.compound not in compounds_used:
            compounds_used = (*compounds_used, event.compound)

        new_car = replace(
            car,
            team=car.team or self._team_by_driver_number.get(event.driver),
            position=event.position,
            gap_to_leader_s=event.gap_to_leader_s,
            interval_s=event.interval_s,
            compound=event.compound,
            tyre_age_laps=event.tyre_age_laps,
            compounds_used=compounds_used,
            in_pit=False,  # completing a lap means they're back on track
            last_lap=event.lap,
            last_lap_time_s=event.lap_time_s,
        )
        new_state = state.with_car(new_car)
        if event.lap > new_state.lap:
            new_state = replace(new_state, lap=event.lap)
        if event.track_status and event.track_status != new_state.track_status:
            new_state = replace(new_state, track_status=event.track_status)
        return new_state, [LapCompletedTrigger(driver=event.driver, lap=event.lap)]

    def _apply_pit_stop(
        self, state: RaceState, event: DomainEvent
    ) -> tuple[RaceState, list[Trigger]]:
        car = state.car(event.driver)
        new_car = replace(
            car, in_pit=True, pit_stops=car.pit_stops + 1, stint_number=car.stint_number + 1
        )
        return state.with_car(new_car), []

    def _apply_race_control(
        self, state: RaceState, event: DomainEvent
    ) -> tuple[RaceState, list[Trigger]]:
        status = _interpret_race_control(event.category, event.flag, event.message)
        if not status or status == state.track_status:
            return state, []

        new_state = replace(state, track_status=status, state_version=state.state_version + 1)
        if status in ("SC", "VSC", "RED"):
            return new_state, [CriticalEventTrigger(reason=status, detail=event.message)]
        return new_state, [CriticalEventTrigger(reason="CLEAR", detail=event.message)]

    def _apply_weather(
        self, state: RaceState, event: DomainEvent
    ) -> tuple[RaceState, list[Trigger]]:
        was_dry = not state.rainfall
        new_state = replace(
            state,
            track_temp_c=event.track_temp_c,
            air_temp_c=event.air_temp_c,
            rainfall=event.rainfall,
            state_version=state.state_version + 1,
        )
        if event.rainfall and was_dry:
            return new_state, [
                CriticalEventTrigger(reason="RAIN_START", detail="rainfall detected")
            ]
        return new_state, []

    def _apply_location_update(
        self, state: RaceState, event: DomainEvent
    ) -> tuple[RaceState, list[Trigger]]:
        # Live (x, y) isn't part of RaceState (design doc §6 has no location
        # fields); T8's WebSocket layer relays these events directly.
        return state, []
