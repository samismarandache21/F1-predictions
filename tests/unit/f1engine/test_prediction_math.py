from __future__ import annotations

import json
from pathlib import Path

import pytest

from f1engine.prediction_math import predict_finish_time_s, predict_lap_time_s


def test_predict_lap_time_with_no_fuel_or_tyre_effect_equals_pace() -> None:
    predicted = predict_lap_time_s(
        pace_base_s=90.0,
        deg_rate_s_per_lap=0.0,
        tyre_age_laps=10,
        lap_number=20,
        fuel_effect_s_per_lap=0.0,
    )
    assert predicted == pytest.approx(90.0)


def test_predict_lap_time_adds_tyre_wear_and_removes_fuel_benefit() -> None:
    predicted = predict_lap_time_s(
        pace_base_s=90.0, deg_rate_s_per_lap=0.05, tyre_age_laps=10, lap_number=20
    )
    # +0.05*10 (wear) - 0.05*20 (fuel burned off by lap 20)
    assert predicted == pytest.approx(90.0 + 0.5 - 1.0)


def test_predict_finish_time_sums_synthetic_pace_and_deg_exactly() -> None:
    # 3 laps already run at 90s flat, 2 laps remain, zero fuel/tyre effect:
    # the "expected finish time exactly" done-when from docs/plan/phase-2.md T4.
    elapsed = 270.0
    finish = predict_finish_time_s(
        elapsed_time_s=elapsed,
        current_lap=3,
        current_tyre_age_laps=2,
        total_laps=5,
        pace_base_s=90.0,
        deg_rate_s_per_lap=0.0,
        fuel_effect_s_per_lap=0.0,
    )
    assert finish == pytest.approx(270.0 + 90.0 + 90.0)


def test_predict_finish_time_with_degradation_matches_hand_computed_sum() -> None:
    finish = predict_finish_time_s(
        elapsed_time_s=0.0,
        current_lap=0,
        current_tyre_age_laps=0,
        total_laps=3,
        pace_base_s=90.0,
        deg_rate_s_per_lap=0.1,
        fuel_effect_s_per_lap=0.05,
    )
    lap1 = 90.0 + 0.1 * 1 - 0.05 * 1
    lap2 = 90.0 + 0.1 * 2 - 0.05 * 2
    lap3 = 90.0 + 0.1 * 3 - 0.05 * 3
    assert finish == pytest.approx(lap1 + lap2 + lap3)


def test_predict_finish_time_with_no_remaining_laps_is_just_elapsed_time() -> None:
    finish = predict_finish_time_s(
        elapsed_time_s=4500.0,
        current_lap=53,
        current_tyre_age_laps=20,
        total_laps=53,
        pace_base_s=90.0,
        deg_rate_s_per_lap=0.05,
    )
    assert finish == pytest.approx(4500.0)


def test_predict_finish_time_on_real_monza_data_is_the_right_order_of_magnitude(
    fixtures_dir: Path,
) -> None:
    """docs/plan/phase-2.md T4's done-when: running against the real Monza
    fixture should land in the same ballpark as the real classification
    (the 2025 Italian GP), not require exact ground truth."""
    fixture_path = fixtures_dir / "openf1" / "monza_2025_driver1_stint1_laps.json"
    laps = json.loads(fixture_path.read_text())
    elapsed = sum(lap["lap_duration"] for lap in laps)
    current_lap = laps[-1]["lap_number"]
    current_age = current_lap - 1

    finish = predict_finish_time_s(
        elapsed_time_s=elapsed,
        current_lap=current_lap,
        current_tyre_age_laps=current_age,
        total_laps=53,  # real Monza 2025 race distance
        pace_base_s=90.0,  # ballpark 2025 Monza race pace
        deg_rate_s_per_lap=0.028,  # the real fuel-corrected fit from this same fixture
    )

    # A ~53-lap Monza race finishes in roughly 75-95 minutes; the fixture's
    # own 37 laps already sum to ~model_math's elapsed, so this is mostly
    # checking the remaining-16-laps extrapolation doesn't blow up.
    assert 4500.0 < finish < 6000.0
