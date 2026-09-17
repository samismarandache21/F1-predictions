"""Uses a lightweight duck-typed stand-in for DomainEvent (any object with
.ts/.type/.driver) rather than the real f1core.events dataclasses: this
lets the clock's timing logic — the most bug-prone part of T5 — be executed
now, ahead of the real f1core-dependent code in adapters/replay.py. See
that module's docstring for why the real dataclasses can't be exercised in
this environment yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from f1ingest.clock import ReplayClock
from f1ingest.publisher import InMemoryPublisher

_T0 = datetime(2025, 9, 7, 13, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _FakeEvent:
    ts: datetime
    type: str = "lap_completed"
    driver: int = 1


def _events(*offsets_s: float) -> list[_FakeEvent]:
    return [_FakeEvent(ts=_T0 + timedelta(seconds=s)) for s in offsets_s]


class _FakeSleeper:
    """Records requested sleep durations; can run a side effect after each
    call (e.g. to simulate another thread un-pausing the clock)."""

    def __init__(self, on_sleep=None) -> None:  # type: ignore[no-untyped-def]
        self.calls: list[float] = []
        self._on_sleep = on_sleep

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if self._on_sleep is not None:
            self._on_sleep(len(self.calls))


def test_events_are_published_in_order() -> None:
    events = _events(0, 5, 10)
    publisher = InMemoryPublisher()
    clock = ReplayClock(events, publisher, sleep=_FakeSleeper())

    list(clock.run())

    assert publisher.events == events


def test_first_event_does_not_sleep() -> None:
    events = _events(0, 5)
    publisher = InMemoryPublisher()
    sleeper = _FakeSleeper()
    clock = ReplayClock(events, publisher, sleep=sleeper)

    list(clock.run())

    assert sleeper.calls == [5.0]


def test_sleep_duration_scales_with_speed() -> None:
    events = _events(0, 10)
    publisher = InMemoryPublisher()
    sleeper = _FakeSleeper()
    clock = ReplayClock(events, publisher, speed=10.0, sleep=sleeper)

    list(clock.run())

    assert sleeper.calls == [1.0]  # 10s gap / 10x speed


@pytest.mark.parametrize("bad_speed", [0.0, 0.999, 50.001, -5])
def test_speed_out_of_range_is_rejected(bad_speed: float) -> None:
    with pytest.raises(ValueError):
        ReplayClock([], InMemoryPublisher(), speed=bad_speed)


def test_pause_blocks_until_resumed() -> None:
    events = _events(0, 5)
    publisher = InMemoryPublisher()
    clock_box: list[ReplayClock] = []

    def on_sleep(call_count: int) -> None:
        if call_count >= 2:  # resume after two pause-polls
            clock_box[0].play()

    sleeper = _FakeSleeper(on_sleep=on_sleep)
    clock = ReplayClock(events, publisher, sleep=sleeper)
    clock_box.append(clock)
    clock.pause()

    list(clock.run())

    assert publisher.events == events
    assert sleeper.calls[0] == pytest.approx(0.05)
    assert sleeper.calls[1] == pytest.approx(0.05)


def test_seek_skips_earlier_events_without_publishing_them() -> None:
    events = _events(0, 5, 10, 15)
    publisher = InMemoryPublisher()
    clock = ReplayClock(events, publisher, sleep=_FakeSleeper())

    clock.seek(_T0 + timedelta(seconds=10))
    list(clock.run())

    assert publisher.events == events[2:]


def test_seek_does_not_sleep_through_the_skipped_interval() -> None:
    events = _events(0, 5, 100, 105)
    publisher = InMemoryPublisher()
    sleeper = _FakeSleeper()
    clock = ReplayClock(events, publisher, sleep=sleeper)

    clock.seek(_T0 + timedelta(seconds=100))
    list(clock.run())

    assert sleeper.calls == [5.0]  # only the gap between the two post-seek events


def test_seek_mid_run_resets_the_reference_timestamp() -> None:
    """Regression test: seeking while a run() generator is already in
    flight must not compute the next delta against a stale pre-seek
    timestamp, which would otherwise produce a huge, wrong sleep."""
    events = _events(0, 5, 200, 205)
    publisher = InMemoryPublisher()
    sleeper = _FakeSleeper()
    clock = ReplayClock(events, publisher, sleep=sleeper)

    gen = clock.run()
    next(gen)  # publishes events[0] @ t=0, no sleep
    next(gen)  # sleeps 5s, publishes events[1] @ t=5

    clock.seek(_T0 + timedelta(seconds=200))
    next(gen)  # must publish events[2] immediately, no 195s catch-up sleep
    next(gen)  # sleeps 5s (200 -> 205), publishes events[3]

    assert publisher.events == events
    assert sleeper.calls == [5.0, 5.0]


def test_should_stop_ends_the_run_early() -> None:
    events = _events(0, 5, 10)
    publisher = InMemoryPublisher()
    clock = ReplayClock(events, publisher, sleep=_FakeSleeper())

    list(clock.run(should_stop=lambda: clock.position >= 2))

    assert publisher.events == events[:2]
