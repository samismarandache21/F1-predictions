"""circuit_geometry table (T7).

The table definition lives in f1ingest.db.schema (single source of truth,
per 0001's approach); `metadata.create_all` is a no-op for tables that
already exist, so this just adds the one new table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18

"""

from __future__ import annotations

from alembic import op
from f1ingest.db.schema import metadata

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.tables["circuit_geometry"].drop(bind=op.get_bind())
