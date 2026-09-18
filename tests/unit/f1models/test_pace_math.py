from __future__ import annotations

import pytest

from f1models.pace_math import ewma, tyre_corrected_lap_time


def test_tyre_corrected_lap_time_removes_estimated_wear() -> None:
    corrected = tyre_corrected_lap_time(90.5, tyre_age_laps=10, deg_rate_s_per_lap=0.05)
    assert corrected == pytest.approx(90.0)


def test_tyre_corrected_lap_time_is_a_noop_at_zero_age() -> None:
    assert tyre_corrected_lap_time(90.5, tyre_age_laps=0, deg_rate_s_per_lap=0.05) == pytest.approx(
        90.5
    )


def test_ewma_of_a_single_value_is_that_value() -> None:
    assert ewma([91.234]) == pytest.approx(91.234)


def test_ewma_of_constant_values_is_that_constant() -> None:
    assert ewma([90.0] * 10, alpha=0.3) == pytest.approx(90.0)


def test_ewma_requires_at_least_one_value() -> None:
    with pytest.raises(ValueError):
        ewma([])


def test_ewma_converges_towards_a_step_change_within_a_bounded_number_of_laps() -> None:
    """Property behind docs/plan/phase-2.md T3's done-when: a driver who
    suddenly goes 2 s/lap faster should have their EWMA visibly move
    towards the new pace lap by lap, without ever jumping there instantly
    and without still being closer to the old pace after many laps."""
    old_pace = 92.0
    new_pace = 90.0
    values = [old_pace] * 5 + [new_pace] * 15
    alpha = 0.3

    running = [ewma(values[: i + 1], alpha) for i in range(len(values))]

    # Still at the old pace before the step.
    assert running[4] == pytest.approx(old_pace)
    # Moves monotonically towards the new pace immediately after the step.
    post_step = running[5:]
    assert all(a >= b - 1e-9 for a, b in zip(post_step, post_step[1:]))
    assert post_step[0] < old_pace
    # Converges close to the new pace well before the end of a normal
    # stint, but not on the very next lap (not instant).
    assert post_step[0] > new_pace + 0.5
    assert post_step[-1] == pytest.approx(new_pace, abs=0.05)
