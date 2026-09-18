"""Includes a real-data check against the actual 2025 Italian GP (Monza,
session_key=9912, driver 1's opening stint) — see degradation_math.py's
module docstring for the exact numbers this was validated against before
being written as assertions here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from f1models.degradation_math import (
    MAX_PLAUSIBLE_K1_S_PER_LAP,
    MIN_PLAUSIBLE_K1_S_PER_LAP,
    clamp_degradation_rate,
    fit_linear_degradation,
    fuel_corrected_lap_time,
)


def test_fuel_correction_adds_time_proportional_to_lap_number() -> None:
    corrected = fuel_corrected_lap_time(90.0, lap_number=10, fuel_effect_s_per_lap=0.05)
    assert corrected == pytest.approx(90.5)
    assert fuel_corrected_lap_time(90.0, lap_number=0) == pytest.approx(90.0)


def test_fit_recovers_a_known_synthetic_slope() -> None:
    rng = np.random.default_rng(seed=42)
    ages = np.arange(0, 25, dtype=float)
    true_k0, true_k1 = 90.0, 0.07
    noise = rng.normal(0, 0.02, size=ages.shape)
    times = true_k0 + true_k1 * ages + noise

    k1 = fit_linear_degradation(ages, times)

    assert k1 == pytest.approx(true_k1, abs=0.01)


def test_fit_recovers_approximately_zero_slope_for_flat_laps() -> None:
    ages = np.arange(0, 20, dtype=float)
    times = np.full_like(ages, 90.0)

    k1 = fit_linear_degradation(ages, times)

    assert k1 == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize(("k1", "expected"), [(-0.5, 0.0), (0.3, 0.22), (0.1, 0.1)])
def test_clamp_keeps_degradation_rate_physically_plausible(k1: float, expected: float) -> None:
    assert clamp_degradation_rate(k1) == pytest.approx(expected)
    assert MIN_PLAUSIBLE_K1_S_PER_LAP <= clamp_degradation_rate(k1) <= MAX_PLAUSIBLE_K1_S_PER_LAP


def test_naive_uncorrected_fit_on_real_monza_data_is_confounded(fixtures_dir: Path) -> None:
    """Regression/documentation test: without the fuel correction, this
    real stint's slope comes out negative — the exact failure mode
    docs/f1-strategy-research.md §3.6/§12#1 warns about. This test exists
    to make sure that fact stays visible, not to endorse the naive fit."""
    laps = json.loads(
        (fixtures_dir / "openf1" / "monza_2025_driver1_stint1_laps.json").read_text()
    )
    ages = np.array([lap["lap_number"] - 1 for lap in laps], dtype=float)
    raw_times = np.array([lap["lap_duration"] for lap in laps], dtype=float)

    naive_k1 = fit_linear_degradation(ages, raw_times)

    assert naive_k1 < 0


def test_fuel_corrected_fit_on_real_monza_data_is_physically_plausible(fixtures_dir: Path) -> None:
    laps = json.loads(
        (fixtures_dir / "openf1" / "monza_2025_driver1_stint1_laps.json").read_text()
    )
    lap_numbers = np.array([lap["lap_number"] for lap in laps], dtype=float)
    ages = lap_numbers - 1.0
    raw_times = np.array([lap["lap_duration"] for lap in laps], dtype=float)
    assert len(raw_times) == len(lap_numbers)
    corrected = np.array(
        [fuel_corrected_lap_time(t, int(n)) for t, n in zip(raw_times, lap_numbers)]
    )

    k1 = fit_linear_degradation(ages, corrected)

    # Real result during T2: +0.028 s/lap. A wide but meaningful band: must
    # be positive (degradation, not "tyres get faster forever") and within
    # the physically plausible range research.md §3.6 clamps to.
    assert 0.0 < k1 < MAX_PLAUSIBLE_K1_S_PER_LAP
    assert k1 == pytest.approx(0.028, abs=0.01)
