"""DB-touching test for circuit geometry persistence (T7). Skipped locally
when no database is reachable; runs for real in CI. See
tests/unit/f1ingest/test_db_upsert.py for the same pattern.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from sqlalchemy import create_engine, delete, select

from f1ingest.db.schema import circuit_geometry, metadata
from f1ingest.geometry_store import load_geometry, save_geometry
from f1track import CircuitGeometry

TEST_CIRCUIT_ID = "__test_monza__"


@pytest.fixture(scope="module")
def db_engine():  # type: ignore[no-untyped-def]
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set (run `docker compose up` + `make migrate` to enable)")
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database not reachable: {exc}")

    metadata.create_all(engine, checkfirst=True)
    yield engine

    with engine.begin() as conn:
        conn.execute(delete(circuit_geometry).where(circuit_geometry.c.circuit_id == TEST_CIRCUIT_ID))
    engine.dispose()


def _sample_geometry(version: int) -> CircuitGeometry:
    n = 50
    s = np.linspace(0.0, 1000.0, n, endpoint=False)
    return CircuitGeometry(
        circuit_id=TEST_CIRCUIT_ID,
        version=version,
        built_from_session_key=9912,
        x=np.cos(s / 1000.0 * 2 * np.pi) * 100,
        y=np.sin(s / 1000.0 * 2 * np.pi) * 100,
        s=s,
        length_m=1000.0,
        sector_boundaries_s=(300.0, 650.0),
        rotation_deg=12.5,
        pit_lane_x=np.array([1.0, 2.0, 3.0]),
        pit_lane_y=np.array([1.0, 1.0, 1.0]),
        pit_lane_s=np.array([0.0, 1.0, 2.0]),
    )


def test_save_then_load_round_trips_geometry(db_engine) -> None:  # type: ignore[no-untyped-def]
    geometry = _sample_geometry(version=1)

    with db_engine.begin() as conn:
        save_geometry(conn, geometry)

    with db_engine.connect() as conn:
        loaded = load_geometry(conn, TEST_CIRCUIT_ID, version=1)

    assert loaded is not None
    assert loaded.length_m == geometry.length_m
    assert loaded.sector_boundaries_s == geometry.sector_boundaries_s
    assert loaded.rotation_deg == geometry.rotation_deg
    assert np.allclose(loaded.x, geometry.x)
    assert np.allclose(loaded.y, geometry.y)
    assert np.allclose(loaded.pit_lane_x, geometry.pit_lane_x)


def test_load_without_version_returns_the_latest(db_engine) -> None:  # type: ignore[no-untyped-def]
    with db_engine.begin() as conn:
        save_geometry(conn, _sample_geometry(version=1))
        save_geometry(conn, _sample_geometry(version=2))

    with db_engine.connect() as conn:
        loaded = load_geometry(conn, TEST_CIRCUIT_ID)

    assert loaded is not None
    assert loaded.version == 2


def test_save_is_idempotent_on_conflict(db_engine) -> None:  # type: ignore[no-untyped-def]
    geometry = _sample_geometry(version=1)
    with db_engine.begin() as conn:
        save_geometry(conn, geometry)
        save_geometry(conn, geometry)  # re-run: must not raise a duplicate-key error

    with db_engine.connect() as conn:
        rows = conn.execute(
            select(circuit_geometry).where(circuit_geometry.c.circuit_id == TEST_CIRCUIT_ID)
        ).fetchall()

    assert len([r for r in rows if r.version == 1]) == 1


def test_load_returns_none_for_an_unknown_circuit(db_engine) -> None:  # type: ignore[no-untyped-def]
    with db_engine.connect() as conn:
        assert load_geometry(conn, "__does_not_exist__") is None
