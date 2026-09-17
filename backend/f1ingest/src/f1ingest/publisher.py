"""Event publishing: the abstraction that lets ReplayAdapter and (later,
M6) OpenF1LiveAdapter be indistinguishable to the rest of the system
(docs/f1-strategy-design.md §4.1). Redis Streams is the real transport
(design doc §4.1: topics timing/pit/race_control/weather/manual_input);
InMemoryPublisher exists for tests and local demos without Redis running.

`DomainEvent` is only imported under `TYPE_CHECKING`: this module needs no
real f1core.events objects at runtime (publish() just needs `.type`, which
any of the event dataclasses provide), which keeps it independently
testable without pulling in f1core's pydantic-based submodules — see the
T5 summary for why that matters right now.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from f1core.events import DomainEvent

_TOPIC_BY_EVENT_TYPE = {
    "lap_completed": "timing",
    "location_update": "timing",
    "pit_stop": "pit",
    "race_control": "race_control",
    "weather": "weather",
}


def topic_for(event: DomainEvent) -> str:
    return _TOPIC_BY_EVENT_TYPE[event.type]


class EventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class InMemoryPublisher:
    """Records published events in order. Used by tests, and by anything
    driving a replay without a running Redis instance."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


class RedisStreamPublisher:
    def __init__(self, redis_client: Any, *, stream_prefix: str) -> None:
        self._redis = redis_client
        self._stream_prefix = stream_prefix

    def publish(self, event: DomainEvent) -> None:
        stream_key = f"{self._stream_prefix}:{topic_for(event)}"
        self._redis.xadd(stream_key, {"payload": json.dumps(asdict(event), default=str)})
