"""Component-level tests for LapTimePredictor and DeterministicRacePredictor.

NOT RUNNABLE in this dev environment: constructing real f1core.Snapshot/
Value objects requires importing f1core, which needs Python >= 3.11 here
(see f1engine/__init__.py and predictors.py's module docstrings). Written
and hand-traced against f1core.snapshot/values/registry's actual code, in
the same style as tests/unit/f1models/test_tyre.py; run this once the
project's real 3.12 toolchain is installed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from f1core.registry import VariableRegistry
from f1core.snapshot import Snapshot
from f1core.values import Kind, Value
from f1engine.prediction_math import predict_finish_time_s, predict_lap_time_s
from f1engine.predictors import DeterministicRacePredictor, LapTimePredictor

_VARS_YAML = (
    "- id: car.lap.observation\n  scope: car_lap\n  dtype: object\n  unit: none\n"
    "  kinds_allowed: [observed]\n  depends_on: []\n  affects: []\n  description: x\n"
    "- id: car.tyre.deg_rate\n  scope: car_stint\n  dtype: float\n  unit: s_per_lap\n"
    "  kinds_allowed: [prior, estimated]\n  depends_on: []\n  affects: []\n  description: y\n"
    "- id: car.pace.base_s\n  scope: car\n  dtype: float\n  unit: _s\n"
    "  kinds_allowed: [prior, estimated]\n  depends_on: []\n  affects: []\n  description: z\n"
    "- id: race.total_laps\n  scope: race\n  dtype: int\n  unit: laps\n"
    "  kinds_allowed: [observed, prior]\n  depends_on: []\n  affects: []\n  description: w\n"
)

_T0 = datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc)


def _registry(tmp_path: Path) -> VariableRegistry:
    (tmp_path / "vars.yaml").write_text(_VARS_YAML)
    return VariableRegistry.load(tmp_path)


def _lap_observation(driver: str, lap: int, *, tyre_age_laps: int, lap_time_s: float) -> Value:
    return Value(
        var_id="car.lap.observation",
        scope_id=f"{driver}:{lap}",
        kind=Kind.OBSERVED,
        data={
            "lap": lap,
            "tyre_age_laps": tyre_age_laps,
            "compound": "medium",
            "lap_time_s": lap_time_s,
            "is_clean_air": True,
            "stint_number": 1,
        },
        source="test",
        state_version="s0",
        ts=_T0 + timedelta(seconds=90 * lap),
    )


def _scalar(var_id: str, scope_id: str, data: object, kind: Kind = Kind.ESTIMATED) -> Value:
    return Value(
        var_id=var_id,
        scope_id=scope_id,
        kind=kind,
        data=data,
        source="test",
        state_version="s0",
        ts=_T0,
    )


def _snapshot(tmp_path: Path, values: list[Value]) -> Snapshot:
    registry = _registry(tmp_path)
    snapshot = Snapshot(state_version="s0", registry=registry)
    return snapshot.with_updates(values, state_version="s1")


def test_lap_time_predictor_returns_nothing_without_history(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, [_scalar("car.pace.base_s", "44", 90.0)])
    assert LapTimePredictor().compute(snapshot, "44") == {}


def test_lap_time_predictor_returns_nothing_without_a_pace_value(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, [_lap_observation("44", 1, tyre_age_laps=0, lap_time_s=90.0)])
    assert LapTimePredictor().compute(snapshot, "44") == {}


def test_lap_time_predictor_matches_the_pure_math_for_the_next_lap(tmp_path: Path) -> None:
    values = [
        _lap_observation("44", 10, tyre_age_laps=9, lap_time_s=91.0),
        _scalar("car.pace.base_s", "44", 90.0),
        _scalar("car.tyre.deg_rate", "44", 0.05),
    ]
    snapshot = _snapshot(tmp_path, values)

    result = LapTimePredictor().compute(snapshot, "44")

    expected = predict_lap_time_s(
        pace_base_s=90.0, deg_rate_s_per_lap=0.05, tyre_age_laps=10, lap_number=11
    )
    assert result["car.lap.time_pred"].kind == Kind.PREDICTED
    assert result["car.lap.time_pred"].data == pytest.approx(expected)


def test_lap_time_predictor_falls_back_to_the_generic_deg_rate_prior(tmp_path: Path) -> None:
    from f1models.tyre import GENERIC_PRIOR_K1_S_PER_LAP

    values = [
        _lap_observation("44", 1, tyre_age_laps=0, lap_time_s=90.0),
        _scalar("car.pace.base_s", "44", 90.0),
    ]
    snapshot = _snapshot(tmp_path, values)
    assert snapshot.get("car.tyre.deg_rate", "44") is None

    result = LapTimePredictor().compute(snapshot, "44")

    expected = predict_lap_time_s(
        pace_base_s=90.0,
        deg_rate_s_per_lap=GENERIC_PRIOR_K1_S_PER_LAP,
        tyre_age_laps=1,  # last observed lap had age 0, so the next lap is age 1
        lap_number=2,
    )
    assert result["car.lap.time_pred"].data == pytest.approx(expected)


def test_finish_time_predictor_returns_nothing_without_total_laps(tmp_path: Path) -> None:
    values = [
        _lap_observation("44", 1, tyre_age_laps=0, lap_time_s=90.0),
        _scalar("car.pace.base_s", "44", 90.0),
    ]
    snapshot = _snapshot(tmp_path, values)
    assert DeterministicRacePredictor().compute(snapshot, "44") == {}


def test_finish_time_predictor_sums_real_elapsed_time_plus_predicted_remaining_laps(
    tmp_path: Path,
) -> None:
    observations = [
        _lap_observation("44", lap, tyre_age_laps=lap - 1, lap_time_s=90.0) for lap in range(1, 4)
    ]
    values = [
        *observations,
        _scalar("car.pace.base_s", "44", 90.0),
        _scalar("car.tyre.deg_rate", "44", 0.05),
        _scalar("race.total_laps", "", 5, kind=Kind.OBSERVED),
    ]
    snapshot = _snapshot(tmp_path, values)

    result = DeterministicRacePredictor().compute(snapshot, "44")

    expected = predict_finish_time_s(
        elapsed_time_s=270.0,
        current_lap=3,
        current_tyre_age_laps=2,
        total_laps=5,
        pace_base_s=90.0,
        deg_rate_s_per_lap=0.05,
    )
    assert result["car.race.finish_time_pred"].kind == Kind.PREDICTED
    assert result["car.race.finish_time_pred"].data == pytest.approx(expected)
