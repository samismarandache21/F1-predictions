from datetime import datetime, timezone
from pathlib import Path

from f1core.registry import VariableRegistry
from f1core.snapshot import Snapshot
from f1core.values import Kind, Value


def _val(var_id: str, scope_id: str, kind: Kind, data: object, ts: str) -> Value:
    return Value(
        var_id=var_id,
        scope_id=scope_id,
        kind=kind,
        data=data,
        source="test",
        state_version="s1",
        ts=datetime.fromisoformat(ts).replace(tzinfo=timezone.utc),
    )


def test_with_updates_never_mutates_the_original_snapshot(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    snap0 = Snapshot(state_version="s0", registry=registry)

    snap1 = snap0.with_updates(
        [_val("race.lap", "", Kind.OBSERVED, 1, "2026-01-01T00:00:00")], "s1"
    )

    assert snap0.get("race.lap") is None
    assert snap0.state_version == "s0"
    assert snap1.get("race.lap") is not None
    assert snap1.get("race.lap").data == 1
    assert snap1.state_version == "s1"


def test_higher_precedence_wins_regardless_of_application_order(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    snap = Snapshot(state_version="s0", registry=registry)

    predicted = _val("race.total_laps", "", Kind.PREDICTED, 55, "2026-01-01T00:00:01")
    observed = _val("race.total_laps", "", Kind.OBSERVED, 53, "2026-01-01T00:00:00")

    snap = snap.with_updates([predicted, observed], "s1")

    result = snap.get("race.total_laps")
    assert result is not None
    assert result.data == 53
    assert result.kind == Kind.OBSERVED


def test_explain_surfaces_dependency_values(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    snap = Snapshot(state_version="s0", registry=registry)

    lap_time = _val("car.lap.time_s", "44", Kind.OBSERVED, 91.2, "2026-01-01T00:00:00")
    position = _val("car.lap.position", "44", Kind.OBSERVED, 3, "2026-01-01T00:00:01")
    snap = snap.with_updates([lap_time, position], "s1")

    explanation = snap.explain("car.lap.position", "44")

    assert explanation.value.data == 3
    dep = explanation.depends_on["car.lap.time_s"]
    assert dep is not None
    assert dep.data == 91.2
