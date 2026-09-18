"""FastAPI REST + WebSocket gateway (T8). Session/circuit/replay endpoints
live in their own router modules; this module wires them together and
owns the LiveReplayManager singleton (on `app.state`, not a module
global — see live_router.py's docstring for why).
"""

from __future__ import annotations

from typing import Optional

from f1ingest.db.engine import get_engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from f1api import circuits, live_router, sessions
from f1api.live import LiveReplayManager
from f1api.settings import get_settings


def create_app(*, engine: Optional[Engine] = None) -> FastAPI:
    """`engine` is injectable so tests can point the whole app at an
    isolated database (e.g. an in-memory SQLite instance) instead of the
    real Postgres from DATABASE_URL."""
    settings = get_settings()
    app = FastAPI(title="F1 Strategy API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_engine = engine or get_engine()
    app.state.db_engine = db_engine
    app.state.live_manager = LiveReplayManager(db_engine)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(sessions.router)
    app.include_router(circuits.router)
    app.include_router(live_router.router)

    return app


app = create_app()
