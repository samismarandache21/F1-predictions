"""Exceptions for f1core. All fail fast and carry the offending IDs, per
CLAUDE.md rule 7 (degrade gracefully in the pipeline, but config/registry
errors must not pass silently)."""

from __future__ import annotations


class F1CoreError(Exception):
    """Base class for all f1core errors."""


class DuplicateVariableError(F1CoreError):
    def __init__(self, var_id: str) -> None:
        self.var_id = var_id
        super().__init__(f"variable {var_id!r} is defined more than once")


class UnknownVariableError(F1CoreError):
    def __init__(self, unknown_ids: list[str]) -> None:
        self.unknown_ids = unknown_ids
        super().__init__(
            f"depends_on/affects reference undefined variable ids: {unknown_ids}"
        )


class UnknownValueKindError(F1CoreError):
    def __init__(self, var_id: str, kind: str, allowed: list[str]) -> None:
        self.var_id = var_id
        self.kind = kind
        self.allowed = allowed
        super().__init__(
            f"variable {var_id!r} does not allow kind {kind!r} (allowed: {allowed})"
        )


class CycleError(F1CoreError):
    def __init__(self, remaining: list[str]) -> None:
        self.remaining = remaining
        super().__init__(
            f"dependency cycle detected within a single lap among: {remaining}"
        )
