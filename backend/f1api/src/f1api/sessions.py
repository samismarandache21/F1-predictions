"""GET /sessions, GET /sessions/{session_key} — T8."""

from __future__ import annotations

from typing import Optional

from f1ingest.db.schema import sessions as sessions_table
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Engine, select

from f1api.db import get_db_engine
from f1api.schemas import SessionOut

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    year: Optional[int] = Query(default=None),
    session_type: Optional[str] = Query(default=None),
    engine: Engine = Depends(get_db_engine),
) -> list[SessionOut]:
    query = select(sessions_table)
    if year is not None:
        query = query.where(sessions_table.c.season == year)
    if session_type is not None:
        query = query.where(sessions_table.c.session_type == session_type)
    query = query.order_by(sessions_table.c.date_start)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [SessionOut(**row) for row in rows]


@router.get("/sessions/{session_key}", response_model=SessionOut)
def get_session(session_key: int, engine: Engine = Depends(get_db_engine)) -> SessionOut:
    with engine.connect() as conn:
        row = (
            conn.execute(select(sessions_table).where(sessions_table.c.session_key == session_key))
            .mappings()
            .first()
        )
    if row is None:
        raise HTTPException(status_code=404, detail=f"session {session_key} not found")
    return SessionOut(**row)
