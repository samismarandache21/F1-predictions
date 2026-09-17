from __future__ import annotations

from dataclasses import dataclass

import pytest

from f1ingest.publisher import InMemoryPublisher, topic_for


@dataclass(frozen=True)
class _FakeEvent:
    type: str


@pytest.mark.parametrize(
    ("event_type", "expected_topic"),
    [
        ("lap_completed", "timing"),
        ("location_update", "timing"),
        ("pit_stop", "pit"),
        ("race_control", "race_control"),
        ("weather", "weather"),
    ],
)
def test_topic_for_matches_design_doc_topics(event_type: str, expected_topic: str) -> None:
    assert topic_for(_FakeEvent(type=event_type)) == expected_topic


def test_in_memory_publisher_records_events_in_order() -> None:
    publisher = InMemoryPublisher()
    e1, e2 = _FakeEvent(type="weather"), _FakeEvent(type="lap_completed")

    publisher.publish(e1)
    publisher.publish(e2)

    assert publisher.events == [e1, e2]
