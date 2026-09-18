"""f1core: the variable registry, dependency graph, snapshots and config loaders
that everything else in the monorepo is built on.

See docs/f1-strategy-foundation.md §4 for the design this package implements.
"""

from f1core.exceptions import (
    CycleError,
    DuplicateVariableError,
    F1CoreError,
    UnknownValueKindError,
    UnknownVariableError,
)
from f1core.graph import DependencyGraph
from f1core.orchestrator import Component, Orchestrator
from f1core.registry import Scope, VariableDef, VariableRegistry
from f1core.snapshot import Explanation, Snapshot
from f1core.values import Kind, Value, precedence

__all__ = [
    "Component",
    "CycleError",
    "DependencyGraph",
    "DuplicateVariableError",
    "Explanation",
    "F1CoreError",
    "Kind",
    "Orchestrator",
    "Scope",
    "Snapshot",
    "UnknownValueKindError",
    "UnknownVariableError",
    "Value",
    "VariableDef",
    "VariableRegistry",
    "precedence",
]
