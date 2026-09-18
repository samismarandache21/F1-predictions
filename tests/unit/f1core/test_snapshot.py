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


def test_history_for_driver_returns_every_lap_sorted_by_time(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    snap = Snapshot(state_version="s0", registry=registry)

    lap2 = _val("car.lap.observation", "44:2", Kind.OBSERVED, {"lap": 2}, "2026-01-01T00:02:00")
    lap1 = _val("car.lap.observation", "44:1", Kind.OBSERVED, {"lap": 1}, "2026-01-01T00:01:00")
    lap3 = _val("car.lap.observation", "44:3", Kind.OBSERVED, {"lap": 3}, "2026-01-01T00:03:00")
    # A different driver's laps must never leak into "44"'s history, even
    # though scope_id is a plain string prefix match, not a structured key.
    other_driver = _val(
        "car.lap.observation", "144:1", Kind.OBSERVED, {"lap": 1}, "2026-01-01T00:01:30"
    )
    snap = snap.with_updates([lap2, lap1, lap3, other_driver], "s1")

    history = snap.history_for_driver("car.lap.observation", "44")

    assert [value.data["lap"] for value in history] == [1, 2, 3]


def test_history_for_driver_is_empty_for_a_driver_with_no_laps(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    snap = Snapshot(state_version="s0", registry=registry)

    assert snap.history_for_driver("car.lap.observation", "44") == []
