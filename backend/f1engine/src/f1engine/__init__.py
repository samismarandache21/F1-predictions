"""Lap-time/finish-time predictors (M2, docs/plan/phase-2.md T4). Monte
Carlo position-odds simulation is M4 ("Simulate") — see
docs/plan/phase-1.md.

`LapTimePredictor`/`DeterministicRacePredictor` are imported lazily (PEP
562) because `predictors.py` constructs real f1core.Value objects and so
pulls in f1core, which needs Python >= 3.11 to import on this dev machine
(see f1models/__init__.py's docstring for the same pattern). Keeping them
out of this module's top-level import lets `prediction_math` — pure, no
f1core — stay importable and testable ahead of the project's real 3.12
toolchain being installed.
"""

from f1engine.prediction_math import predict_finish_time_s, predict_lap_time_s

__all__ = [
    "DeterministicRacePredictor",
    "LapTimePredictor",
    "predict_finish_time_s",
    "predict_lap_time_s",
]


def __getattr__(name: str):
    if name in ("LapTimePredictor", "DeterministicRacePredictor"):
        from f1engine import predictors

        return getattr(predictors, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
