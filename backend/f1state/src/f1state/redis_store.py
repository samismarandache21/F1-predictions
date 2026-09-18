"""Persists the current RaceState to Redis, keyed by session (design doc
§4.1/§6: the race state service "maintains the authoritative RaceState
snapshot in Redis"). Plain JSON, not RedisJSON or a hash: the whole state
is small (22 cars) and replacing it wholesale on each update is simpler and
correct, at the cost of some redundant bytes over the wire — an acceptable
trade for M1.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from f1state.state import CarState, RaceState


def _key(session_key: int) -> str:
    return f"race_state:{session_key}"


class RedisStateStore:
    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    def save(self, state: RaceState) -> None:
        self._redis.set(_key(state.session_key), json.dumps(asdict(state)))

    def load(self, session_key: int) -> RaceState | None:
        raw = self._redis.get(_key(session_key))
        if raw is None:
            return None
        payload = json.loads(raw)

        cars: dict[int, CarState] = {}
        for driver_str, car_payload in payload["cars"].items():
            car_payload = dict(car_payload)
            # JSON has no tuple type; round-tripping through it turns
            # compounds_used back into a list, so it must be coerced back.
            car_payload["compounds_used"] = tuple(car_payload.get("compounds_used", ()))
            cars[int(driver_str)] = CarState(**car_payload)

        payload = {**payload, "cars": cars}
        return RaceState(**payload)
