"""Real, in-memory SQLite database for API tests — no Docker/Postgres
needed. Works because `sessions` and `circuit_geometry` (unlike some other
tables in f1ingest.db.schema) use no Postgres-specific column types
(verified live during T8). Upsert helpers that use
`sqlalchemy.dialects.postgresql.insert` (save_geometry, pipeline.upsert_rows)
still need real Postgres — tests seed rows with plain `.insert()` instead.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from f1ingest.db.schema import circuit_geometry
from f1ingest.db.schema import sessions as sessions_table


@pytest.fixture
def sqlite_engine():
    # StaticPool: an in-memory SQLite DB is otherwise per-connection, so a
    # fresh `engine.connect()` (as every request handler does) would see an
    # empty database despite `.create()` having run moments earlier.
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    sessions_table.create(engine)
    circuit_geometry.create(engine)
    return engine


@pytest.fixture
def seeded_engine(sqlite_engine):
    with sqlite_engine.begin() as conn:
        conn.execute(
            sessions_table.insert().values(
                session_key=9912,
                meeting_key=1268,
                season=2025,
                round=16,
                circuit_id="monza",
                session_type="Race",
                session_name="Race",
                date_start=datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc),
                date_end=None,
                total_laps=53,
                source="openf1",
            )
        )
    return sqlite_engine


@pytest.fixture
def app(seeded_engine):
    from f1api.main import create_app

    return create_app(engine=seeded_engine)


@pytest.fixture
def client(app):
    return TestClient(app)
