from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from f1track.geometry import LocationSample


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_samples(fixtures_dir: Path, name: str) -> list[LocationSample]:
    raw = json.loads((fixtures_dir / "openf1" / name).read_text())
    return [LocationSample(ts=_parse_ts(p["date"]), x_m=p["x"] / 10.0, y_m=p["y"] / 10.0) for p in raw]


@pytest.fixture(scope="session")
def monza_lap2_samples(fixtures_dir: Path) -> list[LocationSample]:
    """Real 2025 Italian GP (Monza) telemetry, driver 1, lap 2 — used to
    *build* the geometry. Raw OpenF1 x/y are decimetres; see T7's summary
    for how that unit was discovered and fixed in the T4 ingestion adapter.
    """
    return _load_samples(fixtures_dir, "location_lap_driver1.json")


@pytest.fixture(scope="session")
def monza_lap3_samples(fixtures_dir: Path) -> list[LocationSample]:
    """The same driver's very next lap — genuinely held out, never used to
    build the geometry, for validating projection accuracy."""
    return _load_samples(fixtures_dir, "location_lap3_driver1.json")


@pytest.fixture(scope="session")
def lap2_sector_durations() -> tuple[float, float]:
    """Real sector 1/2 durations for lap 2 (driver 1, Monza 2025), from
    tests/fixtures/openf1/laps.json."""
    return 28.457, 28.843


@pytest.fixture(scope="session")
def monza_official_length_m() -> float:
    return 5793.0
