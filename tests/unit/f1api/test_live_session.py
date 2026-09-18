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


def _session(predictions: object = None) -> ReplaySession:
    return ReplaySession(
        9912,
        clock=None,
        builder=RaceStateBuilder(),
        initial_state=RaceState(session_key=9912),
        predictions=predictions,
    )


class _FakeValue:
    def __init__(self, data: object, kind: str = "estimated", uncertainty: float = 0.1) -> None:
        self.data = data
        self.kind = kind
        self.uncertainty = uncertainty


class _FakePredictionPipeline:
    """Duck-typed stand-in for f1state.predictions.PredictionPipeline —
    real f1core.Value construction isn't needed to test that
    ReplaySession.consume drives it correctly on lap_completed events."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def on_lap_completed(
        self, car: object, event: object, total_laps: object = None
    ) -> dict[str, _FakeValue]:
        self.calls.append((event.driver, event.lap))
        return {"car.tyre.deg_rate": _FakeValue(0.05)}


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


def test_predictions_pipeline_is_driven_on_lap_completed_and_mirrored_onto_state() -> None:
    predictions = _FakePredictionPipeline()
    session = _session(predictions)

    session.consume([_FakeLap(driver=1, lap=1)])

    assert predictions.calls == [(1, 1)]
    assert session.state.car(1).deg_rate_s_per_lap == 0.05
    assert session.state.car(1).deg_rate_kind == "estimated"


def test_predictions_pipeline_is_not_driven_by_non_lap_events() -> None:
    predictions = _FakePredictionPipeline()
    session = _session(predictions)

    session.consume([_FakeLocation(driver=1, x_m=1.0, y_m=2.0)])

    assert predictions.calls == []


def test_no_predictions_pipeline_is_a_no_op_like_before_m2() -> None:
    session = _session(predictions=None)

    session.consume([_FakeLap(driver=1, lap=1)])

    assert session.state.car(1).deg_rate_s_per_lap is None
