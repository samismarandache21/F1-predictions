"""Router for POST /replays, POST /replays/{id}/control, GET /live/{id}/state,
and WS /live/{id}/stream (T8). The LiveReplayManager singleton lives on
`app.state` (set in main.create_app), not a module-level global, so tests
can spin up independent app instances with independent managers.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from f1api.live import LiveReplayManager
from f1api.schemas import (
    LiveFrameOut,
    PositionOut,
    RaceStateOut,
    ReplayControlRequest,
    ReplayCreateRequest,
    ReplayCreateResponse,
)

router = APIRouter(tags=["live"])

# Design doc §8: the WebSocket "pushes state deltas and car positions at 4 Hz".
_STREAM_INTERVAL_S = 0.25


def get_manager(request: Request) -> LiveReplayManager:
    return request.app.state.live_manager  # type: ignore[no-any-return]


def get_manager_ws(websocket: WebSocket) -> LiveReplayManager:
    return websocket.app.state.live_manager  # type: ignore[no-any-return]


@router.post("/replays", response_model=ReplayCreateResponse)
def create_replay(
    request: ReplayCreateRequest, manager: LiveReplayManager = Depends(get_manager)
) -> ReplayCreateResponse:
    try:
        live_id = manager.create(request.session_key, speed=request.speed)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReplayCreateResponse(live_id=live_id)


@router.post("/replays/{live_id}/control")
def control_replay(
    live_id: str,
    request: ReplayControlRequest,
    manager: LiveReplayManager = Depends(get_manager),
) -> dict[str, str]:
    try:
        manager.control(live_id, request.action, speed=request.speed, seek_ts=request.seek_ts)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown live_id {live_id!r}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/live/{live_id}/state", response_model=RaceStateOut)
def get_live_state(live_id: str, manager: LiveReplayManager = Depends(get_manager)) -> RaceStateOut:
    session = manager.get(live_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"unknown live_id {live_id!r}")
    return RaceStateOut.from_state(session.state)


@router.websocket("/live/{live_id}/stream")
async def stream_live_state(
    websocket: WebSocket, live_id: str, manager: LiveReplayManager = Depends(get_manager_ws)
) -> None:
    session = manager.get(live_id)
    if session is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    try:
        while True:
            frame = LiveFrameOut(
                state=RaceStateOut.from_state(session.state),
                positions={
                    driver: PositionOut(x=x, y=y) for driver, (x, y) in session.positions.items()
                },
            )
            await websocket.send_json(frame.model_dump(mode="json"))
            await asyncio.sleep(_STREAM_INTERVAL_S)
    except (WebSocketDisconnect, RuntimeError):
        pass
