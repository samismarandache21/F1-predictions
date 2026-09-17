"""SQLAlchemy Core schema for the raw ingested data store.

Scope: only the tables Phase 1 (M1 "Watch") needs per docs/plan/phase-1.md T4 —
sessions, driver entries, laps, stints, pit stops, race control, weather, car
locations, results, plus the ingest log and a quarantine table for bad rows
(CLAUDE.md rule 7). Tables that belong to later milestones (`overtake`,
`model_artifact`, `strategy_report` from docs/f1-strategy-design.md §9) are
deliberately not created here — see docs/backlog.md.

`laps`, `weather` and `location` become TimescaleDB hypertables in the initial
migration, partitioned on `ts`. TimescaleDB requires the partitioning column
to be part of any unique constraint on a hypertable, so their primary keys
include `ts`. This is safe for idempotent upserts (CLAUDE.md rule 8) because
`ts` here is always sourced from the provider's own immutable timestamp for
that record (OpenF1's `date`/`date_start`), verified live against
https://api.openf1.org during T4 — re-ingesting the same historical session
reproduces the same key, so the upsert is a no-op.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("session_key", BigInteger, primary_key=True),
    Column("meeting_key", BigInteger, nullable=False),
    Column("season", Integer, nullable=False),
    # Nullable: OpenF1's /sessions endpoint has no championship round number.
    # The pipeline fills this in from Jolpica's schedule by matching on date.
    Column("round", Integer, nullable=True),
    # References config/circuits/<id>.yaml — not a DB foreign key, since
    # circuit metadata is config (CLAUDE.md rule 1), not ingested data.
    Column("circuit_id", Text, nullable=True),
    Column("session_type", Text, nullable=False),
    Column("session_name", Text, nullable=False),
    Column("date_start", DateTime(timezone=True), nullable=False),
    Column("date_end", DateTime(timezone=True), nullable=True),
    Column("total_laps", Integer, nullable=True),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

driver_sessions = Table(
    "driver_sessions",
    metadata,
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("driver_number", Integer, nullable=False),
    Column("broadcast_name", Text, nullable=True),
    Column("full_name", Text, nullable=True),
    Column("name_acronym", Text, nullable=True),
    Column("team_name", Text, nullable=True),
    Column("team_colour", Text, nullable=True),
    Column("grid_position", Integer, nullable=True),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("session_key", "driver_number"),
)

laps = Table(
    "laps",
    metadata,
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("driver_number", Integer, nullable=False),
    Column("lap_number", Integer, nullable=False),
    # Lap START time (OpenF1 `date_start`), not completion — always present,
    # unlike `lap_duration` which can be null for incomplete laps. Hypertable
    # partition column.
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("lap_time_s", Float, nullable=True),
    Column("sector_1_s", Float, nullable=True),
    Column("sector_2_s", Float, nullable=True),
    Column("sector_3_s", Float, nullable=True),
    Column("position", Integer, nullable=True),  # as-of resampled from `position`
    Column("gap_to_leader_s", Float, nullable=True),  # as-of resampled from `intervals`
    Column("interval_s", Float, nullable=True),  # as-of resampled from `intervals`
    Column("compound", Text, nullable=True),
    Column("tyre_age_laps", Integer, nullable=True),
    Column("track_status", Text, nullable=True),
    Column("is_pit_out_lap", Boolean, nullable=False, server_default="false"),
    # OpenF1 has no `is_pit_in_lap` field; derived by the pipeline from a join
    # against `pit_stops` on lap_number (see f1ingest.pipeline).
    Column("is_pit_in_lap", Boolean, nullable=False, server_default="false"),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("session_key", "driver_number", "lap_number", "ts"),
)

stints = Table(
    "stints",
    metadata,
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("driver_number", Integer, nullable=False),
    Column("stint_number", Integer, nullable=False),
    Column("compound", Text, nullable=True),
    Column("tyre_age_at_start", Integer, nullable=True),
    Column("lap_start", Integer, nullable=True),
    Column("lap_end", Integer, nullable=True),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("session_key", "driver_number", "stint_number"),
)

pit_stops = Table(
    "pit_stops",
    metadata,
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("driver_number", Integer, nullable=False),
    Column("lap_number", Integer, nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("lane_time_s", Float, nullable=True),
    # Rarely available per docs/f1-strategy-research.md §4.1; null unless the
    # source actually reports stationary (wheels-off-to-wheels-on) time.
    Column("stationary_time_s", Float, nullable=True),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("session_key", "driver_number", "lap_number"),
)

race_control = Table(
    "race_control",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("lap_number", Integer, nullable=True),
    Column("category", Text, nullable=True),
    Column("flag", Text, nullable=True),
    Column("scope", Text, nullable=True),
    Column("driver_number", Integer, nullable=True),
    Column("message", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint(
        "session_key", "ts", "category", "message", name="uq_race_control_natural_key"
    ),
)

weather = Table(
    "weather",
    metadata,
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("track_temp_c", Float, nullable=True),
    Column("air_temp_c", Float, nullable=True),
    Column("humidity_pct", Float, nullable=True),
    Column("rainfall", Boolean, nullable=True),
    Column("wind_speed_ms", Float, nullable=True),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("session_key", "ts"),
)

location = Table(
    "location",
    metadata,
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("driver_number", Integer, nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("x_m", Float, nullable=False),
    Column("y_m", Float, nullable=False),
    Column("z_m", Float, nullable=True),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("session_key", "driver_number", "ts"),
)

results = Table(
    "results",
    metadata,
    Column("session_key", BigInteger, ForeignKey("sessions.session_key"), nullable=False),
    Column("driver_number", Integer, nullable=False),
    # Null when not classified (DNF/DSQ/etc.) — see f1ingest.adapters.jolpica
    # for the classification rule (Ergast `positionText` numeric vs R/W/D).
    Column("classified_position", Integer, nullable=True),
    Column("status", Text, nullable=True),
    Column("points", Float, nullable=True),
    Column("laps_completed", Integer, nullable=True),
    Column("source", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("session_key", "driver_number"),
)

ingest_log = Table(
    "ingest_log",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("session_key", BigInteger, nullable=True),
    Column("source", Text, nullable=False),
    Column("endpoint", Text, nullable=False),
    Column("status", Text, nullable=False),  # ok | error
    Column("rows_ingested", Integer, nullable=False, server_default="0"),
    Column("rows_quarantined", Integer, nullable=False, server_default="0"),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("error_message", Text, nullable=True),
)

ingest_quarantine = Table(
    "ingest_quarantine",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("session_key", BigInteger, nullable=True),
    Column("source", Text, nullable=False),
    Column("table_name", Text, nullable=False),
    Column("raw_payload", JSONB, nullable=False),
    Column("reason", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

# Converted to TimescaleDB hypertables (partitioned on `ts`) in the initial
# Alembic migration.
HYPERTABLES = ("laps", "weather", "location")
