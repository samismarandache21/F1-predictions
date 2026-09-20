"""docs/plan/phase-2.md T8: backtest the M2 prediction pipeline against
real fixture data, walk-forward (no lookahead — each lap's prediction only
ever uses laps seen before it, exactly like the live pipeline would).

This reimplements TyreDegEstimator/PaceEstimator/LapTimePredictor's exact
algorithms in pure form (`_fit_deg_rate`/`_fit_pace` below), rather than
driving the real f1core Components, because f1core needs Python >= 3.11 to
import on this dev machine (see f1models/tyre.py's module docstring) — the
same constraint every other M2 test file hits. If tyre.py/pace.py's
algorithm ever changes, this file's copies need updating to match; there
is currently no way to enforce that mechanically without the real
toolchain (flagged, not solved, per the rest of this session's approach).

Fixture: tests/fixtures/openf1/monza_2025_driver1_stint1_laps.json — the
real 2025 Italian GP (Monza, session_key=9912), driver 1's 37-lap opening
stint (T2). Laps 1 (standing start, 87.5s vs a ~83s baseline) and 37
(confirmed via a live /pit fetch: the real in-lap, pit_duration=24.5s) are
excluded from the "racing" sample used for fitting/prediction — the
fixture has no interval_s, so the strict CLAUDE.md clean-air definition
(interval > 2s) can't be computed here; excluding the two laps we do know
are atypical (race start, pit-in) is a documented substitute, not the real
gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from f1engine.prediction_math import predict_finish_time_s, predict_lap_time_s
from f1models.degradation_math import (
    FUEL_EFFECT_S_PER_LAP,
    GENERIC_PRIOR_K1_S_PER_LAP,
    MAX_PLAUSIBLE_K1_S_PER_LAP,
    MIN_CLEAN_LAPS_FOR_ESTIMATE,
    MIN_PLAUSIBLE_K1_S_PER_LAP,
    clamp_degradation_rate,
    fit_linear_degradation,
    fuel_corrected_lap_time,
)
from f1models.pace_math import DEFAULT_EWMA_ALPHA, ewma, tyre_corrected_lap_time

LapHistory = list[tuple[int, int, float]]  # (tyre_age_laps, lap_number, raw_lap_time_s)


def _fit_deg_rate(history: LapHistory) -> tuple[float, str]:
    """Mirrors TyreDegEstimator.compute()'s branch exactly."""
    if len(history) < MIN_CLEAN_LAPS_FOR_ESTIMATE:
        return GENERIC_PRIOR_K1_S_PER_LAP, "prior"
    ages = np.array([age for age, _, _ in history], dtype=float)
    lap_numbers = np.array([lap for _, lap, _ in history], dtype=float)
    raw_times = np.array([t for _, _, t in history], dtype=float)
    corrected = raw_times + FUEL_EFFECT_S_PER_LAP * lap_numbers
    return clamp_degradation_rate(fit_linear_degradation(ages, corrected)), "estimated"


def _fit_pace(history: LapHistory, deg_rate_s_per_lap: float) -> float:
    """Mirrors PaceEstimator.compute()'s EWMA input exactly."""
    corrected = [
        tyre_corrected_lap_time(fuel_corrected_lap_time(t, lap), age, deg_rate_s_per_lap)
        for age, lap, t in history
    ]
    return ewma(corrected, DEFAULT_EWMA_ALPHA)


def _load_racing_laps(fixtures_dir: Path) -> list[dict]:
    path = fixtures_dir / "openf1" / "monza_2025_driver1_stint1_laps.json"
    laps = json.loads(path.read_text())
    return [lap for lap in laps if 2 <= lap["lap_number"] <= 36]


def _walk_forward(racing_laps: list[dict]) -> list[dict]:
    history: LapHistory = []
    predictions = []
    for entry in racing_laps:
        age = entry["lap_number"] - 1
        lap_number = entry["lap_number"]
        raw_time = entry["lap_duration"]
        if history:
            deg_rate, kind = _fit_deg_rate(history)
            pace = _fit_pace(history, deg_rate)
            predicted = predict_lap_time_s(pace, deg_rate, age, lap_number)
            predictions.append(
                {"lap": lap_number, "kind": kind, "predicted": predicted, "actual": raw_time}
            )
        history.append((age, lap_number, raw_time))
    return predictions


def test_walk_forward_predictions_are_more_accurate_once_estimated(fixtures_dir: Path) -> None:
    """The headline validation: one-lap-ahead prediction error should be
    small once car.tyre.deg_rate has actual data behind it, and clearly
    worse while still on the generic prior — that gap is the whole reason
    the kind/uncertainty system exists.

    Real result (recorded here so a future change that regresses this is
    visible in the diff, not just a passing/failing bool): prior-phase MAE
    ≈ 0.91 s (n=4, laps 3-6), estimated-phase MAE ≈ 0.14 s (n=30, laps
    7-36). The bounds below are loose on purpose — this is one stint from
    one driver at one circuit, not a calibration target.
    """
    predictions = _walk_forward(_load_racing_laps(fixtures_dir))

    prior_errors = [abs(p["predicted"] - p["actual"]) for p in predictions if p["kind"] == "prior"]
    estimated_errors = [
        abs(p["predicted"] - p["actual"]) for p in predictions if p["kind"] == "estimated"
    ]

    assert len(prior_errors) > 0
    assert len(estimated_errors) > 0
    prior_mae = float(np.mean(prior_errors))
    estimated_mae = float(np.mean(estimated_errors))

    assert estimated_mae < 0.5
    assert estimated_mae < prior_mae


def test_walk_forward_deg_rate_stays_within_the_plausible_clamp(fixtures_dir: Path) -> None:
    """Regardless of how noisy an early-stint fit is, the resolved rate
    must never leave research.md §3.6's plausible band — this is exactly
    what clamp_degradation_rate exists to guarantee."""
    racing_laps = _load_racing_laps(fixtures_dir)
    history: LapHistory = []
    for entry in racing_laps:
        if history:
            deg_rate, _kind = _fit_deg_rate(history)
            assert MIN_PLAUSIBLE_K1_S_PER_LAP <= deg_rate <= MAX_PLAUSIBLE_K1_S_PER_LAP
        history.append((entry["lap_number"] - 1, entry["lap_number"], entry["lap_duration"]))


def test_mid_stint_finish_prediction_is_in_the_right_ballpark(fixtures_dir: Path) -> None:
    """docs/plan/phase-2.md T4's original done-when, re-run honestly here:
    using only laps 2-20's data, predict the cumulative time through the
    end of this stint (lap 36 — the last representative racing lap before
    the pit-in on lap 37) and compare to what actually happened.

    Real result: predicted 2898.9 s vs. actual 2994.6 s, a -3.2% error.
    The direction is informative, not just the magnitude: at lap 20 the
    walk-forward fit's degradation rate was still clamped to 0.0 (the
    early-stint signal is too weak relative to noise to detect real wear
    yet — see the module docstring's cross-reference to T2's finding that
    this same fit is unstable/near-zero before ~25 laps), so the
    prediction assumed less wear than the tyre actually showed over the
    remaining 16 laps and came out optimistic. This is the M2 v1 model
    "clearly wrong" in exactly the honest, bounded way the plan asks to
    report — not hidden, and not disqualifying for a first pass.
    """
    laps = json.loads(
        (fixtures_dir / "openf1" / "monza_2025_driver1_stint1_laps.json").read_text()
    )
    cutoff_lap = 20
    stint_end_lap = 36
    history: LapHistory = [
        (lap["lap_number"] - 1, lap["lap_number"], lap["lap_duration"])
        for lap in laps
        if 2 <= lap["lap_number"] <= cutoff_lap
    ]

    deg_rate, _kind = _fit_deg_rate(history)
    pace = _fit_pace(history, deg_rate)
    elapsed_s = sum(t for _, _, t in history)

    predicted = predict_finish_time_s(
        elapsed_time_s=elapsed_s,
        current_lap=cutoff_lap,
        current_tyre_age_laps=cutoff_lap - 1,
        total_laps=stint_end_lap,
        pace_base_s=pace,
        deg_rate_s_per_lap=deg_rate,
    )
    actual = sum(lap["lap_duration"] for lap in laps if 2 <= lap["lap_number"] <= stint_end_lap)

    relative_error = abs(predicted - actual) / actual
    assert relative_error < 0.10  # "same order of magnitude", per T4's original done-when


def test_cold_start_circuit_has_no_calibrated_priors_to_backtest_against() -> None:
    """Madring (2026) is CLAUDE.md's own cold-start example: no session has
    ever run there, so there is no real lap data to backtest at all. What
    *can* be validated is that the config honestly reflects that — every
    degradation-relevant field is null, not a guessed number (CLAUDE.md
    rule 7) — rather than silently claiming a calibration that doesn't
    exist."""
    repo_root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load((repo_root / "config" / "circuits" / "madring.yaml").read_text())

    assert config["deg_class"] == "unknown"
    assert config["pit_lane_loss_s"]["value"] is None
    assert config["pit_lane_loss_s"]["kind"] == "prior"


def test_cold_start_falls_back_to_the_generic_prior_not_a_fit() -> None:
    """The other half of the Madring story: with zero laps of history (its
    actual situation), the exact branch every other lap in this file's
    early-stint predictions also took must resolve to the documented
    generic constant — never an attempted fit on no data, never a
    fabricated per-circuit number."""
    deg_rate, kind = _fit_deg_rate([])

    assert kind == "prior"
    assert deg_rate == GENERIC_PRIOR_K1_S_PER_LAP
