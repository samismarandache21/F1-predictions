"""The orchestrator: runs registered Components over a Snapshot, recomputing
only what a dirty-flag set touches, in topological order. See
docs/f1-strategy-foundation.md §4.5-4.6 and docs/plan/phase-2.md T1.

M1 never needed this: every value was `observed`, so there was nothing to
derive. M2 is the first milestone with estimated/predicted values, so this
is the first real exercise of the registry/graph/snapshot machinery built
in T3 — `config/pipelines/default.yaml` had `components: []` for exactly
this reason.

One deliberate extension beyond foundation.md §4.5's illustrative
`Component.compute(self, ctx: Snapshot) -> dict[VarId, Value]` signature:
that dict return type is ambiguous for a car-scoped variable, which has one
value per car, so `compute` here also takes the `scope_id` (e.g. a driver
number) it should compute for. A component is invoked once per dirty scope,
not once per dirty variable, so a component that produces several outputs
together (e.g. a degradation rate and its cliff lap, fit jointly) only runs
once.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from f1core.graph import DependencyGraph
from f1core.snapshot import Snapshot
from f1core.values import Value


class Component(Protocol):
    name: str
    inputs: list[str]
    outputs: list[str]

    def compute(self, ctx: Snapshot, scope_id: str) -> dict[str, Value]: ...


class Orchestrator:
    def __init__(self, graph: DependencyGraph, components: Iterable[Component]) -> None:
        self._graph = graph
        self._component_by_output: dict[str, Component] = {}
        for component in components:
            for output in component.outputs:
                self._component_by_output[output] = component

    def recompute(
        self,
        snapshot: Snapshot,
        changed_var_ids: list[str],
        scope_id: str,
        state_version: str,
    ) -> Snapshot:
        """Recompute every component downstream of `changed_var_ids`, for
        one scope (e.g. one driver), in topological order. Variables with
        no registered component (most of M1's observed variables) are
        simply skipped — they have nothing to derive.
        """
        order = self._graph.downstream(changed_var_ids)
        already_run: set[str] = set()
        for var_id in order:
            component = self._component_by_output.get(var_id)
            if component is None or component.name in already_run:
                continue
            already_run.add(component.name)
            new_values = component.compute(snapshot, scope_id)
            snapshot = snapshot.with_updates(new_values.values(), state_version)
        return snapshot
