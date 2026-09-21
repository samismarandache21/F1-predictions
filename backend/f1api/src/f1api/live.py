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

import logging
import os
import threading
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from f1ingest.db.schema import laps as laps_table
from f1ingest.db.schema import sessions as sessions_table
from f1ingest.publisher import InMemoryPublisher
from f1state.builder import LapCompletedTrigger, RaceStateBuilder
from f1state.state import RaceState
from sqlalchemy import Engine, func, select

# f1ingest.adapters.replay, f1core.config.season, and (M2, T5)
# f1state.predictions are imported lazily, inside
# LiveReplayManager.create()/_team_lookup() below, not at module level:
# each pulls in f1core (constructing real domain events, the season
# config, or f1core.Value/Snapshot respectively) — all need Python >= 3.10
# to resolve (same limitation as the rest of f1core). Keeping them out of
# this module's top level means ReplaySession and LiveReplayManager's
# class definitions (and everything except an actual `create()` call) stay
# testable ahead of the real 3.12 toolchain — see the T8/phase-2 T5
# summaries.

# backend/f1api/src/f1api/live.py -> repo root is 4 parents up (see
# f1ingest.cli's identical pattern).
_REPO_ROOT = Path(__file__).resolve().parents[4]

logger = logging.getLogger(__name__)

# The stored data starts ~55 minutes before lap 1 (cars parked in the garage), so a replay
# begins this long before the first lap instead - at 1x the default would otherwise be an
# hour of an empty map. The user can still seek; this is only where playback starts.
_LEAD_IN_BEFORE_LAP_1 = timedelta(seconds=120)


def _config_dir() -> Path:
    """F1_CONFIG_DIR wins: inside the api container, `_REPO_ROOT` resolves to `/` (the
    package lives at /app/f1api/src/...), not the repo, so the default would point nowhere."""
    return Path(os.environ.get("F1_CONFIG_DIR", str(_REPO_ROOT / "config")))


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
        self,
        session_key: int,
        clock: Any,
        builder: RaceStateBuilder,
        initial_state: RaceState,
        predictions: Optional[Any] = None,
    ) -> None:
        self.session_key = session_key
        self.clock = clock
        self._builder = builder
        self._state = initial_state
        self._predictions = predictions
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
        with fake events. `self._predictions` (a
        f1state.predictions.PredictionPipeline, or None in tests/M1-only
        use) is driven the same way, purely through the duck-typed
        LapCompletedTrigger it reacts to — see docs/plan/phase-2.md T5."""
        for event in events:
            with self._lock:
                if event.type == "location_update":
                    self._positions[event.driver] = (event.x_m, event.y_m)
                    continue

                self._state, triggers = self._builder.apply(self._state, event)
                if self._predictions is None:
                    continue
                for trigger in triggers:
                    if not isinstance(trigger, LapCompletedTrigger):
                        continue
                    car = self._state.car(trigger.driver)
                    try:
                        resolved = self._predictions.on_lap_completed(
                            car, event, total_laps=self._state.total_laps
                        )
                    except Exception:
                        # This runs on a daemon thread: an uncaught error here would
                        # silently end the whole replay. Predictions are additive
                        # (CLAUDE.md rule 7) - log and keep the timing data flowing.
                        logger.exception(
                            "prediction failed for driver %s lap %s", trigger.driver, trigger.lap
                        )
                        continue
                    self._state = self._builder.apply_predictions(
                        self._state, trigger.driver, resolved
                    )


class LiveReplayManager:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._sessions: dict[str, ReplaySession] = {}

    def create(self, session_key: int, speed: float = 1.0) -> str:
        from f1ingest.adapters.replay import DbRowSource, ReplayAdapter
        from f1state.predictions import PredictionPipeline

        row = self._session_row(session_key)
        if row is None:
            raise KeyError(f"session {session_key} not found")

        rows = DbRowSource(self._engine)
        publisher = InMemoryPublisher()
        adapter = ReplayAdapter(rows, publisher, speed=speed)
        clock = adapter.prepare(session_key)  # blocks briefly: fetches + sorts all events
        race_start = self._first_lap_start(session_key)
        if race_start is not None:
            clock.seek(race_start - _LEAD_IN_BEFORE_LAP_1)

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

        predictions = PredictionPipeline(_config_dir())

        live_id = uuid.uuid4().hex
        session = ReplaySession(session_key, clock, builder, initial_state, predictions)
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

    def _first_lap_start(self, session_key: int) -> Optional[datetime]:
        with self._engine.connect() as conn:
            return conn.execute(
                select(func.min(laps_table.c.ts)).where(laps_table.c.session_key == session_key)
            ).scalar_one_or_none()

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
        config_path = _config_dir() / "seasons" / f"{season}.yaml"
        if not config_path.exists():
            return {}, {}
        from f1core.config.season import load_season

        season_config = load_season(config_path)
        team_by_driver = season_config.team_by_driver_number(round_no)
        colour_by_driver = {
            driver: season_config.team(team_id).colour for driver, team_id in team_by_driver.items()
        }
        return team_by_driver, colour_by_driver
