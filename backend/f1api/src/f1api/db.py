"""Shared DB engine dependency for FastAPI routes. Reads from `app.state`
(set once in main.create_app) rather than calling f1ingest's global
`get_engine()` directly — that's what lets tests point the whole app at an
isolated database (e.g. in-memory SQLite) via `create_app(engine=...)`."""

from __future__ import annotations

from fastapi import Request, WebSocket
from sqlalchemy import Engine


def get_db_engine(request: Request) -> Engine:
    return request.app.state.db_engine  # type: ignore[no-any-return]


def get_db_engine_ws(websocket: WebSocket) -> Engine:
    return websocket.app.state.db_engine  # type: ignore[no-any-return]
