from __future__ import annotations

from datetime import datetime, timedelta, timezone

from f1ingest.adapters.base import AdapterResult
from f1ingest.pipeline import _enrich_laps

_BASE_TS = datetime(2025, 9, 7, 13, 0, 0, tzinfo=timezone.utc)


def _ts(offset_s: float) -> datetime:
    return _BASE_TS + timedelta(seconds=offset_s)


def _lap(driver_number: int, lap_number: int, ts: datetime) -> dict:
    return {
        "driver_number": driver_number,
        "lap_number": lap_number,
        "ts": ts,
        "compound": None,
        "tyre_age_laps": None,
        "track_status": None,
    }


def test_lap_gets_compound_and_tyre_age_from_the_matching_stint() -> None:
    result = AdapterResult()
    result.add(
        "stints",
        {
            "driver_number": 1,
            "stint_number": 1,
            "compound": "MEDIUM",
            "tyre_age_at_start": 0,
            "lap_start": 1,
            "lap_end": 20,
        },
    )
    result.add(
        "stints",
        {
            "driver_number": 1,
            "stint_number": 2,
            "compound": "HARD",
            "tyre_age_at_start": 0,
            "lap_start": 21,
            "lap_end": 51,
        },
    )
    result.add("laps", _lap(1, 10, _ts(0)))
    result.add("laps", _lap(1, 25, _ts(1)))

    _enrich_laps(result)

    lap10, lap25 = result.rows["laps"]
    assert lap10["compound"] == "MEDIUM"
    assert lap10["tyre_age_laps"] == 9  # 0 + (10 - 1)
    assert lap25["compound"] == "HARD"
    assert lap25["tyre_age_laps"] == 4  # 0 + (25 - 21)


def test_lap_with_no_matching_stint_keeps_compound_none() -> None:
    result = AdapterResult()
    result.add("laps", _lap(1, 1, _ts(0)))

    _enrich_laps(result)

    assert result.rows["laps"][0]["compound"] is None


def test_track_status_defaults_to_green_with_no_race_control_events() -> None:
    result = AdapterResult()
    result.add("laps", _lap(1, 1, _ts(0)))

    _enrich_laps(result)

    assert result.rows["laps"][0]["track_status"] == "GREEN"


def test_track_status_reflects_the_most_recent_flag() -> None:
    result = AdapterResult()
    result.add(
        "race_control", {"ts": _ts(0), "category": "Flag", "flag": "YELLOW", "message": "YELLOW FLAG"}
    )
    result.add(
        "race_control", {"ts": _ts(10), "category": "Flag", "flag": "GREEN", "message": "CLEAR"}
    )
    result.add("laps", _lap(1, 1, _ts(5)))  # between the two flags
    result.add("laps", _lap(1, 2, _ts(20)))  # after both

    _enrich_laps(result)

    lap1, lap2 = result.rows["laps"]
    assert lap1["track_status"] == "YELLOW"
    assert lap2["track_status"] == "GREEN"


def test_safety_car_deployed_and_ending_messages_toggle_status() -> None:
    result = AdapterResult()
    result.add(
        "race_control",
        {"ts": _ts(0), "category": "SafetyCar", "flag": None, "message": "SAFETY CAR DEPLOYED"},
    )
    result.add(
        "race_control",
        {
            "ts": _ts(10),
            "category": "SafetyCar",
            "flag": None,
            "message": "SAFETY CAR ENDING",
        },
    )
    result.add("laps", _lap(1, 1, _ts(5)))
    result.add("laps", _lap(1, 2, _ts(15)))

    _enrich_laps(result)

    lap1, lap2 = result.rows["laps"]
    assert lap1["track_status"] == "SC"
    assert lap2["track_status"] == "GREEN"
