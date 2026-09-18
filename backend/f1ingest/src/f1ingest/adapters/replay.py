"""ReplayAdapter: reads a stored session and turns it into a deterministic,
time-ordered sequence of domain events — the same event types an OpenF1
live adapter (M6) would eventually produce (docs/f1-strategy-design.md
§4.1: "The rest of the system cannot tell the two apart"). See
docs/plan/phase-1.md T5.

NOTE ON LOCAL VERIFICATION: unlike the rest of T5 (clock.py, publisher.py),
this module constructs real f1core.events dataclass instances at runtime,
which requires importing the f1core package — and f1core's __init__.py
eagerly imports pydantic-based submodules that need Python >= 3.10 to even
resolve their type annotations (established in T3/T4). This module could
not be exercised by pytest in this development environment before the
project's real 3.12 toolchain was installed; the mapping logic below was
hand-traced against T4's real recorded fixtures instead. Re-run
tests/unit/f1ingest/test_replay_adapter.py once `uv sync` has run to
confirm it behaves as intended.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Protocol

from f1core.events import (
    DomainEvent,
    LapCompletedEvent,
    LocationUpdateEvent,
    PitStopEvent,
    RaceControlEvent,
    WeatherEvent,
)

from f1ingest.clock import ReplayClock
from f1ingest.publisher import EventPublisher

# Deterministic tie-break when several events share the same timestamp.
# The exact order doesn't matter for correctness, only that it's fixed —
# this is what makes build_event_sequence's output byte-identical across
# runs (docs/plan/phase-1.md T5's "identical event sequence" requirement).
_TYPE_PRIORITY = {
    "weather": 0,
    "race_control": 1,
    "location_update": 2,
    "pit_stop": 3,
    "lap_completed": 4,
}


def _sort_key(event: DomainEvent) -> tuple[Any, ...]:
    driver = getattr(event, "driver", None)
    return (event.ts, _TYPE_PRIORITY[event.type], driver if driver is not None else -1)


class RowSource(Protocol):
    """Whatever can hand back a session's rows, keyed by table name. Tests
    use a plain dict-backed fake (see test_replay_adapter.py); DbRowSource
    below is the real SQLAlchemy-backed implementation."""

    def fetch(self, table_name: str, session_key: int) -> Sequence[Mapping[str, Any]]: ...


class DbRowSource:
    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def fetch(self, table_name: str, session_key: int) -> Sequence[Mapping[str, Any]]:
        from sqlalchemy import select

        from f1ingest.db.schema import metadata

        table = metadata.tables[table_name]
        with self._engine.connect() as conn:
            result = conn.execute(
                select(table)
                .where(table.c.session_key == session_key)
                .order_by(*table.primary_key.columns)
            )
            return [dict(row._mapping) for row in result]


def build_event_sequence(session_key: int, rows: RowSource) -> list[DomainEvent]:
    """Pure function: the same rows in always produce the same event
    sequence out. This is what T5's determinism (hash) test checks.
    """
    events: list[DomainEvent] = []

    laps = rows.fetch("laps", session_key)
    stints = rows.fetch("stints", session_key)
    pit_stops = rows.fetch("pit_stops", session_key)
    race_control = rows.fetch("race_control", session_key)
    weather = rows.fetch("weather", session_key)
    location = rows.fetch("location", session_key)

    # (driver_number, lap_start) -> stint, to look up the compound/age a
    # pit stop's out-lap begins on (see PitStopEvent's docstring).
    stint_by_driver_lap_start = {
        (s["driver_number"], s["lap_start"]): s for s in stints if s.get("lap_start") is not None
    }

    for lap in laps:
        events.append(
            LapCompletedEvent(
                ts=lap["ts"],
                session_key=session_key,
                driver=lap["driver_number"],
                lap=lap["lap_number"],
                lap_time_s=lap.get("lap_time_s"),
                sector_1_s=lap.get("sector_1_s"),
                sector_2_s=lap.get("sector_2_s"),
                sector_3_s=lap.get("sector_3_s"),
                position=lap.get("position"),
                gap_to_leader_s=lap.get("gap_to_leader_s"),
                interval_s=lap.get("interval_s"),
                compound=lap.get("compound"),
                tyre_age_laps=lap.get("tyre_age_laps"),
                track_status=lap.get("track_status"),
                is_pit_out_lap=bool(lap.get("is_pit_out_lap", False)),
                is_pit_in_lap=bool(lap.get("is_pit_in_lap", False)),
            )
        )

    for pit in pit_stops:
        out_stint = stint_by_driver_lap_start.get((pit["driver_number"], pit["lap_number"] + 1))
        events.append(
            PitStopEvent(
                ts=pit["ts"],
                session_key=session_key,
                driver=pit["driver_number"],
                lap=pit["lap_number"],
                pit_lane_time_s=pit.get("lane_time_s"),
                stationary_time_s=pit.get("stationary_time_s"),
                new_compound=out_stint.get("compound") if out_stint else None,
                new_tyre_age=out_stint.get("tyre_age_at_start") if out_stint else None,
            )
        )

    for rc in race_control:
        events.append(
            RaceControlEvent(
                ts=rc["ts"],
                session_key=session_key,
                lap=rc.get("lap_number"),
                category=rc.get("category"),
                flag=rc.get("flag"),
                scope=rc.get("scope"),
                driver=rc.get("driver_number"),
                message=rc["message"],
            )
        )

    for w in weather:
        events.append(
            WeatherEvent(
                ts=w["ts"],
                session_key=session_key,
                track_temp_c=w.get("track_temp_c"),
                air_temp_c=w.get("air_temp_c"),
                humidity_pct=w.get("humidity_pct"),
                rainfall=w.get("rainfall"),
                wind_speed_ms=w.get("wind_speed_ms"),
            )
        )

    for loc in location:
        events.append(
            LocationUpdateEvent(
                ts=loc["ts"],
                session_key=session_key,
                driver=loc["driver_number"],
                x_m=loc["x_m"],
                y_m=loc["y_m"],
                z_m=loc.get("z_m"),
            )
        )

    events.sort(key=_sort_key)
    return events


class ReplayAdapter:
    """Pairs a RowSource with a ReplayClock. `stream()` matches the
    `SourceAdapter.stream() -> Iterator[RawEvent]` interface from
    docs/f1-strategy-design.md §4.1, so a future OpenF1LiveAdapter (M6) can
    stand in for this one without the rest of the system noticing. The
    clock is exposed so a caller (T8's replay control endpoint) can
    play/pause/seek/re-speed it while `stream()` is being iterated
    elsewhere (e.g. from a worker thread).
    """

    def __init__(self, rows: RowSource, publisher: EventPublisher, *, speed: float = 1.0) -> None:
        self._rows = rows
        self._publisher = publisher
        self._initial_speed = speed
        self.clock: ReplayClock | None = None

    def load_events(self, session_key: int) -> list[DomainEvent]:
        return build_event_sequence(session_key, self._rows)

    def prepare(self, session_key: int) -> ReplayClock:
        """Build the event sequence and clock synchronously, without
        starting playback. Split out from `stream()` so a caller (T8) can
        hand back a live_id with a controllable clock attached immediately,
        before handing the actual iteration off to a background thread —
        generator functions don't run any of their body, including setting
        `self.clock`, until first iterated.
        """
        events = self.load_events(session_key)
        self.clock = ReplayClock(events, self._publisher, speed=self._initial_speed)
        return self.clock

    def stream(self, session_key: int) -> Iterator[DomainEvent]:
        clock = self.clock or self.prepare(session_key)
        yield from clock.run()
