"""Property: for any acyclic edge set, DependencyGraph.topological_order()
produces an order consistent with every edge. Edges are generated with
src < dst so the input is acyclic by construction — this is what
docs/plan/phase-1.md T3 calls "topological order" as a property, distinct
from the explicit 2-node cycle-rejection unit test in test_graph.py.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from f1core.graph import DependencyGraph
from f1core.registry import Scope, VariableDef, VariableRegistry
from f1core.values import Kind


def _build_registry(n: int, edges: list[tuple[int, int]]) -> VariableRegistry:
    ids = [f"v{i}" for i in range(n)]
    depends_on: dict[str, list[str]] = {var_id: [] for var_id in ids}
    for src, dst in edges:  # src must be computed before dst
        depends_on[ids[dst]].append(ids[src])

    defs = {
        var_id: VariableDef(
            id=var_id,
            scope=Scope.RACE,
            dtype="float",
            unit="none",
            kinds_allowed=[Kind.OBSERVED],
            depends_on=depends_on[var_id],
            affects=[],
            description="",
        )
        for var_id in ids
    }
    return VariableRegistry(defs)


@st.composite
def _acyclic_graphs(draw: st.DrawFn) -> tuple[int, list[tuple[int, int]]]:
    n = draw(st.integers(min_value=1, max_value=8))
    edge = st.tuples(st.integers(0, n - 1), st.integers(0, n - 1)).filter(
        lambda pair: pair[0] < pair[1]
    )
    edges = draw(st.lists(edge, max_size=n * 2, unique=True))
    return n, edges


@given(_acyclic_graphs())
@settings(max_examples=100)
def test_topological_order_always_respects_acyclic_edges(
    params: tuple[int, list[tuple[int, int]]],
) -> None:
    n, edges = params
    registry = _build_registry(n, edges)
    order = DependencyGraph(registry).topological_order()

    assert set(order) == {f"v{i}" for i in range(n)}
    index = {var_id: i for i, var_id in enumerate(order)}
    for src, dst in edges:
        assert index[f"v{src}"] < index[f"v{dst}"]
