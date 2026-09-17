"""FastF1 fallback adapter: used only when OpenF1 is missing lap data for a
session (docs/plan/phase-1.md T4: "FastF1 (fallback laps)"). The pipeline
calls this only for laps OpenF1 didn't supply, not as the primary source.

Column names are FastF1's stable, documented `Session.laps` DataFrame
columns (https://docs.fastf1.dev). Unlike the OpenF1 and Jolpica adapters,
this one has NOT been exercised against live data in this environment —
FastF1 needs its own multi-hundred-MB per-session cache, which wasn't
practical to pull here. Treat it as best-effort and verify column names
against the installed FastF1 version the first time it actually runs.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

import fastf1
import pandas as pd

SOURCE = "fastf1"


def _seconds(value: Any) -> float | None:
    """Convert a pandas Timedelta (or NaT) to seconds."""
    if pd.isna(value):
        return None
    return float(value.total_seconds())


def _int_or_none(value: Any) -> int | None:
    return None if pd.isna(value) else int(value)


class FastF1FallbackAdapter:
    def __init__(self, cache_dir: str) -> None:
        fastf1.Cache.enable_cache(cache_dir)

    def fetch_laps(self, season: int, round_no: int) -> list[dict[str, Any]]:
        session = fastf1.get_session(season, round_no, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)

        rows: list[dict[str, Any]] = []
        for _, lap in session.laps.iterrows():
            driver_number = _int_or_none(lap.get("DriverNumber"))
            lap_number = _int_or_none(lap.get("LapNumber"))
            lap_start = lap.get("LapStartDate")
            if driver_number is None or lap_number is None or pd.isna(lap_start):
                continue
            ts = lap_start.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            rows.append(
                {
                    "driver_number": driver_number,
                    "lap_number": lap_number,
                    "ts": ts,
                    "lap_time_s": _seconds(lap.get("LapTime")),
                    "sector_1_s": _seconds(lap.get("Sector1Time")),
                    "sector_2_s": _seconds(lap.get("Sector2Time")),
                    "sector_3_s": _seconds(lap.get("Sector3Time")),
                    "position": _int_or_none(lap.get("Position")),
                    "gap_to_leader_s": None,  # not present in FastF1's laps table
                    "interval_s": None,
                    "compound": lap.get("Compound"),
                    "tyre_age_laps": _int_or_none(lap.get("TyreLife")),
                    "track_status": lap.get("TrackStatus"),
                    "is_pit_out_lap": bool(pd.notna(lap.get("PitOutTime"))),
                    "is_pit_in_lap": bool(pd.notna(lap.get("PitInTime"))),
                    "source": SOURCE,
                }
            )
        return rows
