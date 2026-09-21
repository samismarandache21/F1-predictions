"""NOTE ON EXECUTION: could not be run in this development environment —
see f1ingest.adapters.replay's module docstring. Importing f1core.events
pulls in f1core's __init__.py, which eagerly imports pydantic-based
submodules needing Python >= 3.10 to resolve their type annotations (the
same limitation as f1core's own T3 test suite). Re-run once `uv sync` has
provisioned the project's real Python 3.12. The row-shapes below mirror
T4's real recorded fixtures (tests/fixtures/openf1/), and the mapping logic
was hand-traced against them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from f1ingest.adapters.replay import ReplayAdapter, build_event_sequence
from f1ingest.publisher import InMemoryPublisher

_T0 = datetime(2025, 9, 7, 13, 0, 0, tzinfo=timezone.utc)


def _ts(offset_s: float) -> datetime:
    return _T0 + timedelta(seconds=offset_s)


class _FakeRowSource:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self._tables = tables

    def fetch(self, table_name: str, session_key: int) -> list[dict[str, Any]]:
        return self._tables.get(table_name, [])


def _sample_tables() -> dict[str, list[dict[str, Any]]]:
    """Shaped after the real Monza 2025 fixtures in tests/fixtures/openf1/:
    driver 30 pits on lap 9 (matches tests/fixtures/openf1/pit.json) and
    starts stint 2 on lap 10 (matches tests/fixtures/openf1/stints.json)."""
    return {
        "laps": [
            {
                "driver_number": 1,
                "lap_number": 1,
                "ts": _ts(0),
                "lap_time_s": 87.498,
                "sector_1_s": 29.893,
                "sector_2_s": 29.088,
                "sector_3_s": 28.517,
                "position": 1,
                "gap_to_leader_s": 0.0,
                "interval_s": 0.0,
                "compound": "MEDIUM",
                "tyre_age_laps": 1,
                "track_status": "GREEN",
                "is_pit_out_lap": False,
                "is_pit_in_lap": False,
            },
            {
                "driver_number": 30,
                "lap_number": 9,
                "ts": _ts(5),
                "lap_time_s": 88.824,
                "sector_1_s": 27.362,
                "sector_2_s": 28.963,
                "sector_3_s": 32.499,
                "position": 5,
                "gap_to_leader_s": 10.0,
                "interval_s": 2.0,
                "compound": "MEDIUM",
                "tyre_age_laps": 8,
                "track_status": "GREEN",
                "is_pit_out_lap": False,
                "is_pit_in_lap": True,
            },
        ],
        "stints": [
            {
                "driver_number": 30,
                "stint_number": 2,
                "compound": "HARD",
                "tyre_age_at_start": 0,
                "lap_start": 10,
                "lap_end": 30,
            },
        ],
        "pit_stops": [
            {
                "driver_number": 30,
                "lap_number": 9,
                "ts": _ts(5),
                "lane_time_s": 24.156,
                "stationary_time_s": 2.2,
            },
        ],
        "race_control": [
            {
                "ts": _ts(1),
                "lap_number": 1,
                "category": "Flag",
                "flag": "GREEN",
                "scope": "Track",
                "driver_number": None,
                "message": "GREEN LIGHT - PIT EXIT OPEN",
            },
        ],
        "weather": [
            {
                "ts": _ts(0),
                "track_temp_c": 43.2,
                "air_temp_c": 28.5,
                "humidity_pct": 45.0,
                "rainfall": False,
                "wind_speed_ms": 1.8,
            },
        ],
        "location": [
            {"driver_number": 1, "ts": _ts(0.1), "x_m": 120.5, "y_m": -30.2, "z_m": None},
        ],
    }


def test_pit_stop_event_gets_new_compound_from_the_out_stint() -> None:
    events = build_event_sequence(9912, _FakeRowSource(_sample_tables()))

    pit_events = [e for e in events if e.type == "pit_stop"]
    assert len(pit_events) == 1
    assert pit_events[0].new_compound == "HARD"
    assert pit_events[0].new_tyre_age == 0


def test_events_are_sorted_by_timestamp_then_deterministic_type_order() -> None:
    events = build_event_sequence(9912, _FakeRowSource(_sample_tables()))

    # weather(t=0) and lap(t=0, driver 1) tie on ts; weather sorts first.
    assert [e.type for e in events[:2]] == ["weather", "lap_completed"]
    timestamps = [e.ts for e in events]
    assert timestamps == sorted(timestamps)


def test_build_event_sequence_is_deterministic_across_runs() -> None:
    """T5's 'replaying the same session twice gives an identical event
    sequence' requirement."""
    tables = _sample_tables()

    events_a = build_event_sequence(9912, _FakeRowSource(tables))
    events_b = build_event_sequence(9912, _FakeRowSource(tables))

    def _hash(events: list[Any]) -> str:
        payload = [asdict(e) for e in events]
        text = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(text.encode()).hexdigest()

    assert _hash(events_a) == _hash(events_b)
    assert events_a == events_b


def test_row_order_does_not_affect_the_final_sequence() -> None:
    tables = _sample_tables()
    reversed_tables = {name: list(reversed(rows)) for name, rows in tables.items()}

    events_forward = build_event_sequence(9912, _FakeRowSource(tables))
    events_reversed = build_event_sequence(9912, _FakeRowSource(reversed_tables))

    assert events_forward == events_reversed


def test_replay_adapter_stream_publishes_all_events_via_the_clock() -> None:
    publisher = InMemoryPublisher()
    adapter = ReplayAdapter(_FakeRowSource(_sample_tables()), publisher, speed=50.0)

    published = list(adapter.stream(9912))

    assert len(published) == 6  # 2 laps + 1 pit + 1 race_control + 1 weather + 1 location
    assert publisher.events == published
    assert adapter.clock is not None
    assert adapter.clock.position == len(published)


def test_zero_zero_location_fixes_are_not_replayed() -> None:
    """OpenF1 reports (0, 0) before a car has a GPS lock - thousands of rows in
    the real Monza data's pre-race stretch. They aren't positions; replaying
    them put dots at the origin (found on the first end-to-end run)."""
    tables = _sample_tables()
    tables["location"] = [
        {"driver_number": 1, "ts": _ts(1.0), "x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
        {"driver_number": 1, "ts": _ts(2.0), "x_m": 120.5, "y_m": -30.2, "z_m": 1.0},
    ]

    events = build_event_sequence(9912, _FakeRowSource(tables))

    locations = [e for e in events if e.type == "location_update"]
    assert [(e.x_m, e.y_m) for e in locations] == [(120.5, -30.2)]
