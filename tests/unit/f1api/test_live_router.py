"""Exercises the API wiring (routing, serialization, the WebSocket push
loop) with a ReplaySession injected directly, bypassing
LiveReplayManager.create() — which needs a real database and f1core.events
construction to actually run a replay (unverified in this environment; see
f1api.live's module docstring). This is the T8 'Done when' WebSocket smoke
test: a real FastAPI app, a real WebSocket handshake, receiving a real
position/state frame.
"""

from __future__ import annotations

from typing import Optional

import pytest
from starlette.websockets import WebSocketDisconnect

from f1api.live import ReplaySession
from f1state.builder import RaceStateBuilder
from f1state.state import CarState, RaceState


class _FakeClock:
    def __init__(self) -> None:
        self.played = False
        self.paused_ = False
        self.speed = 1.0
        self.sought = None

    def play(self) -> None:
        self.played = True

    def pause(self) -> None:
        self.paused_ = True

    def seek(self, ts: object) -> None:
        self.sought = ts


def _inject_session(
    app, live_id: str, state: RaceState, clock: Optional[_FakeClock] = None
) -> ReplaySession:
    session = ReplaySession(state.session_key, clock or _FakeClock(), RaceStateBuilder(), state)
    app.state.live_manager._sessions[live_id] = session
    return session


def test_get_live_state_returns_current_state(app, client) -> None:
    state = RaceState(session_key=9912, lap=5, track_status="GREEN")
    state = state.with_car(CarState(driver=1, position=1))
    _inject_session(app, "abc123", state)

    response = client.get("/live/abc123/state")

    assert response.status_code == 200
    body = response.json()
    assert body["lap"] == 5
    assert body["cars"]["1"]["position"] == 1


def test_get_live_state_unknown_id_is_404(client) -> None:
    response = client.get("/live/does-not-exist/state")

    assert response.status_code == 404


def test_control_play_pause_speed_dispatch_to_the_clock(app, client) -> None:
    clock = _FakeClock()
    _inject_session(app, "abc123", RaceState(session_key=9912), clock=clock)

    r_pause = client.post("/replays/abc123/control", json={"action": "pause"})
    r_play = client.post("/replays/abc123/control", json={"action": "play"})
    r_speed = client.post("/replays/abc123/control", json={"action": "speed", "speed": 10.0})

    assert r_pause.status_code == 200
    assert clock.paused_ is True
    assert r_play.status_code == 200
    assert clock.played is True
    assert r_speed.status_code == 200
    assert clock.speed == 10.0


def test_control_seek_dispatches_to_the_clock(app, client) -> None:
    clock = _FakeClock()
    _inject_session(app, "abc123", RaceState(session_key=9912), clock=clock)

    response = client.post(
        "/replays/abc123/control", json={"action": "seek", "seek_ts": "2025-09-07T13:05:00Z"}
    )

    assert response.status_code == 200
    assert clock.sought is not None


def test_control_unknown_live_id_is_404(client) -> None:
    response = client.post("/replays/nope/control", json={"action": "play"})

    assert response.status_code == 404


def test_control_unknown_action_is_400(app, client) -> None:
    _inject_session(app, "abc123", RaceState(session_key=9912))

    response = client.post("/replays/abc123/control", json={"action": "not-a-real-action"})

    assert response.status_code == 400


def test_control_speed_action_without_value_is_400(app, client) -> None:
    _inject_session(app, "abc123", RaceState(session_key=9912))

    response = client.post("/replays/abc123/control", json={"action": "speed"})

    assert response.status_code == 400


def test_websocket_receives_a_state_frame_with_positions(app, client) -> None:
    """T8's 'Done when': a WebSocket smoke test receives position frames."""
    state = RaceState(session_key=9912, lap=3)
    state = state.with_car(CarState(driver=44, position=2, compound="HARD"))
    session = _inject_session(app, "abc123", state)
    session._positions[44] = (120.5, -30.2)  # location_update events bypass RaceState entirely

    with client.websocket_connect("/live/abc123/stream") as ws:
        frame = ws.receive_json()

    assert frame["state"]["lap"] == 3
    assert frame["state"]["cars"]["44"]["position"] == 2
    assert frame["state"]["cars"]["44"]["compound"] == "HARD"
    assert frame["positions"]["44"] == {"x": 120.5, "y": -30.2}


def test_websocket_unknown_live_id_is_rejected(client) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/live/does-not-exist/stream") as ws:
            ws.receive_json()


def test_websocket_frame_includes_a_populated_prediction(app, client) -> None:
    """docs/plan/phase-2.md T6's 'Done when': the same live-router pattern
    covers a car with M2 prediction fields set, riding the existing 4 Hz
    WS stream (no new endpoint)."""
    state = RaceState(session_key=9912, lap=10)
    state = state.with_car(
        CarState(
            driver=1,
            deg_rate_s_per_lap=0.028,
            deg_rate_kind="estimated",
            deg_uncertainty=0.02,
            predicted_lap_time_s=91.4,
            predicted_finish_time_s=4820.5,
            prediction_kind="predicted",
        )
    )
    _inject_session(app, "abc123", state)

    with client.websocket_connect("/live/abc123/stream") as ws:
        frame = ws.receive_json()

    car = frame["state"]["cars"]["1"]
    assert car["deg_rate_s_per_lap"] == 0.028
    assert car["deg_rate_kind"] == "estimated"
    assert car["deg_uncertainty"] == 0.02
    assert car["predicted_lap_time_s"] == 91.4
    assert car["predicted_finish_time_s"] == 4820.5
    assert car["prediction_kind"] == "predicted"


def test_websocket_frame_has_null_predictions_for_a_car_with_none_yet(app, client) -> None:
    state = RaceState(session_key=9912, lap=1)
    state = state.with_car(CarState(driver=1))
    _inject_session(app, "abc123", state)

    with client.websocket_connect("/live/abc123/stream") as ws:
        frame = ws.receive_json()

    car = frame["state"]["cars"]["1"]
    assert car["deg_rate_s_per_lap"] is None
    assert car["prediction_kind"] is None
