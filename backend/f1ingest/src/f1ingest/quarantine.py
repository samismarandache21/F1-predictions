"""Quarantine helper: bad rows are logged and stored, never dropped silently
(CLAUDE.md rule 7 — never crash the pipeline on a bad row; log it and
quarantine it).
"""

from __future__ import annotations

from sqlalchemy import Connection

from f1ingest.adapters.base import QuarantinedRow
from f1ingest.db.schema import ingest_quarantine


def write_quarantined_rows(
    conn: Connection, *, session_key: int | None, source: str, rows: list[QuarantinedRow]
) -> None:
    if not rows:
        return
    conn.execute(
        ingest_quarantine.insert(),
        [
            {
                "session_key": session_key,
                "source": source,
                "table_name": row.table_name,
                "raw_payload": row.raw_payload,
                "reason": row.reason,
            }
            for row in rows
        ],
    )
