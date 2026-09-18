"""Projection: (x, y) -> s. Nearest-neighbour search over the resampled
polyline (via a KD-tree), refined by exact point-to-segment projection on
the winning point's two adjacent segments — this is what gets projection
error down from the ~L/N sampling quantisation (≈2.9 m for a 5.8 km circuit
at 2000 points) to a small fraction of a metre. See
docs/f1-strategy-foundation.md §5 and geometry.py's module docstring for the
real validation numbers from T7.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.spatial import cKDTree

from f1track.geometry import CircuitGeometry


def _project_onto_segment(
    px: float, py: float, ax: float, ay: float, a_s: float, bx: float, by: float, b_s: float
) -> tuple[float, float]:
    abx, aby = bx - ax, by - ay
    seg_len_sq = abx * abx + aby * aby
    if seg_len_sq == 0:
        return a_s, math.hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x, proj_y = ax + t * abx, ay + t * aby
    dist = math.hypot(px - proj_x, py - proj_y)
    proj_s = a_s + t * (b_s - a_s)
    return proj_s, dist


class CircuitProjector:
    def __init__(self, geometry: CircuitGeometry) -> None:
        self._geometry = geometry
        self._tree = cKDTree(np.column_stack([geometry.x, geometry.y]))

    def project(self, x: float, y: float) -> tuple[float, float]:
        """Returns `(s, distance_m)`: the arc-length position of the
        closest point on the polyline to `(x, y)`, and how far off the
        track centreline `(x, y)` actually was."""
        geometry = self._geometry
        n = len(geometry.x)
        _, nearest_idx = self._tree.query([x, y])
        nearest_idx = int(nearest_idx)

        best_s = float(geometry.s[nearest_idx])
        best_dist = math.hypot(geometry.x[nearest_idx] - x, geometry.y[nearest_idx] - y)

        for start in (nearest_idx - 1, nearest_idx):
            i = start % n
            j = (start + 1) % n
            # The segment from the last point back to the first wraps
            # around s=0; treat its far end as length_m, not 0, so the
            # interpolated s stays monotonic through the wrap.
            b_s = geometry.length_m if j == 0 else float(geometry.s[j])
            proj_s, dist = _project_onto_segment(
                x,
                y,
                float(geometry.x[i]),
                float(geometry.y[i]),
                float(geometry.s[i]),
                float(geometry.x[j]),
                float(geometry.y[j]),
                b_s,
            )
            if dist < best_dist:
                best_dist = dist
                best_s = proj_s % geometry.length_m

        return best_s, best_dist
