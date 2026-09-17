"""Circuit config loader: metadata and priors. Geometry itself is not stored
here — it's built by f1track from a session's location samples (T7) and
versioned separately. See docs/f1-strategy-foundation.md §7 and
docs/f1-driver-circuit-intel.md §9.

Numeric prior fields are optional (`None`) on purpose for cold-start circuits
(Madring, Sepang): CLAUDE.md rule 7 ("degrade gracefully") means a missing
prior must be handled by falling back to a circuit-type-class prior with wide
uncertainty, not by inventing a number here.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class ValuePrior(BaseModel):
    value: float | None = None
    sd: float | None = None
    kind: str = "prior"
    note: str | None = None


class WeatherPrior(BaseModel):
    rain_risk: str
    forecast_source: str


class CircuitConfig(BaseModel):
    id: str
    name: str
    country: str
    type: str  # street | permanent | hybrid
    lat: float
    lon: float
    length_m: float | None = None
    laps: int | None = None
    pit_lane_loss_s: ValuePrior
    overtake_difficulty: ValuePrior
    sc_hazard_per_lap: ValuePrior
    deg_class: str
    weather: WeatherPrior
    cluster: str
    data_since: int


def load_circuit(path: Path) -> CircuitConfig:
    raw = yaml.safe_load(path.read_text())
    return CircuitConfig.model_validate(raw)


def load_all_circuits(directory: Path) -> dict[str, CircuitConfig]:
    return {(cfg := load_circuit(path)).id: cfg for path in sorted(directory.glob("*.yaml"))}
