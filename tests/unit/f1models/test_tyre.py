"""Component-level tests for TyreDegEstimator.

NOT RUNNABLE in this dev environment: constructing real f1core.Snapshot/
Value objects requires importing f1core, which needs Python >= 3.11 here
(see f1models/__init__.py and tyre.py's module docstrings). Written and
hand-traced against f1core.snapshot/values/registry's actual code, in the
same style as tests/unit/f1core/test_orchestrator.py; run this once the
project's real 3.12 toolchain is installed.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from f1core.snapshot import Snapshot
from f1core.values import Kind, Value
from f1models.tyre import (
    ESTIMATED_UNCERTAINTY,
    GENERIC_PRIOR_CLIFF_LAP,
    GENERIC_PRIOR_K1_S_PER_LAP,
    PRIOR_UNCERTAINTY,
    DegradationPrior,
    TyreDegEstimator,
)


def test_no_history_returns_no_values(snapshot_factory: Callable[[list[Value]], Snapshot]) -> None:
    snapshot = snapshot_factory([])
    result = TyreDegEstimator().compute(snapshot, "44")
    assert result == {}


def test_below_min_clean_laps_falls_back_to_prior(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    observations = [
        lap_observation("44", lap, tyre_age_laps=lap - 1, lap_time_s=90.0) for lap in range(1, 4)
    ]
    snapshot = snapshot_factory(observations)

    result = TyreDegEstimator().compute(snapshot, "44")

    assert result["car.tyre.deg_rate"].kind == Kind.PRIOR
    assert result["car.tyre.deg_rate"].data == GENERIC_PRIOR_K1_S_PER_LAP
    assert result["car.tyre.deg_rate"].uncertainty == PRIOR_UNCERTAINTY
    assert result["car.tyre.deg_cliff_lap"].kind == Kind.PRIOR
    assert result["car.tyre.deg_cliff_lap"].data == GENERIC_PRIOR_CLIFF_LAP


def test_custom_prior_is_used_below_min_clean_laps(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    observations = [lap_observation("44", 1, tyre_age_laps=0, lap_time_s=90.0)]
    snapshot = snapshot_factory(observations)
    prior = DegradationPrior(k1_s_per_lap=0.11, cliff_lap=30)

    result = TyreDegEstimator(prior=prior).compute(snapshot, "44")

    assert result["car.tyre.deg_rate"].data == 0.11
    assert result["car.tyre.deg_cliff_lap"].data == 30


def test_enough_clean_laps_estimates_from_real_monza_data(
    fixtures_dir: Path,
    lap_observation: Callable[..., Value],
    snapshot_factory: Callable[[list[Value]], Snapshot],
) -> None:
    fixture_path = fixtures_dir / "openf1" / "monza_2025_driver1_stint1_laps.json"
    laps = json.loads(fixture_path.read_text())
    observations = [
        lap_observation(
            "1",
            lap["lap_number"],
            tyre_age_laps=lap["lap_number"] - 1,
            lap_time_s=lap["lap_duration"],
        )
        for lap in laps
    ]
    snapshot = snapshot_factory(observations)

    result = TyreDegEstimator().compute(snapshot, "1")

    # Locks in the same real-data result degradation_math's own tests
    # validate directly (fuel-corrected linear slope ~= +0.028 s/lap).
    assert result["car.tyre.deg_rate"].kind == Kind.ESTIMATED
    assert result["car.tyre.deg_rate"].data == pytest.approx(0.028, abs=0.01)
    assert result["car.tyre.deg_rate"].uncertainty == ESTIMATED_UNCERTAINTY
    # Cliff stays a fixed prior in M2 v1 even when the rate is estimated.
    assert result["car.tyre.deg_cliff_lap"].kind == Kind.PRIOR


def test_dirty_air_laps_are_excluded_from_the_fit(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    clean = [
        lap_observation("44", lap, tyre_age_laps=lap - 1, lap_time_s=90.0 + 0.1 * (lap - 1))
        for lap in range(1, 7)
    ]
    dirty = [lap_observation("44", 7, tyre_age_laps=6, lap_time_s=95.0, is_clean_air=False)]
    snapshot = snapshot_factory(clean + dirty)

    result = TyreDegEstimator(min_clean_laps=5).compute(snapshot, "44")

    assert result["car.tyre.deg_rate"].kind == Kind.ESTIMATED


def test_only_current_stint_laps_are_used(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    stint1 = [
        lap_observation("44", lap, tyre_age_laps=lap - 1, lap_time_s=90.0, stint_number=1)
        for lap in range(1, 6)
    ]
    stint2 = [
        lap_observation("44", 20, tyre_age_laps=0, lap_time_s=91.0, stint_number=2),
        lap_observation("44", 21, tyre_age_laps=1, lap_time_s=91.0, stint_number=2),
    ]
    snapshot = snapshot_factory(stint1 + stint2)

    result = TyreDegEstimator().compute(snapshot, "44")

    # Only 2 clean laps in the current (second) stint: below the default
    # min_clean_laps of 5, so this must fall back to the prior rather than
    # fitting across the stint boundary.
    assert result["car.tyre.deg_rate"].kind == Kind.PRIOR
