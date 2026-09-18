"""ReplaySession.consume() is pure enough to test with fake duck-typed
events (same technique as f1state's builder tests, T6) — no f1core import
needed here."""

from __future__ import annotations

from dataclasses import dataclass

from f1api.live import ReplaySession
from f1state.builder import RaceStateBuilder
from f1state.state import RaceState


@dataclass(frozen=True)
class _FakeLap:
    driver: int
    lap: int
    position: int = 1
    type: str = "lap_completed"
    lap_time_s: float = 90.0
    gap_to_leader_s: float = 0.0
    interval_s: float = 0.0
    compound: str = "MEDIUM"
    tyre_age_laps: int = 1
    track_status: str = "GREEN"
    is_pit_out_lap: bool = False
    is_pit_in_lap: bool = False


@dataclass(frozen=True)
class _FakeLocation:
    driver: int
    x_m: float
    y_m: float
    type: str = "location_update"


def _session() -> ReplaySession:
    return ReplaySession(9912, clock=None, builder=RaceStateBuilder(), initial_state=RaceState(session_key=9912))


def test_consume_applies_events_and_updates_state() -> None:
    session = _session()

    session.consume([_FakeLap(driver=1, lap=1), _FakeLap(driver=1, lap=2, position=2)])

    assert session.state.lap == 2
    assert session.state.car(1).position == 2


def test_state_property_returns_an_immutable_snapshot() -> None:
    session = _session()
    session.consume([_FakeLap(driver=1, lap=1)])

    snapshot = session.state
    session.consume([_FakeLap(driver=1, lap=2)])

    # The earlier snapshot must not have been affected by the later update.
    assert snapshot.lap == 1
    assert session.state.lap == 2


def test_location_updates_are_tracked_separately_from_race_state() -> None:
    session = _session()

    session.consume(
        [_FakeLocation(driver=1, x_m=120.5, y_m=-30.2), _FakeLap(driver=1, lap=1, position=1)]
    )

    assert session.positions == {1: (120.5, -30.2)}
    assert session.state.lap == 1  # location_update never touches RaceState


def test_positions_property_returns_a_copy() -> None:
    session = _session()
    session.consume([_FakeLocation(driver=1, x_m=1.0, y_m=2.0)])

    snapshot = session.positions
    session.consume([_FakeLocation(driver=1, x_m=99.0, y_m=99.0)])

    assert snapshot == {1: (1.0, 2.0)}
    assert session.positions == {1: (99.0, 99.0)}
