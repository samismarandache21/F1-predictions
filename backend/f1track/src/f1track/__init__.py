"""Circuit geometry builder: polyline from location samples, projection.
Speed profiles (for ghost-car simulation) are M4 scope — see docs/backlog.md.
"""

from f1track.geometry import CircuitGeometry, LocationSample, build_circuit_geometry
from f1track.projection import CircuitProjector

__all__ = [
    "CircuitGeometry",
    "CircuitProjector",
    "LocationSample",
    "build_circuit_geometry",
]
