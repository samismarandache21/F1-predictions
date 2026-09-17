"""Live smoke tests against the real OpenF1/Jolpica APIs. Excluded from CI
(`pytest -m "not network"`) since CLAUDE.md rule 9 asks us to be polite to
free community APIs, not hammer them on every push. Run manually:

    uv run pytest ../tests/unit/f1ingest/test_live_smoke.py -m network -v

These exist to catch schema drift in the two fixture races
(docs/plan/phase-1.md: 2025 Italian GP / Monza, 2026 Spanish GP / Madring)
that the recorded fixtures in tests/fixtures/ can't detect on their own.
"""

from __future__ import annotations

import pytest

from f1ingest.adapters.jolpica import BASE_URL as JOLPICA_BASE_URL
from f1ingest.adapters.jolpica import JolpicaAdapter
from f1ingest.adapters.openf1_hist import BASE_URL as OPENF1_BASE_URL
from f1ingest.adapters.openf1_hist import OpenF1HistoricalAdapter
from f1ingest.cache import RawResponseCache
from f1ingest.http import RateLimitedClient, RateLimiter

pytestmark = pytest.mark.network

MONZA_2025_SESSION_KEY = 9912
MADRING_2026_SESSION_KEY = 11369


@pytest.fixture
def openf1(tmp_path):  # type: ignore[no-untyped-def]
    cache = RawResponseCache(tmp_path)
    with RateLimitedClient(
        "openf1", OPENF1_BASE_URL, cache=cache, rate_limiters=[RateLimiter(3, 1.0)]
    ) as client:
        yield OpenF1HistoricalAdapter(client)


@pytest.fixture
def jolpica(tmp_path):  # type: ignore[no-untyped-def]
    cache = RawResponseCache(tmp_path)
    with RateLimitedClient(
        "jolpica",
        JOLPICA_BASE_URL,
        cache=cache,
        rate_limiters=[RateLimiter(4, 1.0)],
        headers={"User-Agent": "f1-strategy/0.1 (personal, non-commercial)"},
    ) as client:
        yield JolpicaAdapter(client)


def test_monza_2025_session_is_still_at_the_expected_key(openf1) -> None:  # type: ignore[no-untyped-def]
    session = openf1.fetch_session(MONZA_2025_SESSION_KEY)
    assert session["year"] == 2025
    assert session["location"] == "Monza"
    assert session["session_type"] == "Race"


def test_madring_2026_session_is_still_at_the_expected_key(openf1) -> None:  # type: ignore[no-untyped-def]
    session = openf1.fetch_session(MADRING_2026_SESSION_KEY)
    assert session["year"] == 2026
    assert session["session_type"] == "Race"


def test_2026_round_14_is_still_madring_in_jolpica(jolpica) -> None:  # type: ignore[no-untyped-def]
    schedule = jolpica.fetch_schedule(2026)
    round_14 = next(r for r in schedule if r.round == 14)
    assert round_14.circuit_id == "madring"


def test_2026_round_11_to_12_swap_still_matches_config(jolpica) -> None:  # type: ignore[no-untyped-def]
    round_11 = jolpica.fetch_results(2026, 11)
    round_12 = jolpica.fetch_results(2026, 12)

    hadjar_number = 6
    lawson_number = 30
    tsunoda_number = 22

    by_number_11 = {r.driver_number: r for r in round_11}
    by_number_12 = {r.driver_number: r for r in round_12}

    assert by_number_11[hadjar_number].team_id == "red_bull"
    assert by_number_11[lawson_number].team_id == "racing_bulls"
    assert tsunoda_number not in by_number_11

    assert by_number_12[lawson_number].team_id == "red_bull"
    assert by_number_12[tsunoda_number].team_id == "racing_bulls"
    assert hadjar_number not in by_number_12
