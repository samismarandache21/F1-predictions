"""Uses real recorded fixtures from tests/fixtures/openf1/ (session_key=9912,
the actual Phase 1 fixture race: 2025 Italian GP at Monza), captured live
against https://api.openf1.org during T4.
"""

from __future__ import annotations

from f1ingest.adapters.openf1_hist import OpenF1HistoricalAdapter


def _adapter(load_fixture, fake_client_cls) -> OpenF1HistoricalAdapter:  # type: ignore[no-untyped-def]
    responses = {
        "/sessions": load_fixture("openf1/sessions.json"),
        "/drivers": load_fixture("openf1/drivers.json"),
        "/laps": load_fixture("openf1/laps.json"),
        "/stints": load_fixture("openf1/stints.json"),
        "/pit": load_fixture("openf1/pit.json"),
        "/position": load_fixture("openf1/position.json"),
        "/intervals": load_fixture("openf1/intervals.json"),
        "/race_control": load_fixture("openf1/race_control.json"),
        "/weather": load_fixture("openf1/weather.json"),
        "/location": load_fixture("openf1/location.json"),
    }
    return OpenF1HistoricalAdapter(fake_client_cls(responses))


def test_build_rows_produces_a_session_row(load_fixture, fake_client_cls) -> None:  # type: ignore[no-untyped-def]
    adapter = _adapter(load_fixture, fake_client_cls)

    result = adapter.build_rows(
        session_key=9912, circuit_id="monza", season=2025, round_no=16
    )

    sessions = result.rows["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["session_key"] == 9912
    assert sessions[0]["circuit_id"] == "monza"
    assert sessions[0]["season"] == 2025
    assert sessions[0]["round"] == 16
    assert sessions[0]["session_type"] == "Race"


def test_total_laps_is_the_highest_observed_lap_number(load_fixture, fake_client_cls) -> None:  # type: ignore[no-untyped-def]
    adapter = _adapter(load_fixture, fake_client_cls)
    result = adapter.build_rows(session_key=9912, circuit_id="monza", season=2025, round_no=16)

    # The trimmed laps fixture only goes up to lap 9 (driver 30's pit lap).
    assert result.rows["sessions"][0]["total_laps"] == 9


def test_is_pit_in_lap_is_derived_from_the_pit_table(load_fixture, fake_client_cls) -> None:  # type: ignore[no-untyped-def]
    """Real case from the fixture: driver 30 pitted on lap 9 (pit.json), and
    laps.json includes that exact (driver, lap) row. OpenF1's /laps has no
    is_pit_in_lap field at all — this must come from the join."""
    adapter = _adapter(load_fixture, fake_client_cls)
    result = adapter.build_rows(session_key=9912, circuit_id="monza", season=2025, round_no=16)

    laps_by_key = {(lap["driver_number"], lap["lap_number"]): lap for lap in result.rows["laps"]}
    assert laps_by_key[(30, 9)]["is_pit_in_lap"] is True
    assert laps_by_key[(1, 1)]["is_pit_in_lap"] is False


def test_lap_fields_match_the_recorded_fixture(load_fixture, fake_client_cls) -> None:  # type: ignore[no-untyped-def]
    adapter = _adapter(load_fixture, fake_client_cls)
    result = adapter.build_rows(session_key=9912, circuit_id="monza", season=2025, round_no=16)

    lap1 = next(
        lap
        for lap in result.rows["laps"]
        if lap["driver_number"] == 1 and lap["lap_number"] == 1
    )
    assert lap1["lap_time_s"] == 87.498
    assert lap1["sector_1_s"] == 29.893
    assert lap1["is_pit_out_lap"] is False


def test_malformed_lap_is_quarantined_not_crashed(fake_client_cls, load_fixture) -> None:  # type: ignore[no-untyped-def]
    responses = {
        "/sessions": load_fixture("openf1/sessions.json"),
        "/drivers": load_fixture("openf1/drivers.json"),
        "/laps": [{"driver_number": None, "lap_number": 1, "date_start": "2025-09-07T13:00:00Z"}],
        "/stints": [],
        "/pit": [],
        "/position": [],
        "/intervals": [],
        "/race_control": [],
        "/weather": [],
        "/location": [],
    }
    adapter = OpenF1HistoricalAdapter(fake_client_cls(responses))

    result = adapter.build_rows(session_key=9912, circuit_id="monza", season=2025, round_no=16)

    assert result.rows.get("laps", []) == []
    assert len(result.quarantined) == 1
    assert result.quarantined[0].table_name == "laps"
