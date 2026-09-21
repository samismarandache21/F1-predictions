"""CLI backing the Makefile's `make ingest` / `make replay` targets
(docs/plan/phase-1.md T4/T5)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import click
import redis

from f1ingest.adapters.jolpica import BASE_URL as JOLPICA_BASE_URL
from f1ingest.adapters.jolpica import JolpicaAdapter
from f1ingest.adapters.openf1_hist import BASE_URL as OPENF1_BASE_URL
from f1ingest.adapters.openf1_hist import OpenF1HistoricalAdapter
from f1ingest.adapters.replay import DbRowSource, ReplayAdapter
from f1ingest.cache import RawResponseCache
from f1ingest.clock import MAX_SPEED, MIN_SPEED
from f1ingest.db.engine import get_engine
from f1ingest.geometry_build import build_and_store_geometry
from f1ingest.http import RateLimitedClient, RateLimiter
from f1ingest.pipeline import ingest_session
from f1ingest.publisher import RedisStreamPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# backend/f1ingest/src/f1ingest/cli.py -> repo root is 4 parents up. Overridable
# via F1_DATA_DIR so this doesn't depend on the caller's cwd.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _default_cache_root() -> Path:
    return Path(os.environ.get("F1_DATA_DIR", str(_REPO_ROOT / "data"))) / "raw"


def _openf1_client(cache: RawResponseCache) -> RateLimitedClient:
    return RateLimitedClient(
        "openf1",
        OPENF1_BASE_URL,
        cache=cache,
        # OpenF1 free tier: 3 req/s and 30 req/min (docs/f1-strategy-research.md §11).
        rate_limiters=[RateLimiter(3, 1.0), RateLimiter(30, 60.0)],
    )


def _jolpica_client(cache: RawResponseCache) -> RateLimitedClient:
    return RateLimitedClient(
        "jolpica",
        JOLPICA_BASE_URL,
        cache=cache,
        rate_limiters=[RateLimiter(4, 1.0)],
        headers={
            "User-Agent": os.environ.get(
                "JOLPICA_USER_AGENT", "f1-strategy/0.1 (personal, non-commercial)"
            )
        },
    )


@click.group()
def cli() -> None:
    """f1ingest: historical ingestion (T4) and replay (T5)."""


@cli.command()
@click.option("--season", required=True, type=int)
@click.option("--round", "round_no", required=True, type=int)
def ingest(season: int, round_no: int) -> None:
    """Ingest one session: `make ingest SEASON=2026 ROUND=14`."""
    cache = RawResponseCache(_default_cache_root())
    engine = get_engine()
    with _openf1_client(cache) as openf1_http, _jolpica_client(cache) as jolpica_http:
        openf1 = OpenF1HistoricalAdapter(openf1_http)
        jolpica = JolpicaAdapter(jolpica_http)
        summary = ingest_session(engine, openf1, jolpica, season=season, round_no=round_no)
    logger.info(
        "ingested season=%s round=%s session_key=%s circuit=%s rows=%s quarantined=%s",
        summary.season,
        summary.round,
        summary.session_key,
        summary.circuit_id,
        summary.rows_ingested,
        summary.rows_quarantined,
    )
    # Ingestion itself succeeded; a geometry failure must not undo that
    # (CLAUDE.md rule 7). `make build-geometry` can retry it on its own.
    try:
        geometry = build_and_store_geometry(engine, summary.session_key)
    except Exception:
        logger.exception("circuit geometry build failed for session %s", summary.session_key)
    else:
        logger.info(
            "built geometry circuit=%s length_m=%.0f", geometry.circuit_id, geometry.length_m
        )


@cli.command("build-geometry")
@click.option("--session", "session_key", required=True, type=int)
def build_geometry_cmd(session_key: int) -> None:
    """Build and store a circuit's geometry from an ingested session."""
    geometry = build_and_store_geometry(get_engine(), session_key)
    logger.info("built geometry circuit=%s length_m=%.0f", geometry.circuit_id, geometry.length_m)


@cli.command("ingest-season")
@click.option("--season", required=True, type=int)
def ingest_season_cmd(season: int) -> None:
    """Ingest every round of a season, continuing past individual failures."""
    cache = RawResponseCache(_default_cache_root())
    engine = get_engine()
    with _openf1_client(cache) as openf1_http, _jolpica_client(cache) as jolpica_http:
        openf1 = OpenF1HistoricalAdapter(openf1_http)
        jolpica = JolpicaAdapter(jolpica_http)
        schedule = jolpica.fetch_schedule(season)
        for round_info in schedule:
            try:
                summary = ingest_session(
                    engine, openf1, jolpica, season=season, round_no=round_info.round
                )
            except Exception:
                logger.exception(
                    "round %s failed; continuing with the rest of the season", round_info.round
                )
                continue
            logger.info(
                "round %s: %s rows, %s quarantined",
                round_info.round,
                sum(summary.rows_ingested.values()),
                summary.rows_quarantined,
            )


@cli.command()
@click.option("--session", "session_key", required=True, type=int)
@click.option("--speed", default=1.0, type=float)
def replay(session_key: int, speed: float) -> None:
    """Replay a stored session at the given speed, publishing to Redis Streams."""
    if not (MIN_SPEED <= speed <= MAX_SPEED):
        raise click.BadParameter(f"--speed must be within [{MIN_SPEED}, {MAX_SPEED}]")

    engine = get_engine()
    redis_client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    publisher = RedisStreamPublisher(redis_client, stream_prefix=f"replay:{session_key}")
    adapter = ReplayAdapter(DbRowSource(engine), publisher, speed=speed)

    logger.info("replaying session_key=%s at %sx", session_key, speed)
    count = sum(1 for _ in adapter.stream(session_key))
    logger.info("replay finished: %s events published", count)


if __name__ == "__main__":
    cli()
