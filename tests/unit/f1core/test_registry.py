from pathlib import Path

import pytest

from f1core.exceptions import DuplicateVariableError, UnknownVariableError
from f1core.registry import Scope, VariableRegistry

_MINIMAL_VAR = (
    "- id: a\n"
    "  scope: race\n"
    "  dtype: int\n"
    "  unit: none\n"
    "  kinds_allowed: [observed]\n"
    "  depends_on: []\n"
    "  affects: []\n"
    "  description: x\n"
)


def test_loads_all_m1_variables(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    for var_id in [
        "race.lap",
        "race.total_laps",
        "race.track_status",
        "weather.track_temp_c",
        "car.lap.time_s",
        "car.lap.position",
        "car.tyre.compound",
        "car.stint.number",
        "car.pit.lane_time_s",
        "car.location.x_m",
    ]:
        assert var_id in registry, var_id

    assert registry["race.lap"].scope == Scope.RACE
    assert registry["car.tyre.compound"].scope == Scope.CAR_STINT


def test_unknown_reference_fails_fast(tmp_path: Path) -> None:
    bad = _MINIMAL_VAR.replace("depends_on: []", "depends_on: [does.not.exist]")
    (tmp_path / "bad.yaml").write_text(bad)
    with pytest.raises(UnknownVariableError):
        VariableRegistry.load(tmp_path)


def test_duplicate_id_fails(tmp_path: Path) -> None:
    (tmp_path / "one.yaml").write_text(_MINIMAL_VAR)
    (tmp_path / "two.yaml").write_text(_MINIMAL_VAR)
    with pytest.raises(DuplicateVariableError):
        VariableRegistry.load(tmp_path)
