"""GET /circuits/{id}/geometry — T8."""

from __future__ import annotations

from f1ingest.geometry_store import load_geometry
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from f1api.db import get_db_engine
from f1api.schemas import GeometryOut

router = APIRouter(tags=["circuits"])


@router.get("/circuits/{circuit_id}/geometry", response_model=GeometryOut)
def get_circuit_geometry(circuit_id: str, engine: Engine = Depends(get_db_engine)) -> GeometryOut:
    with engine.connect() as conn:
        geometry = load_geometry(conn, circuit_id)
    if geometry is None:
        raise HTTPException(
            status_code=404, detail=f"no geometry stored for circuit {circuit_id!r}"
        )
    return GeometryOut.from_geometry(geometry)
