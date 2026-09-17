"""The variable registry: loads `config/variables/*.yaml`, validates that every
`depends_on`/`affects` reference points at a defined variable, and gives
components a single place to look up what a variable id means.

See docs/f1-strategy-foundation.md §4.1 and docs/plan/phase-1.md T3.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from f1core.exceptions import DuplicateVariableError, UnknownVariableError
from f1core.values import Kind


class Scope(StrEnum):
    RACE = "race"
    LAP = "lap"
    CAR = "car"
    CAR_LAP = "car_lap"
    CAR_STINT = "car_stint"
    CIRCUIT = "circuit"
    SEASON = "season"


class VariableDef(BaseModel):
    id: str
    scope: Scope
    dtype: str
    unit: str
    kinds_allowed: list[Kind]
    depends_on: list[str] = []
    affects: list[str] = []
    description: str


def _load_yaml_list(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text())
    return raw or []


class VariableRegistry:
    """Immutable once loaded. Unknown variable ids in `depends_on`/`affects`
    fail fast at load time, per CLAUDE.md rule 1 (config over code) and
    docs/f1-strategy-foundation.md §7 ("Variable definitions in YAML are
    validated at startup; unknown IDs fail fast.")
    """

    def __init__(self, definitions: dict[str, VariableDef]) -> None:
        self._definitions = definitions

    @classmethod
    def load(cls, directory: Path) -> VariableRegistry:
        definitions: dict[str, VariableDef] = {}
        for path in sorted(directory.glob("*.yaml")):
            for item in _load_yaml_list(path):
                var = VariableDef.model_validate(item)
                if var.id in definitions:
                    raise DuplicateVariableError(var.id)
                definitions[var.id] = var
        registry = cls(definitions)
        registry._validate_references()
        return registry

    def _validate_references(self) -> None:
        unknown: set[str] = set()
        for var in self._definitions.values():
            for ref in (*var.depends_on, *var.affects):
                if ref not in self._definitions:
                    unknown.add(ref)
        if unknown:
            raise UnknownVariableError(sorted(unknown))

    def __getitem__(self, var_id: str) -> VariableDef:
        return self._definitions[var_id]

    def __contains__(self, var_id: str) -> bool:
        return var_id in self._definitions

    def __iter__(self) -> Iterator[VariableDef]:
        return iter(self._definitions.values())

    def __len__(self) -> int:
        return len(self._definitions)

    def ids(self) -> list[str]:
        return list(self._definitions.keys())

    def allows_kind(self, var_id: str, kind: Kind) -> bool:
        return kind in self._definitions[var_id].kinds_allowed
