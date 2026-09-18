"""Immutable snapshots of resolved variable values, and the Explain API.

See docs/f1-strategy-foundation.md §4.6 ("Every recompute produces an
immutable, versioned snapshot") and §4.6.5 (the Explain API).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from f1core.registry import VariableRegistry
from f1core.values import Value


@dataclass(frozen=True)
class Explanation:
    var_id: str
    scope_id: str
    value: Value
    depends_on: Mapping[str, Value | None]


@dataclass(frozen=True)
class Snapshot:
    """`current` holds only the winning Value per (var_id, scope_id) key —
    the precedence/recency resolution in `Value.beats` has already happened
    by the time a value is stored here. A Snapshot is never mutated in
    place; `with_updates` returns a new one.
    """

    state_version: str
    registry: VariableRegistry
    current: Mapping[tuple[str, str], Value] = field(default_factory=dict)

    def get(self, var_id: str, scope_id: str = "") -> Value | None:
        return self.current.get((var_id, scope_id))

    def history_for_driver(self, var_id: str, driver: str) -> list[Value]:
        """All values for `var_id` whose scope_id is `"{driver}:{lap}"`,
        sorted by timestamp. Most car_lap-scoped variables only ever need
        the *latest* value per driver (scope_id is just the driver number),
        which the plain (var_id, scope_id) key already gives via `get`. A
        handful of variables — car.lap.observation, so far — instead need
        the *whole stint's history* per driver (a degradation fit needs
        every lap, not just the last one), and use this `driver:lap`
        scope_id convention specifically so history doesn't get lost to
        `with_updates`' per-key precedence resolution. See
        docs/plan/phase-2.md T2.
        """
        prefix = f"{driver}:"
        matches = [
            value
            for (candidate_var_id, scope_id), value in self.current.items()
            if candidate_var_id == var_id and scope_id.startswith(prefix)
        ]
        return sorted(matches, key=lambda value: value.ts)

    def with_updates(self, new_values: Iterable[Value], state_version: str) -> Snapshot:
        merged = dict(self.current)
        for val in new_values:
            existing = merged.get(val.key)
            if existing is None or val.beats(existing):
                merged[val.key] = val
        return Snapshot(state_version=state_version, registry=self.registry, current=merged)

    def explain(self, var_id: str, scope_id: str = "") -> Explanation:
        value = self.get(var_id, scope_id)
        if value is None:
            raise KeyError(f"no value for {var_id!r} at scope_id {scope_id!r}")
        var_def = self.registry[var_id]
        depends_on = {dep: self.get(dep, scope_id) for dep in var_def.depends_on}
        return Explanation(var_id=var_id, scope_id=scope_id, value=value, depends_on=depends_on)
