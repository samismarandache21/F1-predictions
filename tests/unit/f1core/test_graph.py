from pathlib import Path

import pytest

from f1core.exceptions import CycleError
from f1core.graph import DependencyGraph
from f1core.registry import VariableRegistry

_CYCLE = (
    "- id: a\n"
    "  scope: race\n  dtype: int\n  unit: none\n  kinds_allowed: [observed]\n"
    "  depends_on: [b]\n  affects: []\n  description: x\n"
    "- id: b\n"
    "  scope: race\n  dtype: int\n  unit: none\n  kinds_allowed: [observed]\n"
    "  depends_on: [a]\n  affects: []\n  description: y\n"
)


def test_topological_order_respects_all_edges(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    graph = DependencyGraph(registry)
    order = graph.topological_order()
    assert set(order) == set(registry.ids())

    index = {var_id: i for i, var_id in enumerate(order)}
    for var in registry:
        for dep in var.depends_on:
            assert index[dep] < index[var.id], f"{dep} must precede {var.id}"
        for aff in var.affects:
            assert index[var.id] < index[aff], f"{var.id} must precede {aff}"


def test_downstream_includes_changed_node_and_its_dependents(config_dir: Path) -> None:
    registry = VariableRegistry.load(config_dir / "variables")
    graph = DependencyGraph(registry)

    dirty = graph.downstream(["car.lap.time_s"])

    assert "car.lap.time_s" in dirty
    assert "car.lap.position" in dirty
    assert "car.lap.gap_to_leader_s" in dirty
    assert "car.lap.interval_s" in dirty
    # Unrelated variables are not marked dirty.
    assert "weather.rainfall" not in dirty

    index = {var_id: i for i, var_id in enumerate(dirty)}
    assert index["car.lap.time_s"] < index["car.lap.position"]


def test_cycle_within_a_lap_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "cycle.yaml").write_text(_CYCLE)
    registry = VariableRegistry.load(tmp_path)
    with pytest.raises(CycleError):
        DependencyGraph(registry).topological_order()
