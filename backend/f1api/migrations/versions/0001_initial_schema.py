"""initial schema: sessions, driver_sessions, laps, stints, pit_stops,
race_control, weather, location, results, ingest_log, ingest_quarantine.

`laps`, `weather` and `location` become TimescaleDB hypertables partitioned
on `ts`, per docs/plan/phase-1.md T4. The table definitions themselves live
in f1ingest.db.schema (single source of truth); this migration just applies
them and runs the TimescaleDB-specific conversion.

Revision ID: 0001
Revises:
Create Date: 2026-09-17

"""

from __future__ import annotations

from alembic import op
from f1ingest.db.schema import HYPERTABLES, metadata

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    bind = op.get_bind()
    metadata.create_all(bind=bind)
    for table_name in HYPERTABLES:
        op.execute(
            f"SELECT create_hypertable('{table_name}', 'ts', "
            f"if_not_exists => TRUE, migrate_data => TRUE)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
