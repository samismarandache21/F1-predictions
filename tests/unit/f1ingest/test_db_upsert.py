"""DB-touching tests: schema creation and idempotent upsert (CLAUDE.md rule 8).
Skipped locally when no database is reachable (before `docker compose up` /
`make migrate`); run for real in CI against the timescale service container —
see .github/workflows/ci.yml. Never touches a live external API.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, delete, select

from f1ingest.db.schema import metadata, sessions
from f1ingest.pipeline import upsert_rows

TEST_SESSION_KEY = 999999001


@pytest.fixture(scope="module")
def db_engine():  # type: ignore[no-untyped-def]
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set (run `docker compose up` + `make migrate` to enable)")
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure as a skip
        pytest.skip(f"database not reachable: {exc}")

    metadata.create_all(engine, checkfirst=True)
    yield engine

    with engine.begin() as conn:
        conn.execute(delete(sessions).where(sessions.c.session_key == TEST_SESSION_KEY))
    engine.dispose()


def _session_row(total_laps: int) -> dict[str, object]:
    return {
        "session_key": TEST_SESSION_KEY,
        "meeting_key": 1268,
        "season": 2025,
        "round": 16,
        "circuit_id": "monza",
        "session_type": "Race",
        "session_name": "Race",
        "date_start": datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc),
        "date_end": None,
        "total_laps": total_laps,
        "source": "test",
    }


def test_upsert_then_reupsert_is_a_no_op(db_engine) -> None:  # type: ignore[no-untyped-def]
    row = _session_row(total_laps=53)

    with db_engine.begin() as conn:
        upsert_rows(conn, sessions, [row])
    with db_engine.begin() as conn:
        upsert_rows(conn, sessions, [row])  # re-run with identical data

    with db_engine.connect() as conn:
        rows = conn.execute(
            select(sessions).where(sessions.c.session_key == TEST_SESSION_KEY)
        ).fetchall()

    assert len(rows) == 1
    assert rows[0].total_laps == 53


def test_upsert_updates_changed_fields_on_conflict(db_engine) -> None:  # type: ignore[no-untyped-def]
    with db_engine.begin() as conn:
        upsert_rows(conn, sessions, [_session_row(total_laps=53)])
    with db_engine.begin() as conn:
        # Same natural key, corrected value — this is the "observed value gets
        # corrected on re-ingestion" case, not a duplicate.
        upsert_rows(conn, sessions, [_session_row(total_laps=51)])

    with db_engine.connect() as conn:
        rows = conn.execute(
            select(sessions).where(sessions.c.session_key == TEST_SESSION_KEY)
        ).fetchall()

    assert len(rows) == 1
    assert rows[0].total_laps == 51
