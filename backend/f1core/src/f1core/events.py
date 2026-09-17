"""Domain event schemas shared by the ingestion adapters (producers, in
f1ingest) and the race state service (consumer, T6, in f1state). See
docs/f1-strategy-design.md §5 for the reference shapes; fields here extend
those examples with what T9's timing tower actually needs (tyre/compound,
track status, pit in/out flags) — the doc's JSON was illustrative, not
exhaustive. `location_update` is an addition beyond the doc's examples,
needed for the track map (V1).

Plain dataclasses rather than pydantic models: these are internal,
already-validated value objects flowing through Redis Streams, not external
input that needs validation (that already happened during ingestion, T4).
Keeping this module pydantic-free also means it can be exercised on any
Python >= 3.9 during development, ahead of the project's real 3.12 toolchain
being installed — see the T5 summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Union


@dataclass(frozen=True)
class LapCompletedEvent:
    ts: datetime
    session_key: int
    driver: int
    lap: int
    lap_time_s: float | None
    sector_1_s: float | None
    sector_2_s: float | None
    sector_3_s: float | None
    position: int | None
    gap_to_leader_s: float | None
    interval_s: float | None
    compound: str | None
    tyre_age_laps: int | None
    track_status: str | None
    is_pit_out_lap: bool
    is_pit_in_lap: bool
    type: str = "lap_completed"


@dataclass(frozen=True)
class PitStopEvent:
    ts: datetime
    session_key: int
    driver: int
    lap: int
    pit_lane_time_s: float | None
    stationary_time_s: float | None
    # Derived from the stint starting the lap after this stop, not from the
    # pit_stops table itself (OpenF1 doesn't put the new compound there).
    new_compound: str | None
    new_tyre_age: int | None
    type: str = "pit_stop"


@dataclass(frozen=True)
class RaceControlEvent:
    ts: datetime
    session_key: int
    lap: int | None
    category: str | None
    flag: str | None
    scope: str | None
    driver: int | None
    message: str
    type: str = "race_control"


@dataclass(frozen=True)
class WeatherEvent:
    ts: datetime
    session_key: int
    track_temp_c: float | None
    air_temp_c: float | None
    humidity_pct: float | None
    rainfall: bool | None
    wind_speed_ms: float | None
    type: str = "weather"


@dataclass(frozen=True)
class LocationUpdateEvent:
    ts: datetime
    session_key: int
    driver: int
    x_m: float
    y_m: float
    z_m: float | None
    type: str = "location_update"


# typing.Union rather than the `|` spelling: this is a real assignment
# statement (not an annotation deferred by `from __future__ import
# annotations`), and `|` between classes needs Python 3.10+ at runtime.
DomainEvent = Union[  # noqa: UP007 (see comment above)
    LapCompletedEvent, PitStopEvent, RaceControlEvent, WeatherEvent, LocationUpdateEvent
]
