"""Builds and stores a circuit's geometry from an ingested session.

f1track.build_circuit_geometry (T7) and geometry_store.save_geometry (T7)
existed and were tested, but nothing ever called them, so `make ingest`
never produced geometry and GET /circuits/{id}/geometry always 404'd — found
on the first real end-to-end run. This is the missing glue: pick one clean,
representative lap out of the stored data and build the polyline from that
driver's own location trace for exactly that lap.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import Connection, Engine, and_, select

from f1ingest.db.schema import laps, location
from f1ingest.db.schema import sessions as sessions_table
from f1ingest.geometry_store import save_geometry
from f1track import CircuitGeometry, LocationSample, build_circuit_geometry


def select_reference_lap(conn: Connection, session_key: int) -> dict[str, Any] | None:
    """The fastest green-flag racing lap with complete sector timing: not a
    lap 1 standing start, not an in/out lap. Prefers green-flag laps but
    falls back to any complete lap if a session has none tagged."""
    base = and_(
        laps.c.session_key == session_key,
        laps.c.lap_number > 1,
        laps.c.lap_time_s.is_not(None),
        laps.c.sector_1_s.is_not(None),
        laps.c.sector_2_s.is_not(None),
        laps.c.is_pit_out_lap.is_(False),
        laps.c.is_pit_in_lap.is_(False),
    )
    for condition in (and_(base, laps.c.track_status == "GREEN"), base):
        row = (
            conn.execute(select(laps).where(condition).order_by(laps.c.lap_time_s.asc()).limit(1))
            .mappings()
            .first()
        )
        if row is not None:
            return dict(row)
    return None


def collect_lap_samples(conn: Connection, lap: dict[str, Any]) -> list[LocationSample]:
    """That driver's location trace between the lap's start and finish.
    (0, 0) fixes are dropped: OpenF1 emits them before a car has a GPS lock,
    and one would drag the whole spline toward the origin."""
    start = lap["ts"]
    end = start + timedelta(seconds=lap["lap_time_s"])
    rows = conn.execute(
        select(location.c.ts, location.c.x_m, location.c.y_m)
        .where(
            location.c.session_key == lap["session_key"],
            location.c.driver_number == lap["driver_number"],
            location.c.ts >= start,
            location.c.ts <= end,
        )
        .order_by(location.c.ts.asc())
    ).all()
    return [
        LocationSample(ts=ts, x_m=x_m, y_m=y_m) for ts, x_m, y_m in rows if (x_m, y_m) != (0.0, 0.0)
    ]


def build_and_store_geometry(
    engine: Engine, session_key: int, *, version: int = 1
) -> CircuitGeometry:
    with engine.begin() as conn:
        circuit_id = conn.execute(
            select(sessions_table.c.circuit_id).where(sessions_table.c.session_key == session_key)
        ).scalar_one_or_none()
        if circuit_id is None:
            raise ValueError(f"session {session_key} not found or has no circuit_id")

        lap = select_reference_lap(conn, session_key)
        if lap is None:
            raise ValueError(f"session {session_key} has no complete racing lap to build from")

        samples = collect_lap_samples(conn, lap)
        geometry = build_circuit_geometry(
            samples,
            circuit_id=circuit_id,
            version=version,
            lap_start_ts=lap["ts"],
            sector_1_duration_s=lap["sector_1_s"],
            sector_2_duration_s=lap["sector_2_s"],
            built_from_session_key=session_key,
        )
        save_geometry(conn, geometry)
    return geometry
