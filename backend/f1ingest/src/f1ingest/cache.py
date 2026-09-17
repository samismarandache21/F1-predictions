"""Raw API response cache under `data/raw/` (CLAUDE.md rule 8: "cache raw API
responses under data/raw/"). Keyed by source + endpoint + a hash of the query
parameters, so re-running an ingestion never re-fetches the same request and
stays polite to free community APIs (CLAUDE.md rule 9).

This is a plain filesystem cache, not a DB table: `data/` is gitignored and
treated as disposable local state, not part of the durable store.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class RawResponseCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, source: str, endpoint: str, params: dict[str, Any]) -> Path:
        key = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        safe_endpoint = endpoint.strip("/").replace("/", "_") or "root"
        return self.root / source / f"{safe_endpoint}__{digest}.json"

    def get(self, source: str, endpoint: str, params: dict[str, Any]) -> Any | None:
        path = self._path(source, endpoint, params)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def put(self, source: str, endpoint: str, params: dict[str, Any], payload: Any) -> None:
        path = self._path(source, endpoint, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
