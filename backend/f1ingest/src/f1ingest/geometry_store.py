"""Persists f1track.CircuitGeometry to the circuit_geometry table (T4 owns
the DB schema; T7 owns geometry computation — see db/schema.py's comment).
"""

from __future__ import annotations

import json

import numpy as np
from sqlalchemy import Connection, desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from f1ingest.db.schema import circuit_geometry
from f1track import CircuitGeometry


def save_geometry(conn: Connection, geometry: CircuitGeometry) -> None:
    pit_lane_json = None
    if geometry.pit_lane_x is not None:
        pit_lane_json = json.dumps(
            {
                "x": geometry.pit_lane_x.tolist(),
                "y": geometry.pit_lane_y.tolist(),
                "s": geometry.pit_lane_s.tolist(),
            }
        )

    stmt = pg_insert(circuit_geometry).values(
        circuit_id=geometry.circuit_id,
        version=geometry.version,
        built_from_session_key=geometry.built_from_session_key,
        length_m=geometry.length_m,
        points_json=json.dumps(
            {"x": geometry.x.tolist(), "y": geometry.y.tolist(), "s": geometry.s.tolist()}
        ),
        sector_boundaries_s_json=json.dumps(list(geometry.sector_boundaries_s)),
        rotation_deg=geometry.rotation_deg,
        pit_lane_json=pit_lane_json,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["circuit_id", "version"],
        set_={
            "built_from_session_key": stmt.excluded.built_from_session_key,
            "length_m": stmt.excluded.length_m,
            "points_json": stmt.excluded.points_json,
            "sector_boundaries_s_json": stmt.excluded.sector_boundaries_s_json,
            "rotation_deg": stmt.excluded.rotation_deg,
            "pit_lane_json": stmt.excluded.pit_lane_json,
        },
    )
    conn.execute(stmt)


def load_geometry(
    conn: Connection, circuit_id: str, version: int | None = None
) -> CircuitGeometry | None:
    query = select(circuit_geometry).where(circuit_geometry.c.circuit_id == circuit_id)
    query = (
        query.where(circuit_geometry.c.version == version)
        if version is not None
        else query.order_by(desc(circuit_geometry.c.version)).limit(1)
    )
    row = conn.execute(query).mappings().first()
    if row is None:
        return None

    points = json.loads(row["points_json"])
    sector_boundaries = tuple(json.loads(row["sector_boundaries_s_json"]))
    pit_x = pit_y = pit_s = None
    if row["pit_lane_json"] is not None:
        pit_lane = json.loads(row["pit_lane_json"])
        pit_x = np.array(pit_lane["x"], dtype=float)
        pit_y = np.array(pit_lane["y"], dtype=float)
        pit_s = np.array(pit_lane["s"], dtype=float)

    return CircuitGeometry(
        circuit_id=row["circuit_id"],
        version=row["version"],
        built_from_session_key=row["built_from_session_key"],
        x=np.array(points["x"], dtype=float),
        y=np.array(points["y"], dtype=float),
        s=np.array(points["s"], dtype=float),
        length_m=row["length_m"],
        sector_boundaries_s=sector_boundaries,
        rotation_deg=row["rotation_deg"],
        pit_lane_x=pit_x,
        pit_lane_y=pit_y,
        pit_lane_s=pit_s,
    )
