"""Component-level tests for PaceEstimator.

NOT RUNNABLE in this dev environment — see test_tyre.py's module docstring
for why (constructing f1core.Snapshot/Value needs Python >= 3.11 here).
Written and hand-traced against f1core.snapshot/values/registry's actual
code and against f1models.pace_math, which test_pace_math.py does exercise
directly; run this once the project's real 3.12 toolchain is installed.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from f1core.snapshot import Snapshot
from f1core.values import Kind, Value
from f1models.degradation_math import fuel_corrected_lap_time
from f1models.pace import ESTIMATED_UNCERTAINTY_S, PRIOR_UNCERTAINTY_S, PaceEstimator
from f1models.pace_math import DEFAULT_EWMA_ALPHA, ewma, tyre_corrected_lap_time
from f1models.tyre import GENERIC_PRIOR_K1_S_PER_LAP


def test_no_history_returns_no_values(snapshot_factory: Callable[[list[Value]], Snapshot]) -> None:
    snapshot = snapshot_factory([])
    result = PaceEstimator().compute(snapshot, "44")
    assert result == {}


def test_below_min_clean_laps_uses_prior_kind(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    observations = [lap_observation("44", 1, tyre_age_laps=0, lap_time_s=90.0)]
    snapshot = snapshot_factory(observations)

    result = PaceEstimator().compute(snapshot, "44")

    assert result["car.pace.base_s"].kind == Kind.PRIOR
    assert result["car.pace.base_s"].uncertainty == PRIOR_UNCERTAINTY_S


def test_falls_back_to_the_generic_tyre_prior_when_deg_rate_is_unresolved(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    """No car.tyre.deg_rate value in the snapshot yet (e.g. the very first
    lap of the very first stint, before TyreDegEstimator has ever run for
    this scope_id) must not crash — it should fall back to the same
    generic prior tyre.py itself falls back to."""
    observations = [
        lap_observation("44", lap, tyre_age_laps=lap - 1, lap_time_s=90.0 + 0.1 * (lap - 1))
        for lap in range(1, 4)
    ]
    snapshot = snapshot_factory(observations)
    assert snapshot.get("car.tyre.deg_rate", "44") is None

    result = PaceEstimator().compute(snapshot, "44")

    expected_corrected = [
        tyre_corrected_lap_time(
            fuel_corrected_lap_time(90.0 + 0.1 * (lap - 1), lap),
            lap - 1,
            GENERIC_PRIOR_K1_S_PER_LAP,
        )
        for lap in range(1, 4)
    ]
    assert result["car.pace.base_s"].data == pytest.approx(
        ewma(expected_corrected, DEFAULT_EWMA_ALPHA)
    )


def test_only_clean_air_laps_feed_the_ewma(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    clean = [
        lap_observation("44", lap, tyre_age_laps=lap - 1, lap_time_s=90.0) for lap in range(1, 4)
    ]
    dirty = [lap_observation("44", 4, tyre_age_laps=3, lap_time_s=200.0, is_clean_air=False)]
    snapshot = snapshot_factory(clean + dirty)

    result = PaceEstimator().compute(snapshot, "44")

    # A 200s "lap" (e.g. behind a Safety Car) would have wrecked the EWMA
    # if it leaked in; the flat, all-90s clean history keeps it at ~90.
    assert result["car.pace.base_s"].data == pytest.approx(90.0, abs=1.0)


def test_reaching_min_clean_laps_switches_to_estimated_kind(
    lap_observation: Callable[..., Value], snapshot_factory: Callable[[list[Value]], Snapshot]
) -> None:
    observations = [
        lap_observation("44", lap, tyre_age_laps=lap - 1, lap_time_s=90.0) for lap in range(1, 4)
    ]
    snapshot = snapshot_factory(observations)

    result = PaceEstimator(min_clean_laps=3).compute(snapshot, "44")

    assert result["car.pace.base_s"].kind == Kind.ESTIMATED
    assert result["car.pace.base_s"].uncertainty == ESTIMATED_UNCERTAINTY_S
