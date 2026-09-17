"""Jolpica-F1 adapter: schedule and classified results.

Field shapes verified live against https://api.jolpi.ca/ergast/f1 during T4
(2026-09-17), including cross-checking the real 2026 rounds 1-14 results
against docs/f1-driver-circuit-intel.md §4 (every row matched once the
classification rule below was fixed — see the T4 summary).

The classification rule is Ergast's own convention, not a guess: `position`
is always a final ranking integer (even for retirees), but `positionText` is
the display value — a digit string only when the driver is actually
classified (>= 90% race distance or running at the flag if lapped);
otherwise "R" (retired), "W" (withdrawn/DNS), "D" (disqualified), etc. Naive
`status == "Finished"` checks under- and over-count DNFs (e.g. a car that
retired late but still completed enough distance to be classified shows
status="Retired" yet positionText is numeric).

Jolpica's constructorId does not always match our config/seasons/*.yaml team
ids — only "rb" (Racing Bulls) differs, confirmed against the full 2026
constructor list; `JOLPICA_TEAM_ID_MAP` covers it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from f1ingest.http import RateLimitedClient

SOURCE = "jolpica"
BASE_URL = "https://api.jolpi.ca/ergast/f1"

JOLPICA_TEAM_ID_MAP: dict[str, str] = {"rb": "racing_bulls"}

_DNS_STATUSES = {"Did not start", "Did not qualify"}


def to_team_id(constructor_id: str) -> str:
    return JOLPICA_TEAM_ID_MAP.get(constructor_id, constructor_id)


@dataclass(frozen=True)
class ScheduleRound:
    season: int
    round: int
    circuit_id: str
    race_date: date


@dataclass(frozen=True)
class ResultRow:
    driver_number: int
    team_id: str
    grid_position: int | None
    classified_position: int | None
    status: str
    points: float
    laps_completed: int


class JolpicaAdapter:
    def __init__(self, client: RateLimitedClient) -> None:
        self.client = client

    def fetch_schedule(self, season: int) -> list[ScheduleRound]:
        payload = self.client.get_json(f"/{season}.json", {"limit": 40})
        races = payload["MRData"]["RaceTable"]["Races"]
        return [
            ScheduleRound(
                season=season,
                round=int(race["round"]),
                circuit_id=race["Circuit"]["circuitId"],
                race_date=date.fromisoformat(race["date"]),
            )
            for race in races
        ]

    def fetch_results(self, season: int, round_no: int) -> list[ResultRow]:
        payload = self.client.get_json(f"/{season}/{round_no}/results.json", {"limit": 40})
        races = payload["MRData"]["RaceTable"]["Races"]
        if not races:
            return []
        rows: list[ResultRow] = []
        for res in races[0]["Results"]:
            status = res["status"]
            position_text = res.get("positionText", "")
            if status in _DNS_STATUSES:
                continue  # excluded from "starts" per docs/f1-driver-circuit-intel.md §4
            is_classified = position_text.isdigit()
            rows.append(
                ResultRow(
                    driver_number=int(res["number"]),
                    team_id=to_team_id(res["Constructor"]["constructorId"]),
                    grid_position=int(res["grid"]) if res.get("grid") else None,
                    classified_position=int(position_text) if is_classified else None,
                    status=status,
                    points=float(res["points"]),
                    laps_completed=int(res["laps"]),
                )
            )
        return rows

    def find_round_by_date(self, season: int, race_date: date) -> ScheduleRound | None:
        for round_info in self.fetch_schedule(season):
            if round_info.race_date == race_date:
                return round_info
        return None


def build_result_rows(session_key: int, results: list[ResultRow]) -> list[dict[str, Any]]:
    return [
        {
            "session_key": session_key,
            "driver_number": row.driver_number,
            "classified_position": row.classified_position,
            "status": row.status,
            "points": row.points,
            "laps_completed": row.laps_completed,
            "source": SOURCE,
        }
        for row in results
    ]
