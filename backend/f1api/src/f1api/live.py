"""Live replay management: backs POST /replays, POST /replays/{id}/control,
GET /live/{id}/state, and WS /live/{id}/stream (T8).

The event-driving logic (`ReplaySession.consume`) is deliberately separated
from the DB/threading wiring (`LiveReplayManager.create`) so it can be
tested with fake, duck-typed events — the same technique used for
f1state's builder in T6 — without needing a real database or f1core.events
construction. Actually running a replay end-to-end needs both; that part
is unverified in this environment for the same reason as anything else
touching f1core (see the T5-T8 summaries) but was reasoned through
carefully and follows the same patterns already validated elsewhere.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from f1ingest.db.schema import sessions as sessions_table
from f1ingest.publisher import InMemoryPublisher
from f1state.builder import RaceStateBuilder
from f1state.state import RaceState
from sqlalchemy import Engine, select

# f1ingest.adapters.replay and f1core.config.season are imported lazily,
# inside LiveReplayManager.create()/_team_lookup() below, not at module
# level: the former pulls in f1core.events (constructing real domain
# events), and the latter pulls in f1core's package init directly — both
# need Python >= 3.10 to resolve (same limitation as the rest of f1core).
# Keeping them out of this module's top level means ReplaySession and
# LiveReplayManager's class definitions (and everything except an actual
# `create()` call) stay testable ahead of the real 3.12 toolchain — see
# the T8 summary.

# backend/f1api/src/f1api/live.py -> repo root is 4 parents up (see
# f1ingest.cli's identical pattern).
_REPO_ROOT = Path(__file__).resolve().parents[4]


class ReplaySession:
    """One running replay: its clock (for control), its current RaceState,
    and the latest known (x, y) per car — read thread-safely via `.state`
    and `.positions`.

    `location_update` events never touch RaceState (design doc §6 has no
    location fields there — f1state.builder explicitly no-ops on them,
    T6), but the track map (T9) still needs them, so this class tracks
    them separately rather than teaching RaceStateBuilder about rendering
    concerns it shouldn't know about.
    """

    def __init__(
        self, session_key: int, clock: Any, builder: RaceStateBuilder, initial_state: RaceState
    ) -> None:
        self.session_key = session_key
        self.clock = clock
        self._builder = builder
        self._state = initial_state
        self._positions: dict[int, tuple[float, float]] = {}
        self._lock = threading.Lock()

    @property
    def state(self) -> RaceState:
        with self._lock:
            return self._state

    @property
    def positions(self) -> dict[int, tuple[float, float]]:
        with self._lock:
            return dict(self._positions)

    def consume(self, events: Iterable[Any]) -> None:
        """Apply each event as it arrives. Only needs RaceStateBuilder's
        duck-typed `event.type` dispatch (see f1state.builder) — no
        f1core import required here, which is what keeps this testable
        with fake events."""
        for event in events:
            with self._lock:
                if event.type == "location_update":
                    self._positions[event.driver] = (event.x_m, event.y_m)
                else:
                    self._state, _triggers = self._builder.apply(self._state, event)


class LiveReplayManager:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._sessions: dict[str, ReplaySession] = {}

    def create(self, session_key: int, speed: float = 1.0) -> str:
        from f1ingest.adapters.replay import DbRowSource, ReplayAdapter

        row = self._session_row(session_key)
        if row is None:
            raise KeyError(f"session {session_key} not found")

        rows = DbRowSource(self._engine)
        publisher = InMemoryPublisher()
        adapter = ReplayAdapter(rows, publisher, speed=speed)
        clock = adapter.prepare(session_key)  # blocks briefly: fetches + sorts all events

        team_by_driver_number, team_colour_by_driver_number = self._team_lookup(
            row["season"], row["round"]
        )
        builder = RaceStateBuilder(
            team_by_driver_number=team_by_driver_number,
            team_colour_by_driver_number=team_colour_by_driver_number,
        )
        initial_state = RaceState(
            session_key=session_key,
            circuit_id=row["circuit_id"],
            total_laps=row["total_laps"],
        )

        live_id = uuid.uuid4().hex
        session = ReplaySession(session_key, clock, builder, initial_state)
        self._sessions[live_id] = session

        thread = threading.Thread(
            target=session.consume, args=(adapter.stream(session_key),), daemon=True
        )
        thread.start()
        return live_id

    def get(self, live_id: str) -> Optional[ReplaySession]:
        return self._sessions.get(live_id)

    def control(
        self,
        live_id: str,
        action: str,
        *,
        speed: Optional[float] = None,
        seek_ts: Optional[datetime] = None,
    ) -> None:
        session = self.get(live_id)
        if session is None:
            raise KeyError(live_id)

        if action == "play":
            session.clock.play()
        elif action == "pause":
            session.clock.pause()
        elif action == "seek":
            if seek_ts is None:
                raise ValueError("the 'seek' action requires seek_ts")
            session.clock.seek(seek_ts)
        elif action == "speed":
            if speed is None:
                raise ValueError("the 'speed' action requires speed")
            session.clock.speed = speed
        else:
            raise ValueError(f"unknown action {action!r}")

    def _session_row(self, session_key: int) -> Optional[dict[str, Any]]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    select(sessions_table).where(sessions_table.c.session_key == session_key)
                )
                .mappings()
                .first()
            )
        return dict(row) if row is not None else None

    def _team_lookup(
        self, season: int, round_no: Optional[int]
    ) -> tuple[dict[int, str], dict[int, str]]:
        """Returns (team_by_driver_number, team_colour_by_driver_number).
        Colour is genuinely config data (same as team affiliation), so the
        track map (T9) gets it this way rather than needing its own
        endpoint or a client-side copy of the season config."""
        if round_no is None:
            return {}, {}
        config_path = _REPO_ROOT / "config" / "seasons" / f"{season}.yaml"
        if not config_path.exists():
            return {}, {}
        from f1core.config.season import load_season

        season_config = load_season(config_path)
        team_by_driver = season_config.team_by_driver_number(round_no)
        colour_by_driver = {
            driver: season_config.team(team_id).colour for driver, team_id in team_by_driver.items()
        }
        return team_by_driver, colour_by_driver
