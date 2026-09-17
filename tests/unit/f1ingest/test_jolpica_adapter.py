"""Uses a real recorded fixture (tests/fixtures/jolpica/results_2025_round16.json,
the actual Phase 1 fixture race: 2025 Italian GP at Monza) plus a couple of
synthetic rows to cover statuses the real sample didn't happen to contain
(Monza 2025 had no retirements in this trimmed selection).
"""

from __future__ import annotations

from f1ingest.adapters.jolpica import JolpicaAdapter, build_result_rows, to_team_id


def test_finished_and_lapped_are_both_classified(load_fixture) -> None:  # type: ignore[no-untyped-def]
    """Regression test for the bug caught during T4's validation pass: status
    text alone ("Finished" vs "Lapped") is not the classification rule —
    Ergast's `positionText` being numeric is."""
    payload = load_fixture("jolpica/results_2025_round16.json")
    client = _FakePayloadClient(payload)
    adapter = JolpicaAdapter(client)

    results = adapter.fetch_results(2025, 16)

    by_number = {r.driver_number: r for r in results}
    assert by_number[1].classified_position == 1  # VER, status="Finished"
    assert by_number[1].status == "Finished"
    assert by_number[31].classified_position == 15  # OCO, status="Lapped" but classified
    assert by_number[31].status == "Lapped"


def test_retired_is_not_classified() -> None:
    """Synthetic row: the real trimmed fixture happened to have no
    retirements, so this exercises the R/positionText branch directly."""
    client = _FakePayloadClient(
        {
            "MRData": {
                "RaceTable": {
                    "Races": [
                        {
                            "Results": [
                                {
                                    "number": "99",
                                    "position": "20",
                                    "positionText": "R",
                                    "points": "0",
                                    "grid": "10",
                                    "laps": "12",
                                    "status": "Retired",
                                    "Driver": {"code": "ZZZ"},
                                    "Constructor": {"constructorId": "haas"},
                                }
                            ]
                        }
                    ]
                }
            }
        }
    )
    adapter = JolpicaAdapter(client)

    results = adapter.fetch_results(2025, 16)

    assert len(results) == 1
    assert results[0].classified_position is None
    assert results[0].status == "Retired"


def test_did_not_start_is_excluded_from_starts() -> None:
    client = _FakePayloadClient(
        {
            "MRData": {
                "RaceTable": {
                    "Races": [
                        {
                            "Results": [
                                {
                                    "number": "81",
                                    "position": "21",
                                    "positionText": "W",
                                    "points": "0",
                                    "grid": "0",
                                    "laps": "0",
                                    "status": "Did not start",
                                    "Driver": {"code": "PIA"},
                                    "Constructor": {"constructorId": "mclaren"},
                                }
                            ]
                        }
                    ]
                }
            }
        }
    )
    adapter = JolpicaAdapter(client)

    results = adapter.fetch_results(2025, 16)

    assert results == []


def test_racing_bulls_constructor_id_is_mapped() -> None:
    assert to_team_id("rb") == "racing_bulls"
    assert to_team_id("red_bull") == "red_bull"  # identity for everything else


def test_build_result_rows_attaches_session_key(load_fixture) -> None:  # type: ignore[no-untyped-def]
    payload = load_fixture("jolpica/results_2025_round16.json")
    adapter = JolpicaAdapter(_FakePayloadClient(payload))

    results = adapter.fetch_results(2025, 16)
    rows = build_result_rows(9912, results)

    assert len(rows) == len(results)
    assert all(row["session_key"] == 9912 for row in rows)
    assert all(row["source"] == "jolpica" for row in rows)


class _FakePayloadClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def get_json(self, endpoint: str, params: dict[str, object] | None = None) -> object:
        return self.payload
