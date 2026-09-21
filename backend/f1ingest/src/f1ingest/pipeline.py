"""Orchestrates one session's ingestion: resolve the session across OpenF1 and
Jolpica, fetch and normalise rows, enrich laps with stint/track-status data,
merge in classified results, and upsert everything idempotently. See
docs/plan/phase-1.md T4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Connection, Engine, Table
from sqlalchemy.dialects.postgresql import insert as pg_insert

from f1ingest.adapters.base import AdapterResult
from f1ingest.adapters.jolpica import JolpicaAdapter, build_result_rows
from f1ingest.adapters.openf1_hist import OpenF1HistoricalAdapter
from f1ingest.db.schema import ingest_log, metadata
from f1ingest.quarantine import write_quarantined_rows
from f1ingest.resample import AsOfSeries

logger = logging.getLogger(__name__)

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "sessions": ("session_key",),
    "driver_sessions": ("session_key", "driver_number"),
    "laps": ("session_key", "driver_number", "lap_number", "ts"),
    "stints": ("session_key", "driver_number", "stint_number"),
    "pit_stops": ("session_key", "driver_number", "lap_number"),
    "race_control": ("session_key", "ts", "category", "message"),
    "weather": ("session_key", "ts"),
    "location": ("session_key", "driver_number", "ts"),
    "results": ("session_key", "driver_number"),
}

_FLAG_TO_STATUS = {
    "GREEN": "GREEN",
    "CLEAR": "GREEN",
    "YELLOW": "YELLOW",
    "DOUBLE YELLOW": "YELLOW",
    "RED": "RED",
    "CHEQUERED": "GREEN",
}


@dataclass
class IngestSummary:
    session_key: int
    season: int
    round: int | None
    circuit_id: str | None
    rows_ingested: dict[str, int] = field(default_factory=dict)
    rows_quarantined: int = 0


def _find_session_for_round(
    openf1: OpenF1HistoricalAdapter, season: int, race_date: date
) -> dict[str, Any] | None:
    """OpenF1's /sessions has no championship round number, so a round is
    matched to its OpenF1 session by calendar date within the season.
    """
    sessions = openf1.client.get_json("/sessions", {"year": season, "session_type": "Race"})
    for s in sessions:
        session_date = datetime.fromisoformat(s["date_start"].replace("Z", "+00:00")).date()
        if session_date == race_date:
            return s
    return None


def _track_status_timeline(race_control_rows: list[dict[str, Any]]) -> AsOfSeries[str]:
    """Best-effort GREEN/YELLOW/RED/SC/VSC timeline from race_control flag and
    SafetyCar messages. Only exercised end-to-end once the third fixture race
    (a wet/SC-affected session, see docs/backlog.md) is ingested — flag this
    for re-verification against a real SC/VSC period at that point.
    """
    samples: list[tuple[datetime, str]] = []
    for rc in sorted(race_control_rows, key=lambda r: r["ts"]):
        category = (rc.get("category") or "").upper()
        message = (rc.get("message") or "").upper()
        flag = (rc.get("flag") or "").upper()
        if category == "SAFETYCAR" or "SAFETY CAR" in message:
            ending = "ENDING" in message or "IN THIS LAP" in message
            if "VIRTUAL" in message:
                status = "GREEN" if ending else "VSC"
            else:
                status = "GREEN" if ending else "SC"
            samples.append((rc["ts"], status))
        elif flag in _FLAG_TO_STATUS:
            samples.append((rc["ts"], _FLAG_TO_STATUS[flag]))
    return AsOfSeries(samples)


def _enrich_laps(result: AdapterResult) -> None:
    """Fill in `compound`, `tyre_age_laps` (from stints) and `track_status`
    (from race_control) that the raw OpenF1 adapter left as None — these are
    cross-table joins, not something a single-endpoint adapter should know
    about (CLAUDE.md rule 2: no component reads another component's
    internals; this is the pipeline's own join, not the adapter reaching
    into another adapter).
    """
    stints_by_driver: dict[int, list[dict[str, Any]]] = {}
    for stint in result.rows.get("stints", []):
        stints_by_driver.setdefault(stint["driver_number"], []).append(stint)

    status_timeline = _track_status_timeline(result.rows.get("race_control", []))

    for lap in result.rows.get("laps", []):
        driver_stints = stints_by_driver.get(lap["driver_number"], [])
        for stint in driver_stints:
            lap_start, lap_end = stint.get("lap_start"), stint.get("lap_end")
            if lap_start is None or lap_end is None:
                continue
            if lap_start <= lap["lap_number"] <= lap_end:
                lap["compound"] = stint.get("compound")
                if stint.get("tyre_age_at_start") is not None:
                    lap["tyre_age_laps"] = stint["tyre_age_at_start"] + (
                        lap["lap_number"] - lap_start
                    )
                break
        status = status_timeline.at(lap["ts"])
        lap["track_status"] = status or "GREEN"


def _apply_grid_positions(result: AdapterResult, grid_by_driver: dict[int, int | None]) -> None:
    for row in result.rows.get("driver_sessions", []):
        if row["driver_number"] in grid_by_driver:
            row["grid_position"] = grid_by_driver[row["driver_number"]]


_MAX_STATEMENT_PARAMS = 60_000  # headroom under Postgres' hard limit of 65,535


def upsert_rows(conn: Connection, table: Table, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    pk_columns = PRIMARY_KEYS[table.name]
    update_columns = [
        col.name
        for col in table.columns
        if col.name not in pk_columns and col.name != "ingested_at"
    ]
    # Postgres caps a single statement at 65,535 bound parameters. A full
    # race's location table (~150k rows x 7 columns) blows past that in one
    # multi-row INSERT (found on the first live Monza ingest; fixtures were
    # tiny), so insert in chunks. Each chunk is still an idempotent upsert.
    params_per_row = max(len(row) for row in rows)
    chunk_size = max(1, _MAX_STATEMENT_PARAMS // params_per_row)
    for start in range(0, len(rows), chunk_size):
        stmt = pg_insert(table).values(rows[start : start + chunk_size])
        stmt = stmt.on_conflict_do_update(
            index_elements=list(pk_columns),
            set_={name: getattr(stmt.excluded, name) for name in update_columns},
        )
        conn.execute(stmt)


def ingest_session(
    engine: Engine,
    openf1: OpenF1HistoricalAdapter,
    jolpica: JolpicaAdapter,
    *,
    season: int,
    round_no: int,
    location_downsample_s: float | None = 1.0,
) -> IngestSummary:
    started_at = datetime.now(tz=timezone.utc)  # noqa: UP017 (see resample.py comment)

    schedule = jolpica.fetch_schedule(season)
    round_info = next((r for r in schedule if r.round == round_no), None)
    if round_info is None:
        raise ValueError(f"season {season} round {round_no} not found in Jolpica schedule")

    session = _find_session_for_round(openf1, season, round_info.race_date)
    if session is None:
        raise ValueError(
            f"no OpenF1 Race session found for season {season} round {round_no} "
            f"(date {round_info.race_date})"
        )
    session_key = session["session_key"]

    result = openf1.build_rows(
        session_key=session_key,
        circuit_id=round_info.circuit_id,
        season=season,
        round_no=round_no,
        location_downsample_s=location_downsample_s,
    )
    _enrich_laps(result)

    results = jolpica.fetch_results(season, round_no)
    result.rows.setdefault("results", []).extend(build_result_rows(session_key, results))
    _apply_grid_positions(result, {r.driver_number: r.grid_position for r in results})

    table_by_name = {name: metadata.tables[name] for name in result.rows}
    with engine.begin() as conn:
        for table_name, rows in result.rows.items():
            upsert_rows(conn, table_by_name[table_name], rows)
        write_quarantined_rows(
            conn, session_key=session_key, source="openf1", rows=result.quarantined
        )
        conn.execute(
            ingest_log.insert().values(
                session_key=session_key,
                source="pipeline",
                endpoint=f"season={season} round={round_no}",
                status="ok",
                rows_ingested=sum(len(rows) for rows in result.rows.values()),
                rows_quarantined=len(result.quarantined),
                started_at=started_at,
                finished_at=datetime.now(tz=timezone.utc),  # noqa: UP017
            )
        )

    return IngestSummary(
        session_key=session_key,
        season=season,
        round=round_no,
        circuit_id=round_info.circuit_id,
        rows_ingested={name: len(rows) for name, rows in result.rows.items()},
        rows_quarantined=len(result.quarantined),
    )
