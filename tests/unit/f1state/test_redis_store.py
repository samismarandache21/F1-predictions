"""Skipped locally when Redis isn't reachable (before `docker compose up`);
runs for real once it is. `redis` is imported lazily inside the fixture so
collection doesn't fail if the package isn't installed in a given dev
environment — matching tests/unit/f1ingest/test_db_upsert.py's pattern.
"""

from __future__ import annotations

import os

import pytest

from f1state.state import CarState, RaceState

TEST_SESSION_KEY = 999999002


@pytest.fixture
def redis_client():  # type: ignore[no-untyped-def]
    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.skip("REDIS_URL not set (run `docker compose up` to enable)")
    try:
        import redis
    except ImportError:
        pytest.skip("redis package not installed")

    client = redis.Redis.from_url(url)
    try:
        client.ping()
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure as a skip
        pytest.skip(f"redis not reachable: {exc}")

    yield client
    client.delete(f"race_state:{TEST_SESSION_KEY}")


def test_save_then_load_round_trips_the_state(redis_client) -> None:  # type: ignore[no-untyped-def]
    from f1state.redis_store import RedisStateStore

    store = RedisStateStore(redis_client)
    state = RaceState(session_key=TEST_SESSION_KEY, lap=12, track_status="YELLOW")
    state = state.with_car(
        CarState(driver=1, position=1, compound="HARD", compounds_used=("MEDIUM", "HARD"))
    )

    store.save(state)
    loaded = store.load(TEST_SESSION_KEY)

    assert loaded == state
    assert isinstance(loaded.cars[1].compounds_used, tuple)  # not a list after the JSON round trip


def test_load_returns_none_for_an_unknown_session(redis_client) -> None:  # type: ignore[no-untyped-def]
    from f1state.redis_store import RedisStateStore

    store = RedisStateStore(redis_client)

    assert store.load(123456789) is None
