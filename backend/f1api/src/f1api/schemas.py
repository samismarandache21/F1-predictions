"""Pydantic request/response models for the API (T8). FastAPI's OpenAPI
output generates the TS types Angular uses (`make types`) — see
docs/f1-strategy-foundation.md §7.

Uses `typing.Optional`/`typing.Union` explicitly rather than the `X | None`
shorthand: the shorthand needs Python 3.10+ to even resolve at class-
creation time (pydantic evaluates field annotations eagerly), while
`Optional`/`Union` have always worked identically regardless of Python
version. This is what makes these schemas — and the endpoints built on
them — testable right now, ahead of the project's real 3.12 toolchain
being installed (verified live during T8; see its summary). f1core's own
models use the `X | None` shorthand and are correspondingly blocked on this
machine — that's fine there since f1core isn't API-surface code under
active iteration in the same way.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SessionOut(BaseModel):
    session_key: int
    season: int
    round: Optional[int] = None
    circuit_id: Optional[str] = None
    session_type: str
    session_name: str
    date_start: datetime
    date_end: Optional[datetime] = None
    total_laps: Optional[int] = None

    model_config = {"from_attributes": True}


class PitStopRecordOut(BaseModel):
    lap: int
    lane_time_s: Optional[float] = None
    stationary_time_s: Optional[float] = None


class CarStateOut(BaseModel):
    driver: int
    team: Optional[str] = None
    team_colour: Optional[str] = None
    position: Optional[int] = None
    gap_to_leader_s: Optional[float] = None
    interval_s: Optional[float] = None
    compound: Optional[str] = None
    tyre_age_laps: Optional[int] = None
    stint_number: int
    compounds_used: list[str]
    pit_stops: int
    pit_history: list[PitStopRecordOut]
    in_pit: bool
    retired: bool
    last_lap: Optional[int] = None
    last_lap_time_s: Optional[float] = None

    @classmethod
    def from_car_state(cls, car: Any) -> CarStateOut:
        return cls(
            driver=car.driver,
            team=car.team,
            team_colour=car.team_colour,
            position=car.position,
            gap_to_leader_s=car.gap_to_leader_s,
            interval_s=car.interval_s,
            compound=car.compound,
            tyre_age_laps=car.tyre_age_laps,
            stint_number=car.stint_number,
            compounds_used=list(car.compounds_used),
            pit_stops=car.pit_stops,
            pit_history=[
                PitStopRecordOut(
                    lap=record.lap,
                    lane_time_s=record.lane_time_s,
                    stationary_time_s=record.stationary_time_s,
                )
                for record in car.pit_history
            ],
            in_pit=car.in_pit,
            retired=car.retired,
            last_lap=car.last_lap,
            last_lap_time_s=car.last_lap_time_s,
        )


class RaceStateOut(BaseModel):
    session_key: int
    circuit_id: Optional[str] = None
    lap: int
    total_laps: Optional[int] = None
    track_status: str
    track_temp_c: Optional[float] = None
    air_temp_c: Optional[float] = None
    rainfall: Optional[bool] = None
    cars: dict[int, CarStateOut]
    state_version: int

    @classmethod
    def from_state(cls, state: Any) -> RaceStateOut:
        return cls(
            session_key=state.session_key,
            circuit_id=state.circuit_id,
            lap=state.lap,
            total_laps=state.total_laps,
            track_status=state.track_status,
            track_temp_c=state.track_temp_c,
            air_temp_c=state.air_temp_c,
            rainfall=state.rainfall,
            cars={driver: CarStateOut.from_car_state(car) for driver, car in state.cars.items()},
            state_version=state.state_version,
        )


class PositionOut(BaseModel):
    x: float
    y: float


class LiveFrameOut(BaseModel):
    """What the WebSocket actually pushes (T9's track map needs live (x, y)
    per car, which RaceState deliberately excludes — see design doc §6 and
    f1api.live.ReplaySession's docstring)."""

    state: RaceStateOut
    positions: dict[int, PositionOut]


class GeometryOut(BaseModel):
    circuit_id: str
    version: int
    length_m: float
    x: list[float]
    y: list[float]
    s: list[float]
    sector_boundaries_s: tuple[float, float]
    rotation_deg: float
    pit_lane_x: Optional[list[float]] = None
    pit_lane_y: Optional[list[float]] = None
    pit_lane_s: Optional[list[float]] = None

    @classmethod
    def from_geometry(cls, geometry: Any) -> GeometryOut:
        def _to_list(arr: Any) -> Optional[list[float]]:
            return arr.tolist() if arr is not None else None

        return cls(
            circuit_id=geometry.circuit_id,
            version=geometry.version,
            length_m=geometry.length_m,
            x=geometry.x.tolist(),
            y=geometry.y.tolist(),
            s=geometry.s.tolist(),
            sector_boundaries_s=geometry.sector_boundaries_s,
            rotation_deg=geometry.rotation_deg,
            pit_lane_x=_to_list(geometry.pit_lane_x),
            pit_lane_y=_to_list(geometry.pit_lane_y),
            pit_lane_s=_to_list(geometry.pit_lane_s),
        )


class ReplayCreateRequest(BaseModel):
    session_key: int
    speed: float = 1.0


class ReplayCreateResponse(BaseModel):
    live_id: str


class ReplayControlRequest(BaseModel):
    action: str  # "play" | "pause" | "seek" | "speed"
    speed: Optional[float] = None
    seek_ts: Optional[datetime] = None
