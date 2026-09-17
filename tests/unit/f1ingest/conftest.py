from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def load_fixture(fixtures_dir: Path):
    def _load(relative_path: str) -> Any:
        return json.loads((fixtures_dir / relative_path).read_text())

    return _load


class FakeClient:
    """A `RateLimitedClient` stand-in that serves recorded fixture JSON
    instead of hitting the network. Endpoint -> payload is set up once per
    test; every `get_json` call ignores its params and returns the payload
    registered for that endpoint (fixtures were recorded for one specific
    session/driver already, so params are redundant here).
    """

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((endpoint, params or {}))
        if endpoint not in self._responses:
            raise AssertionError(f"FakeClient has no fixture registered for {endpoint!r}")
        return self._responses[endpoint]


@pytest.fixture
def fake_client_cls() -> type[FakeClient]:
    """Fixture wrapper around `FakeClient` so test modules never need to
    import this conftest module directly (unreliable under
    --import-mode=importlib without `tests/` being a real package)."""
    return FakeClient
