"""Shared f1core fixtures for f1models' Component-level tests
(test_tyre.py, test_pace.py). NOT RUNNABLE in this dev environment — see
test_tyre.py's module docstring for why.

f1core imports are deferred into each fixture body (not module level):
this conftest.py is loaded for every test in this directory, including
test_degradation_math.py/test_pace_math.py, which are pure-NumPy and must
stay collectible without f1core (see f1models/__init__.py's docstring for
why f1core needs Python >= 3.11 here).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from f1core.registry import VariableRegistry
    from f1core.snapshot import Snapshot
    from f1core.values import Value

_VARS_YAML = (
    "- id: car.lap.observation\n  scope: car_lap\n  dtype: object\n  unit: none\n"
    "  kinds_allowed: [observed]\n  depends_on: []\n"
    "  affects: [car.tyre.deg_rate, car.tyre.deg_cliff_lap, car.pace.base_s]\n"
    "  description: x\n"
    "- id: car.tyre.deg_rate\n  scope: car_stint\n  dtype: float\n  unit: s_per_lap\n"
    "  kinds_allowed: [prior, estimated]\n  depends_on: [car.lap.observation]\n"
    "  affects: [car.pace.base_s]\n  description: y\n"
    "- id: car.tyre.deg_cliff_lap\n  scope: car_stint\n  dtype: float\n  unit: laps\n"
    "  kinds_allowed: [prior, estimated]\n  depends_on: [car.lap.observation]\n"
    "  affects: []\n  description: z\n"
    "- id: car.pace.base_s\n  scope: car\n  dtype: float\n  unit: _s\n"
    "  kinds_allowed: [prior, estimated]\n"
    "  depends_on: [car.lap.observation, car.tyre.deg_rate]\n"
    "  affects: []\n  description: w\n"
)

_T0 = datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc)


@pytest.fixture
def registry(tmp_path: Path) -> VariableRegistry:
    from f1core.registry import VariableRegistry

    (tmp_path / "vars.yaml").write_text(_VARS_YAML)
    return VariableRegistry.load(tmp_path)


@pytest.fixture
def lap_observation() -> Callable[..., Value]:
    from f1core.values import Kind, Value

    def _make(
        driver: str,
        lap: int,
        *,
        tyre_age_laps: int,
        lap_time_s: float,
        is_clean_air: bool = True,
        stint_number: int = 1,
    ) -> Value:
        return Value(
            var_id="car.lap.observation",
            scope_id=f"{driver}:{lap}",
            kind=Kind.OBSERVED,
            data={
                "lap": lap,
                "tyre_age_laps": tyre_age_laps,
                "compound": "medium",
                "lap_time_s": lap_time_s,
                "is_clean_air": is_clean_air,
                "stint_number": stint_number,
            },
            source="test",
            state_version="s0",
            ts=_T0 + timedelta(seconds=90 * lap),
        )

    return _make


@pytest.fixture
def snapshot_factory(registry: VariableRegistry) -> Callable[[list[Value]], Snapshot]:
    from f1core.snapshot import Snapshot

    def _make(observations: list[Value]) -> Snapshot:
        snapshot = Snapshot(state_version="s0", registry=registry)
        return snapshot.with_updates(observations, state_version="s1")

    return _make
