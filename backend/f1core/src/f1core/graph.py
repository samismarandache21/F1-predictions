"""Dependency graph over the variable registry: topological order and
dirty-flag propagation. See docs/f1-strategy-foundation.md §4.4 and §4.6.

Real racing has feedback loops (position -> traffic -> lap time -> position),
but those are loop edges from lap n to lap n+1 (the dashed lines in
docs/f1_variable_dependency_graph.png). Within a single lap the graph must be
acyclic; `topological_order` raises CycleError if it isn't, which is exactly
the "cycle detection (rejected within a lap)" requirement in
docs/plan/phase-1.md T3.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from f1core.exceptions import CycleError
from f1core.registry import VariableRegistry


class DependencyGraph:
    def __init__(self, registry: VariableRegistry) -> None:
        self._registry = registry
        edges: dict[str, set[str]] = {var_id: set() for var_id in registry.ids()}
        for var in registry:
            for dep in var.depends_on:
                edges[dep].add(var.id)
            for aff in var.affects:
                edges[var.id].add(aff)
        self._edges = edges

    def topological_order(self) -> list[str]:
        in_degree = dict.fromkeys(self._edges, 0)
        for dsts in self._edges.values():
            for d in dsts:
                in_degree[d] += 1

        queue: deque[str] = deque(sorted(v for v, deg in in_degree.items() if deg == 0))
        order: list[str] = []
        remaining = dict(in_degree)
        while queue:
            node = queue.popleft()
            order.append(node)
            for nxt in sorted(self._edges[node]):
                remaining[nxt] -= 1
                if remaining[nxt] == 0:
                    queue.append(nxt)

        if len(order) != len(self._edges):
            unresolved = sorted(set(self._edges) - set(order))
            raise CycleError(unresolved)
        return order

    def downstream(self, changed: Iterable[str]) -> list[str]:
        """All variable ids reachable from `changed` via dependency edges
        (inclusive of `changed` itself), in topological order. This is the
        dirty-flag set an orchestrator recomputes after an event.
        """
        order = self.topological_order()
        dirty: set[str] = set()
        stack = list(changed)
        while stack:
            node = stack.pop()
            if node in dirty:
                continue
            dirty.add(node)
            stack.extend(self._edges.get(node, ()))
        return [var_id for var_id in order if var_id in dirty]
