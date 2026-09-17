"""Engine factory. A thin wrapper so adapters/pipeline/CLI don't each import
SQLAlchemy's `create_engine` with their own settings-reading logic.
"""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import Engine, create_engine

_DEFAULT_DATABASE_URL = "postgresql+psycopg://f1strategy:changeme@localhost:5432/f1strategy"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)


@lru_cache
def get_engine() -> Engine:
    return create_engine(database_url(), future=True)
