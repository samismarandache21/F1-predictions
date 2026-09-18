from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from f1core.graph import DependencyGraph
from f1core.orchestrator import Orchestrator
from f1core.registry import VariableRegistry
from f1core.snapshot import Snapshot
from f1core.values import Kind, Value

# a -> b -> {c, d}: b has one dependency and two dependents, so it's the
# clearest possible case for both "must run before its dependents" and
# "a component producing several outputs together only runs once".
_DIAMOND_VARS = (
    "- id: a\n  scope: race\n  dtype: float\n  unit: none\n  kinds_allowed: [observed]\n"
    "  depends_on: []\n  affects: [b]\n  description: x\n"
    "- id: b\n  scope: race\n  dtype: float\n  unit: none\n  kinds_allowed: [estimated]\n"
    "  depends_on: [a]\n  affects: [c, d]\n  description: y\n"
    "- id: c\n  scope: race\n  dtype: float\n  unit: none\n  kinds_allowed: [estimated]\n"
    "  depends_on: [b]\n  affects: []\n  description: z\n"
    "- id: d\n  scope: race\n  dtype: float\n  unit: none\n  kinds_allowed: [estimated]\n"
    "  depends_on: [b]\n  affects: []\n  description: w\n"
    "- id: unrelated\n  scope: race\n  dtype: float\n  unit: none\n  kinds_allowed: [estimated]\n"
    "  depends_on: []\n  affects: []\n  description: v\n"
)

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _RecordingComponent:
    """Produces a fixed value for each of `outputs` and records every call,
    so tests can assert both what ran and how many times."""

    def __init__(self, name: str, outputs: list[str], value: float = 1.0) -> None:
        self.name = name
        self.inputs: list[str] = []
        self.outputs = outputs
        self.value = value
        self.calls: list[str] = []  # scope_ids this was called with

    def compute(self, ctx: Snapshot, scope_id: str) -> dict[str, Value]:
        self.calls.append(scope_id)
        return {
            output: Value(
                var_id=output,
                scope_id=scope_id,
                kind=Kind.ESTIMATED,
                data=self.value,
                source="test",
                state_version="s1",
                ts=_TS,
            )
            for output in self.outputs
        }


def _registry(tmp_path: Path) -> VariableRegistry:
    (tmp_path / "vars.yaml").write_text(_DIAMOND_VARS)
    return VariableRegistry.load(tmp_path)


def test_components_run_in_topological_order(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    graph = DependencyGraph(registry)
    order_seen: list[str] = []

    class _OrderTracking(_RecordingComponent):
        def compute(self, ctx: Snapshot, scope_id: str) -> dict[str, Value]:
            order_seen.append(self.name)
            return super().compute(ctx, scope_id)

    comp_b = _OrderTracking("comp_b", ["b"])
    comp_c = _OrderTracking("comp_c", ["c"])
    comp_d = _OrderTracking("comp_d", ["d"])
    orchestrator = Orchestrator(graph, [comp_b, comp_c, comp_d])
    snapshot = Snapshot(state_version="s0", registry=registry)

    orchestrator.recompute(snapshot, ["a"], scope_id="44", state_version="s1")

    assert order_seen.index("comp_b") < order_seen.index("comp_c")
    assert order_seen.index("comp_b") < order_seen.index("comp_d")


def test_unrelated_components_are_not_run(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    graph = DependencyGraph(registry)
    comp_b = _RecordingComponent("comp_b", ["b"])
    comp_unrelated = _RecordingComponent("comp_unrelated", ["unrelated"])
    orchestrator = Orchestrator(graph, [comp_b, comp_unrelated])
    snapshot = Snapshot(state_version="s0", registry=registry)

    orchestrator.recompute(snapshot, ["a"], scope_id="44", state_version="s1")

    assert comp_b.calls == ["44"]
    assert comp_unrelated.calls == []


def test_component_with_multiple_outputs_runs_once(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    graph = DependencyGraph(registry)
    # One component jointly produces both c and d (like a degradation
    # estimator fitting rate and cliff-lap together).
    comp_b = _RecordingComponent("comp_b", ["b"])
    comp_cd = _RecordingComponent("comp_cd", ["c", "d"])
    orchestrator = Orchestrator(graph, [comp_b, comp_cd])
    snapshot = Snapshot(state_version="s0", registry=registry)

    orchestrator.recompute(snapshot, ["a"], scope_id="44", state_version="s1")

    assert comp_cd.calls == ["44"]  # not called twice, once per output


def test_recompute_updates_the_snapshot(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    graph = DependencyGraph(registry)
    comp_b = _RecordingComponent("comp_b", ["b"], value=42.0)
    orchestrator = Orchestrator(graph, [comp_b])
    snapshot = Snapshot(state_version="s0", registry=registry)

    new_snapshot = orchestrator.recompute(snapshot, ["a"], scope_id="44", state_version="s1")

    assert snapshot.get("b", "44") is None  # original snapshot untouched
    result = new_snapshot.get("b", "44")
    assert result is not None
    assert result.data == 42.0
    assert result.kind == Kind.ESTIMATED


def test_empty_component_list_is_a_noop(tmp_path: Path) -> None:
    """Matches M1's config/pipelines/default.yaml (components: []): with no
    components registered, recompute must not error and must not
    manufacture any values."""
    registry = _registry(tmp_path)
    graph = DependencyGraph(registry)
    orchestrator = Orchestrator(graph, [])
    snapshot = Snapshot(state_version="s0", registry=registry)

    result = orchestrator.recompute(snapshot, ["a"], scope_id="44", state_version="s1")

    assert result.get("b", "44") is None
    assert result.get("c", "44") is None
    assert result.get("d", "44") is None
