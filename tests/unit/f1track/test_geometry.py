"""Validated live during T7 against the real 2025 Italian GP (Monza,
session_key=9912): see f1track.geometry's module docstring for the exact
numbers this was checked against before being written as assertions here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from f1track.geometry import LocationSample, build_circuit_geometry


def test_length_is_close_to_the_official_circuit_length(
    monza_lap2_samples, lap2_sector_durations, monza_official_length_m
) -> None:
    sector_1_s, sector_2_s = lap2_sector_durations
    geometry = build_circuit_geometry(
        monza_lap2_samples,
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
    )

    # Real result during T7: 5801.3 m vs Monza's official 5793 m (0.14%).
    # 2% tolerance leaves headroom for future re-fetches of the fixture.
    assert geometry.length_m == pytest.approx(monza_official_length_m, rel=0.02)


def test_resampled_arrays_have_the_requested_length(
    monza_lap2_samples, lap2_sector_durations
) -> None:
    sector_1_s, sector_2_s = lap2_sector_durations
    geometry = build_circuit_geometry(
        monza_lap2_samples,
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
        resample_points=500,
    )

    assert len(geometry.x) == 500
    assert len(geometry.y) == 500
    assert len(geometry.s) == 500


def test_s_is_strictly_increasing_and_starts_at_zero(
    monza_lap2_samples, lap2_sector_durations
) -> None:
    sector_1_s, sector_2_s = lap2_sector_durations
    geometry = build_circuit_geometry(
        monza_lap2_samples,
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
    )

    assert geometry.s[0] == 0.0
    assert np.all(np.diff(geometry.s) > 0)
    assert geometry.s[-1] < geometry.length_m


def test_sector_boundaries_are_ordered_within_the_lap(
    monza_lap2_samples, lap2_sector_durations
) -> None:
    sector_1_s, sector_2_s = lap2_sector_durations
    geometry = build_circuit_geometry(
        monza_lap2_samples,
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
    )

    s1_end, s2_end = geometry.sector_boundaries_s
    assert 0.0 < s1_end < s2_end < geometry.length_m


def test_geometry_build_is_deterministic(monza_lap2_samples, lap2_sector_durations) -> None:
    sector_1_s, sector_2_s = lap2_sector_durations
    kwargs = dict(
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
    )
    a = build_circuit_geometry(monza_lap2_samples, **kwargs)
    b = build_circuit_geometry(monza_lap2_samples, **kwargs)

    assert a.length_m == b.length_m
    assert a.rotation_deg == b.rotation_deg
    assert np.array_equal(a.x, b.x)
    assert np.array_equal(a.y, b.y)


def test_raises_on_too_few_samples() -> None:
    samples = [
        LocationSample(ts=datetime(2025, 1, 1, tzinfo=timezone.utc), x_m=0.0, y_m=0.0),
        LocationSample(ts=datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc), x_m=1.0, y_m=1.0),
    ]
    with pytest.raises(ValueError, match="at least 4"):
        build_circuit_geometry(
            samples,
            circuit_id="monza",
            version=1,
            lap_start_ts=samples[0].ts,
            sector_1_duration_s=1.0,
            sector_2_duration_s=1.0,
        )


def test_pit_lane_geometry_when_samples_provided(
    monza_lap2_samples, lap2_sector_durations
) -> None:
    # Not a real pit lane trace, just enough points to exercise the code
    # path — real pit-lane extraction happens once a fixture with an actual
    # in/out lap is fetched (docs/backlog.md).
    sector_1_s, sector_2_s = lap2_sector_durations
    pit_samples = monza_lap2_samples[:40]

    geometry = build_circuit_geometry(
        monza_lap2_samples,
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
        pit_lane_samples=pit_samples,
    )

    assert geometry.pit_lane_x is not None
    assert len(geometry.pit_lane_x) == len(pit_samples)
    assert geometry.pit_lane_s[0] == 0.0
    assert np.all(np.diff(geometry.pit_lane_s) >= 0)


def test_no_pit_lane_samples_means_no_pit_lane_geometry(
    monza_lap2_samples, lap2_sector_durations
) -> None:
    sector_1_s, sector_2_s = lap2_sector_durations
    geometry = build_circuit_geometry(
        monza_lap2_samples,
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
    )

    assert geometry.pit_lane_x is None
    assert geometry.pit_lane_y is None
    assert geometry.pit_lane_s is None
