"""Circuit geometry builder: turns one clean lap's location samples into a
closed, resampled polyline parametrised by cumulative distance `s`, plus
sector boundaries and a heading (`rotation_deg`). See
docs/f1-strategy-foundation.md §5 and docs/plan/phase-1.md T7.

Algorithm, validated live during T7 against the real 2025 Italian GP
(Monza, session_key=9912): smooth the raw (x, y) trace with a periodic
Savitzky-Golay filter, compute cumulative arc length, close the loop by
duplicating the first point at s=length_m, then fit a periodic cubic spline
directly parametrised by that arc length (no separate re-parametrisation
step needed, unlike a plain B-spline fit). Evaluating that spline at N
evenly-spaced arc-length values gives the resampled polyline.

Real numbers from that validation: a lap-2-built geometry gave a circuit
length of 5801.3 m against Monza's official 5793 m (0.14% error), and a
median projection error of 0.092 m on lap 3 (held out — a different lap,
not used to build the geometry) — far inside the < 5 m median target in
docs/plan/phase-1.md T7's "Done when".

No f1core/Pydantic dependency by design: this is pure numerical code
(numpy + scipy), independently testable without pulling in f1core's
Pydantic-based package init (see f1core.events' module docstring for why
that matters ahead of the project's real 3.12 toolchain being installed).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter

DEFAULT_RESAMPLE_POINTS = 2000
_SMOOTH_WINDOW = 9
_SMOOTH_POLYORDER = 2


@dataclass(frozen=True)
class LocationSample:
    ts: datetime
    x_m: float
    y_m: float


@dataclass(frozen=True)
class CircuitGeometry:
    circuit_id: str
    version: int
    built_from_session_key: int | None
    x: np.ndarray  # shape (N,), metres
    y: np.ndarray  # shape (N,), metres
    s: np.ndarray  # shape (N,), metres, 0..length_m, strictly increasing
    length_m: float
    # (end of sector 1, end of sector 2) as arc length; sector 3 runs from
    # the second value back to length_m (i.e. to the start/finish line).
    sector_boundaries_s: tuple[float, float]
    # Heading of the track at s=0 in the raw telemetry coordinate frame
    # (atan2 convention, degrees) — not true compass north (not derivable
    # from telemetry alone), but a fixed, deterministic value a renderer
    # can use to orient the map consistently.
    rotation_deg: float
    pit_lane_x: np.ndarray | None = None
    pit_lane_y: np.ndarray | None = None
    pit_lane_s: np.ndarray | None = None


def _smooth(values: np.ndarray, *, periodic: bool) -> np.ndarray:
    n = len(values)
    window = min(_SMOOTH_WINDOW, n if n % 2 == 1 else n - 1)
    if window < 3:
        return values.copy()
    polyorder = min(_SMOOTH_POLYORDER, window - 1)
    mode = "wrap" if periodic else "interp"
    return savgol_filter(values, window_length=window, polyorder=polyorder, mode=mode)


def _cumulative_distance(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    seg = np.hypot(np.diff(x), np.diff(y))
    return np.concatenate([[0.0], np.cumsum(seg)])


def build_circuit_geometry(
    samples: list[LocationSample],
    *,
    circuit_id: str,
    version: int,
    lap_start_ts: datetime,
    sector_1_duration_s: float,
    sector_2_duration_s: float,
    built_from_session_key: int | None = None,
    resample_points: int = DEFAULT_RESAMPLE_POINTS,
    pit_lane_samples: list[LocationSample] | None = None,
) -> CircuitGeometry:
    if len(samples) < 4:
        raise ValueError(f"need at least 4 location samples to build geometry, got {len(samples)}")

    ordered = sorted(samples, key=lambda p: p.ts)
    x_raw = np.array([p.x_m for p in ordered], dtype=float)
    y_raw = np.array([p.y_m for p in ordered], dtype=float)
    seconds = np.array([(p.ts - lap_start_ts).total_seconds() for p in ordered], dtype=float)

    x_smooth = _smooth(x_raw, periodic=True)
    y_smooth = _smooth(y_raw, periodic=True)

    s_raw = _cumulative_distance(x_smooth, y_smooth)
    closing_len = math.hypot(x_smooth[0] - x_smooth[-1], y_smooth[0] - y_smooth[-1])
    length_m = float(s_raw[-1] + closing_len)

    # Close the loop: duplicate the first point at s=length_m so a periodic
    # cubic spline can be fit directly against arc length, with no separate
    # arc-length re-parametrisation step afterward.
    s_closed = np.concatenate([s_raw, [length_m]])
    x_closed = np.concatenate([x_smooth, [x_smooth[0]]])
    y_closed = np.concatenate([y_smooth, [y_smooth[0]]])

    spline_x = CubicSpline(s_closed, x_closed, bc_type="periodic")
    spline_y = CubicSpline(s_closed, y_closed, bc_type="periodic")

    s_resampled = np.linspace(0.0, length_m, resample_points, endpoint=False)
    x_resampled = spline_x(s_resampled)
    y_resampled = spline_y(s_resampled)

    # Sector boundaries: find the arc-length position at the timestamp each
    # sector ends, using the SAME lap's own timing — not an assumed
    # constant-speed split of the lap time.
    sector_1_end_s = float(np.interp(sector_1_duration_s, seconds, s_raw))
    sector_2_end_s = float(np.interp(sector_1_duration_s + sector_2_duration_s, seconds, s_raw))

    rotation_deg = math.degrees(math.atan2(y_smooth[1] - y_smooth[0], x_smooth[1] - x_smooth[0]))

    pit_x = pit_y = pit_s = None
    if pit_lane_samples:
        pit_ordered = sorted(pit_lane_samples, key=lambda p: p.ts)
        px_raw = np.array([p.x_m for p in pit_ordered], dtype=float)
        py_raw = np.array([p.y_m for p in pit_ordered], dtype=float)
        pit_x = _smooth(px_raw, periodic=False)
        pit_y = _smooth(py_raw, periodic=False)
        pit_s = _cumulative_distance(pit_x, pit_y)

    return CircuitGeometry(
        circuit_id=circuit_id,
        version=version,
        built_from_session_key=built_from_session_key,
        x=x_resampled,
        y=y_resampled,
        s=s_resampled,
        length_m=length_m,
        sector_boundaries_s=(sector_1_end_s, sector_2_end_s),
        rotation_deg=rotation_deg,
        pit_lane_x=pit_x,
        pit_lane_y=pit_y,
        pit_lane_s=pit_s,
    )
