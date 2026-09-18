"""Tests for PredictionPipeline.

NOT RUNNABLE in this dev environment: PredictionPipeline constructs real
f1core.Value/Snapshot/Orchestrator and f1models/f1engine Components, which
need Python >= 3.11 here (see f1state/predictions.py's module docstring).
Written and hand-traced against the real code in f1core, f1models, and
f1engine; run this once the project's real 3.12 toolchain is installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from f1state.predictions import PredictionPipeline, _is_clean_air
from f1state.state import CarState

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


@dataclass(frozen=True)
class _FakeLap:
    driver: int
    lap: int
    ts: datetime
    lap_time_s: float | None
    interval_s: float | None
    compound: str | None = "MEDIUM"
    tyre_age_laps: int | None = 1
    track_status: str | None = "GREEN"
    is_pit_out_lap: bool = False
    is_pit_in_lap: bool = False
    type: str = "lap_completed"


def _lap(lap: int, *, lap_time_s: float = 90.0, **kwargs: object) -> _FakeLap:
    return _FakeLap(
        driver=1,
        lap=lap,
        ts=datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc),
        lap_time_s=lap_time_s,
        interval_s=kwargs.pop("interval_s", 5.0),
        **kwargs,
    )


def test_is_clean_air_requires_green_flag_and_a_gap_over_two_seconds() -> None:
    assert _is_clean_air(_lap(5, interval_s=5.0, track_status="GREEN"))
    assert not _is_clean_air(_lap(5, interval_s=1.0, track_status="GREEN"))
    assert not _is_clean_air(_lap(5, interval_s=5.0, track_status="SC"))
    assert not _is_clean_air(_lap(5, interval_s=5.0, is_pit_out_lap=True))
    assert not _is_clean_air(_lap(5, interval_s=5.0, is_pit_in_lap=True))
    assert not _is_clean_air(_lap(5, interval_s=None))


def test_on_lap_completed_returns_no_values_when_lap_time_is_missing() -> None:
    pipeline = PredictionPipeline(_CONFIG_DIR)
    car = CarState(driver=1)

    result = pipeline.on_lap_completed(car, _lap(1, lap_time_s=None))

    assert result == {}


def test_on_lap_completed_falls_back_to_priors_below_the_clean_lap_threshold() -> None:
    pipeline = PredictionPipeline(_CONFIG_DIR)
    car = CarState(driver=1)

    result = pipeline.on_lap_completed(car, _lap(1))

    assert result["car.tyre.deg_rate"].kind.value == "prior"
    assert result["car.tyre.deg_cliff_lap"].kind.value == "prior"
    # No car.lap.time_pred/finish_time_pred yet: PaceEstimator has produced
    # a value (kind=prior), but LapTimePredictor/DeterministicRacePredictor
    # depend on car.pace.base_s too — the orchestrator ran them in the same
    # pass, using that prior pace, so a (wide-uncertainty) prediction does
    # exist even this early.
    assert "car.lap.time_pred" in result


def test_on_lap_completed_accumulates_history_and_estimates_after_enough_clean_laps() -> None:
    pipeline = PredictionPipeline(_CONFIG_DIR)
    car = CarState(driver=1, stint_number=1)

    result = {}
    for lap in range(1, 8):
        result = pipeline.on_lap_completed(
            car, _lap(lap, lap_time_s=90.0 + 0.05 * lap), total_laps=53
        )

    assert result["car.tyre.deg_rate"].kind.value == "estimated"
    assert result["car.pace.base_s"].kind.value == "estimated"
    assert result["car.race.finish_time_pred"].kind.value == "predicted"


def test_on_lap_completed_has_no_finish_time_prediction_without_total_laps() -> None:
    """race.total_laps only ever comes from the caller (RaceState) — until
    it's passed, DeterministicRacePredictor must degrade gracefully rather
    than guess a race distance (CLAUDE.md rule 7)."""
    pipeline = PredictionPipeline(_CONFIG_DIR)
    car = CarState(driver=1, stint_number=1)

    result = pipeline.on_lap_completed(car, _lap(1))

    assert "car.race.finish_time_pred" not in result


def test_on_lap_completed_uses_the_stint_number_from_car_state() -> None:
    """car.lap.observation's stint_number comes from CarState (the event
    itself doesn't carry one) — a pit stop bumping CarState.stint_number
    must show up in the next observation's payload."""
    pipeline = PredictionPipeline(_CONFIG_DIR)

    pipeline.on_lap_completed(CarState(driver=1, stint_number=1), _lap(1))
    pipeline.on_lap_completed(CarState(driver=1, stint_number=2), _lap(20, tyre_age_laps=0))

    history = pipeline._snapshot.history_for_driver("car.lap.observation", "1")
    stint_numbers = [v.data["stint_number"] for v in history]
    assert stint_numbers == [1, 2]
