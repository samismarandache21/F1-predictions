"""The replay clock: drives a pre-built, deterministic event sequence at a
configurable speed with play/pause/seek, publishing each event as it comes
due. See docs/plan/phase-1.md T5 ("speed 1-50x, pause, seek").

Determinism (CLAUDE.md rule 4) lives in `build_event_sequence`
(f1ingest.adapters.replay), not here — this class is about *when* to
publish events already in a fixed order, not what order they're in.
Real-time waiting is injected (`sleep`) so tests run instantly instead of
waiting out real race durations.

`DomainEvent` is only imported under `TYPE_CHECKING` — see publisher.py's
docstring for why.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from time import sleep as real_sleep
from typing import TYPE_CHECKING

from f1ingest.publisher import EventPublisher

if TYPE_CHECKING:
    from f1core.events import DomainEvent

MIN_SPEED = 1.0
MAX_SPEED = 50.0
_PAUSE_POLL_S = 0.05


class ReplayClock:
    def __init__(
        self,
        events: Sequence[DomainEvent],
        publisher: EventPublisher,
        *,
        speed: float = 1.0,
        sleep: Callable[[float], None] = real_sleep,
    ) -> None:
        self._events = list(events)
        self._timestamps = [e.ts for e in self._events]
        self._publisher = publisher
        self._sleep = sleep
        self._index = 0
        self.paused = False
        # State on `self`, not a local in run(): a seek() called mid-run
        # (from another thread/caller while a generator is in flight) must
        # be able to reset it, or the next event's delta would be computed
        # against a stale timestamp from before the jump.
        self._last_published_ts: datetime | None = None
        self.speed = speed

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        if not (MIN_SPEED <= value <= MAX_SPEED):
            raise ValueError(f"speed must be within [{MIN_SPEED}, {MAX_SPEED}], got {value}")
        self._speed = value

    @property
    def position(self) -> int:
        return self._index

    def play(self) -> None:
        self.paused = False

    def pause(self) -> None:
        self.paused = True

    def seek(self, ts: datetime) -> None:
        """Jump to the first event at or after `ts`. Events before the seek
        point are not (re-)published, and the clock does not sleep to
        "catch up" through the interval it just skipped."""
        self._index = bisect_left(self._timestamps, ts)
        self._last_published_ts = None

    def run(self, *, should_stop: Callable[[], bool] = lambda: False) -> Iterator[DomainEvent]:
        """Yield events in order, sleeping between them scaled by `speed`.
        A generator so a caller (an asyncio task or worker thread) can drive
        it cooperatively and stop early via `should_stop`.
        """
        while self._index < len(self._events) and not should_stop():
            if self.paused:
                self._sleep(_PAUSE_POLL_S)
                continue
            event = self._events[self._index]
            if self._last_published_ts is not None:
                delta_s = (event.ts - self._last_published_ts).total_seconds()
                if delta_s > 0:
                    self._sleep(delta_s / self.speed)
            self._publisher.publish(event)
            self._last_published_ts = event.ts
            self._index += 1
            yield event
