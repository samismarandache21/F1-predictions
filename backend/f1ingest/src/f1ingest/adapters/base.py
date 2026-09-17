"""Shared types for the T4 ingestion adapters (OpenF1 historical, Jolpica,
FastF1 fallback). These fetch-and-normalise external data into row dicts
ready for upsert; they are distinct from the `SourceAdapter` streaming
interface in docs/f1-strategy-design.md §4.1 (`OpenF1LiveAdapter`/
`ReplayAdapter`), which T5 builds on top of the DB these adapters populate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuarantinedRow:
    table_name: str
    raw_payload: Any
    reason: str


@dataclass
class AdapterResult:
    """Rows ready for upsert, keyed by target table name, plus anything that
    failed validation along the way (CLAUDE.md rule 7: never crash the
    pipeline on a bad row; log it and quarantine it).
    """

    rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    quarantined: list[QuarantinedRow] = field(default_factory=list)

    def add(self, table_name: str, row: dict[str, Any]) -> None:
        self.rows.setdefault(table_name, []).append(row)

    def quarantine(self, table_name: str, raw_payload: Any, reason: str) -> None:
        self.quarantined.append(QuarantinedRow(table_name, raw_payload, reason))

    def merge(self, other: AdapterResult) -> None:
        for table_name, rows in other.rows.items():
            self.rows.setdefault(table_name, []).extend(rows)
        self.quarantined.extend(other.quarantined)
