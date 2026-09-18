"""OpenF1 historical adapter: sessions, drivers, laps, stints, pit stops,
position, intervals, race control, weather and location. Historical data is
free and needs no auth (unlike live, which is a paid subscription — M6).

Field shapes verified live against https://api.openf1.org/v1 during T4
(2026-09-17) — for example `laps` rows look like:

    {"session_key": 9157, "driver_number": 1, "lap_number": 10,
     "date_start": "2023-09-03T13:36:20.855000+00:00",
     "duration_sector_1": 28.315, "duration_sector_2": 29.78,
     "duration_sector_3": 28.508, "is_pit_out_lap": false,
     "lap_duration": 86.603, ...}

Notably: `laps` has no `is_pit_in_lap` field (only `is_pit_out_lap`) — the
in-lap is derived here by joining against `pit` on `lap_number`. `position`
and `intervals` are sparse event streams, not one row per lap, so they are
resampled onto each lap's start time via `f1ingest.resample.AsOfSeries`.
`pit.stop_duration` (stationary time) was `null` in every sample fetched,
matching docs/f1-strategy-research.md §4.1 ("only ~2-2.5s ... rarely
published"); `pit.pit_duration` (lane time) is reliably present.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from f1ingest.adapters.base import AdapterResult
from f1ingest.http import RateLimitedClient
from f1ingest.resample import AsOfSeries

SOURCE = "openf1"
BASE_URL = "https://api.openf1.org/v1"


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _downsample_by_time(samples: Iterable[dict[str, Any]], bucket_s: float) -> list[dict[str, Any]]:
    """Keep the first sample per `bucket_s`-second bucket. Phase 1 decision
    (docs/plan/phase-1.md): downsample to 1 Hz for the bulk store; fixtures
    keep raw ~3.7 Hz by passing `location_downsample_s=None`.
    """
    kept: list[dict[str, Any]] = []
    last_bucket: int | None = None
    for sample in sorted(samples, key=lambda s: s["date"]):
        ts = _parse_ts(sample["date"])
        bucket = int(ts.timestamp() // bucket_s)
        if bucket != last_bucket:
            kept.append(sample)
            last_bucket = bucket
    return kept


class OpenF1HistoricalAdapter:
    def __init__(self, client: RateLimitedClient) -> None:
        self.client = client

    def find_session(
        self, *, year: int, session_type: str = "Race", **filters: Any
    ) -> dict[str, Any] | None:
        """e.g. find_session(year=2025, session_type="Race", country_name="Italy")."""
        params = {"year": year, "session_type": session_type, **filters}
        sessions = self.client.get_json("/sessions", params)
        return sessions[0] if sessions else None

    def fetch_session(self, session_key: int) -> dict[str, Any]:
        rows = self.client.get_json("/sessions", {"session_key": session_key})
        if not rows:
            raise ValueError(f"no OpenF1 session found for session_key={session_key}")
        return rows[0]

    def fetch_drivers(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/drivers", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_laps(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/laps", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_stints(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/stints", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_pit(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/pit", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_position(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/position", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_intervals(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/intervals", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_race_control(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/race_control", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_weather(self, session_key: int) -> list[dict[str, Any]]:
        return self.client.get_json("/weather", {"session_key": session_key})  # type: ignore[no-any-return]

    def fetch_location(self, session_key: int, driver_number: int) -> list[dict[str, Any]]:
        """Per-driver: OpenF1's /location is enormous for a whole session at once."""
        return self.client.get_json(  # type: ignore[no-any-return]
            "/location", {"session_key": session_key, "driver_number": driver_number}
        )

    def build_rows(
        self,
        *,
        session_key: int,
        circuit_id: str | None,
        season: int,
        round_no: int | None,
        location_downsample_s: float | None = 1.0,
    ) -> AdapterResult:
        result = AdapterResult()

        session = self.fetch_session(session_key)
        result.add(
            "sessions",
            {
                "session_key": session_key,
                "meeting_key": session["meeting_key"],
                "season": season,
                "round": round_no,
                "circuit_id": circuit_id,
                "session_type": session["session_type"],
                "session_name": session["session_name"],
                "date_start": _parse_ts(session["date_start"]),
                "date_end": _parse_ts(session["date_end"]) if session.get("date_end") else None,
                "total_laps": None,  # OpenF1 doesn't give this; filled in below from lap numbers
                "source": SOURCE,
            },
        )

        drivers = self.fetch_drivers(session_key)
        for d in drivers:
            result.add(
                "driver_sessions",
                {
                    "session_key": session_key,
                    "driver_number": d["driver_number"],
                    "broadcast_name": d.get("broadcast_name"),
                    "full_name": d.get("full_name"),
                    "name_acronym": d.get("name_acronym"),
                    "team_name": d.get("team_name"),
                    "team_colour": d.get("team_colour"),
                    "grid_position": None,  # filled from Jolpica results, not OpenF1
                    "source": SOURCE,
                },
            )

        for s in self.fetch_stints(session_key):
            if s.get("driver_number") is None or s.get("stint_number") is None:
                result.quarantine("stints", s, "missing driver_number or stint_number")
                continue
            result.add(
                "stints",
                {
                    "session_key": session_key,
                    "driver_number": s["driver_number"],
                    "stint_number": s["stint_number"],
                    "compound": s.get("compound"),
                    "tyre_age_at_start": s.get("tyre_age_at_start"),
                    "lap_start": s.get("lap_start"),
                    "lap_end": s.get("lap_end"),
                    "source": SOURCE,
                },
            )

        pit_by_driver_lap: dict[tuple[int, int], dict[str, Any]] = {}
        for p in self.fetch_pit(session_key):
            if p.get("driver_number") is None or p.get("lap_number") is None:
                result.quarantine("pit_stops", p, "missing driver_number or lap_number")
                continue
            key = (p["driver_number"], p["lap_number"])
            pit_by_driver_lap[key] = p
            result.add(
                "pit_stops",
                {
                    "session_key": session_key,
                    "driver_number": p["driver_number"],
                    "lap_number": p["lap_number"],
                    "ts": _parse_ts(p["date"]),
                    "lane_time_s": p.get("pit_duration"),
                    "stationary_time_s": p.get("stop_duration"),
                    "source": SOURCE,
                },
            )

        for rc in self.fetch_race_control(session_key):
            message = rc.get("message")
            if not message:
                result.quarantine("race_control", rc, "missing message")
                continue
            result.add(
                "race_control",
                {
                    "session_key": session_key,
                    "ts": _parse_ts(rc["date"]),
                    "lap_number": rc.get("lap_number"),
                    "category": rc.get("category"),
                    "flag": rc.get("flag"),
                    "scope": rc.get("scope"),
                    "driver_number": rc.get("driver_number"),
                    "message": message,
                    "source": SOURCE,
                },
            )

        for w in self.fetch_weather(session_key):
            rainfall = w.get("rainfall")
            result.add(
                "weather",
                {
                    "session_key": session_key,
                    "ts": _parse_ts(w["date"]),
                    "track_temp_c": w.get("track_temperature"),
                    "air_temp_c": w.get("air_temperature"),
                    "humidity_pct": w.get("humidity"),
                    "rainfall": bool(rainfall) if rainfall is not None else None,
                    "wind_speed_ms": w.get("wind_speed"),
                    "source": SOURCE,
                },
            )

        position_by_driver: dict[int, AsOfSeries[int]] = {}
        samples_by_driver: dict[int, list[tuple[datetime, int]]] = {}
        for p in self.fetch_position(session_key):
            samples_by_driver.setdefault(p["driver_number"], []).append(
                (_parse_ts(p["date"]), p["position"])
            )
        for driver_number, samples in samples_by_driver.items():
            position_by_driver[driver_number] = AsOfSeries(samples)

        interval_by_driver: dict[int, AsOfSeries[tuple[float | None, float | None]]] = {}
        interval_samples_by_driver: dict[
            int, list[tuple[datetime, tuple[float | None, float | None]]]
        ] = {}
        for iv in self.fetch_intervals(session_key):
            interval_samples_by_driver.setdefault(iv["driver_number"], []).append(
                (_parse_ts(iv["date"]), (iv.get("gap_to_leader"), iv.get("interval")))
            )
        for driver_number, samples in interval_samples_by_driver.items():
            interval_by_driver[driver_number] = AsOfSeries(samples)

        max_lap_number = 0
        for lap in self.fetch_laps(session_key):
            driver_number = lap.get("driver_number")
            lap_number = lap.get("lap_number")
            if driver_number is None or lap_number is None or not lap.get("date_start"):
                result.quarantine("laps", lap, "missing driver_number, lap_number or date_start")
                continue
            max_lap_number = max(max_lap_number, lap_number)
            ts = _parse_ts(lap["date_start"])

            position = (
                position_by_driver[driver_number].at(ts)
                if driver_number in position_by_driver
                else None
            )
            gap_to_leader = interval = None
            if driver_number in interval_by_driver:
                sample = interval_by_driver[driver_number].at(ts)
                if sample is not None:
                    gap_to_leader, interval = sample

            result.add(
                "laps",
                {
                    "session_key": session_key,
                    "driver_number": driver_number,
                    "lap_number": lap_number,
                    "ts": ts,
                    "lap_time_s": lap.get("lap_duration"),
                    "sector_1_s": lap.get("duration_sector_1"),
                    "sector_2_s": lap.get("duration_sector_2"),
                    "sector_3_s": lap.get("duration_sector_3"),
                    "position": position,
                    "gap_to_leader_s": gap_to_leader,
                    "interval_s": interval,
                    "compound": None,  # filled by the pipeline from the matching stint
                    "tyre_age_laps": None,  # filled by the pipeline from the matching stint
                    "track_status": None,  # filled by the pipeline from race_control
                    "is_pit_out_lap": bool(lap.get("is_pit_out_lap", False)),
                    "is_pit_in_lap": (driver_number, lap_number) in pit_by_driver_lap,
                    "source": SOURCE,
                },
            )

        # /sessions has no total_laps field; the highest observed lap number is
        # the best available estimate once every lap has been ingested.
        result.rows["sessions"][0]["total_laps"] = max_lap_number or None

        for driver_number in {d["driver_number"] for d in drivers}:
            samples = self.fetch_location(session_key, driver_number)
            if location_downsample_s:
                samples = _downsample_by_time(samples, location_downsample_s)
            for loc in samples:
                if loc.get("x") is None or loc.get("y") is None:
                    result.quarantine("location", loc, "missing x/y")
                    continue
                result.add(
                    "location",
                    {
                        "session_key": session_key,
                        "driver_number": driver_number,
                        "ts": _parse_ts(loc["date"]),
                        # OpenF1's raw x/y/z are in decimetres, not metres: a
                        # full Monza lap's raw path length comes out to
                        # ~5850-5950 raw units, matching Monza's real 5793 m
                        # length only once divided by 10 (checked live
                        # during T7). Convert here so the x_m/y_m/z_m column
                        # names are honest (CLAUDE.md rule 5: units explicit).
                        "x_m": loc["x"] / 10.0,
                        "y_m": loc["y"] / 10.0,
                        "z_m": loc["z"] / 10.0 if loc.get("z") is not None else None,
                        "source": SOURCE,
                    },
                )

        return result
