"""The T7 'Done when' check: projection error under 5 m median on held-out
laps. Validated live during T7 (median 0.092 m on lap 3, held out from the
lap-2-built geometry, against real Monza 2025 telemetry) before being
written as an assertion here.
"""

from __future__ import annotations

import numpy as np
import pytest

from f1track.geometry import build_circuit_geometry
from f1track.projection import CircuitProjector


@pytest.fixture
def monza_geometry(monza_lap2_samples, lap2_sector_durations):
    sector_1_s, sector_2_s = lap2_sector_durations
    return build_circuit_geometry(
        monza_lap2_samples,
        circuit_id="monza",
        version=1,
        lap_start_ts=monza_lap2_samples[0].ts,
        sector_1_duration_s=sector_1_s,
        sector_2_duration_s=sector_2_s,
        built_from_session_key=9912,
    )


def test_median_projection_error_on_held_out_lap_is_under_5m(
    monza_geometry, monza_lap3_samples
) -> None:
    projector = CircuitProjector(monza_geometry)

    errors = [projector.project(p.x_m, p.y_m)[1] for p in monza_lap3_samples]

    assert np.median(errors) < 5.0
    assert np.max(errors) < 20.0  # no wildly-off outlier from a wraparound bug


def test_projecting_a_point_already_on_the_polyline_has_near_zero_error(
    monza_geometry,
) -> None:
    projector = CircuitProjector(monza_geometry)

    for idx in (0, 100, 500, 1500):
        s, dist = projector.project(float(monza_geometry.x[idx]), float(monza_geometry.y[idx]))
        assert dist < 1e-6
        assert s == pytest.approx(float(monza_geometry.s[idx]), abs=1e-6)


def test_projection_across_the_wraparound_segment_is_continuous(monza_geometry) -> None:
    """A point just before the closing segment (last resampled point) and a
    point just after it (first resampled point) should project to s values
    near length_m and near 0 respectively, not jump discontinuously."""
    projector = CircuitProjector(monza_geometry)

    s_last, _ = projector.project(float(monza_geometry.x[-1]), float(monza_geometry.y[-1]))
    s_first, _ = projector.project(float(monza_geometry.x[0]), float(monza_geometry.y[0]))

    assert s_last > monza_geometry.length_m * 0.99
    assert s_first < monza_geometry.length_m * 0.01


def test_a_point_far_off_track_reports_a_large_distance(monza_geometry) -> None:
    projector = CircuitProjector(monza_geometry)

    far_x = float(monza_geometry.x[0]) + 100_000.0
    far_y = float(monza_geometry.y[0]) + 100_000.0
    _, dist = projector.project(far_x, far_y)

    assert dist > 100_000.0 * 0.9  # roughly the offset applied, not near zero
