"""Tyre and pace models (M2, docs/plan/phase-2.md). Pit/overtake/energy/
weather/damage models are M3+ — see docs/f1-strategy-foundation.md §9.

`DegradationPrior`/`TyreDegEstimator`/`PaceEstimator` are imported lazily
(PEP 562) because `tyre.py`/`pace.py` construct real f1core.Value objects
and so pull in f1core, which needs Python >= 3.11 to import on this dev
machine (see f1core.registry's StrEnum usage and tyre.py's module
docstring). Keeping them out of this module's top-level import lets
`degradation_math`/`pace_math` — pure NumPy, no f1core — stay importable
and testable ahead of the project's real 3.12 toolchain being installed.
"""

from f1models.degradation_math import fit_linear_degradation, fuel_corrected_lap_time
from f1models.pace_math import ewma, tyre_corrected_lap_time

__all__ = [
    "DegradationPrior",
    "PaceEstimator",
    "TyreDegEstimator",
    "ewma",
    "fit_linear_degradation",
    "fuel_corrected_lap_time",
    "tyre_corrected_lap_time",
]

_LAZY = {
    "DegradationPrior": "tyre",
    "TyreDegEstimator": "tyre",
    "PaceEstimator": "pace",
}


def __getattr__(name: str):
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(f"f1models.{module_name}")
    return getattr(module, name)
