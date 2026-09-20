# CLAUDE.md — f1-strategy

Live F1 race companion: replay or live timing for all 22 cars, circuit map, tyre/pit/finish predictions, Monte Carlo position odds, strategy. Personal portfolio project, non-commercial.

## Read first
Docs live in `docs/`. If they conflict, this is the order of authority:
1. `docs/f1-strategy-foundation.md`: needs, variable model, repo layout, milestones. **Authoritative.**
2. `docs/f1-strategy-design.md`: architecture, data sources, API, DB.
3. `docs/f1-strategy-engine-spec.md`: simulator details.
4. `docs/f1-driver-circuit-intel.md` and `docs/f1-driver-ratings.md`: metrics and ratings.
5. `docs/plan/phase-1.md`: M1 "Watch" — complete (T1–T10).
6. `docs/plan/phase-2.md`: M2 "Predict pace" — complete (T1–T9).
7. **M3 (pit-stop prediction, `docs/f1-strategy-foundation.md` §9) has no plan doc yet.** Write
   `docs/plan/phase-3.md` (mirroring phase-1/phase-2's structure) before starting any M3 work — see
   rule 12.

Known stale points in the older docs (always follow the foundation doc):
- Grid size is **22, from config**, never hard-coded 20.
- 2026 has **no DRS**. Use `overtake_mode_available`.

## Stack
- Backend: Python 3.12, `uv` workspace, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, psycopg 3, redis-py, FastF1, httpx, NumPy (Numba later). Lint/format: `ruff`. Types: `mypy --strict` on `f1core`. Tests: `pytest`, `hypothesis`.
- Storage: PostgreSQL 16 + TimescaleDB, Redis 7 (Streams).
- Frontend: Angular (latest stable), standalone components, signals, Canvas 2D for the track map. Types are generated from the FastAPI OpenAPI schema (`openapi-typescript`).
- Everything runs with `docker compose up`.

## Commands
```
make up            # docker compose up -d
make test          # backend + frontend tests
make lint          # ruff + mypy + eslint
make ingest SEASON=2026 ROUND=14
make replay SESSION=<key> SPEED=10
make types         # regenerate TS types from OpenAPI
```
Keep the Makefile in sync when adding commands.

## Rules
1. **Config over code.** Season rules, drivers, teams, colours, points and circuits live in `config/`. No magic numbers in logic.
2. **Everything is a variable.** Components declare `inputs`/`outputs` and read and write through the `f1core` registry. No component reads another component's internals.
3. **Value kinds and precedence:** `overridden > observed > estimated > predicted > prior`. Every value carries `kind`, `source`, `model_version` and `state_version`.
4. **Determinism.** Use seeded RNG and the replay clock. Logic never reads wall-clock time.
5. **Units are explicit** in names or types (`_s`, `_m`, `_laps`, `_c`). Store times in UTC.
6. **Adapters are swappable.** Live and replay implement the same `SourceAdapter` interface.
7. **Degrade gracefully.** Missing data falls back to the prior, with wider uncertainty. Never crash the pipeline on a bad row; log it and quarantine it.
8. **Ingestion is idempotent.** Use upserts keyed on natural keys, and cache raw API responses under `data/raw/`.
9. **Be polite to data sources.** Rate-limit and use exponential backoff. OpenF1 and Jolpica are free community services.
10. **Tests with every change.** Unit tests for logic, property tests for the physics and ordering invariants, and replay tests with recorded fixtures (no network in CI).
11. **Small PR-sized steps.** For each task, state the plan, implement it, run `make lint test`, and summarise what changed.
12. **Don't expand scope.** Put ideas in `docs/backlog.md` instead of building them.

## Data and legal
- Sources: OpenF1 (historical free; live is paid and comes later), FastF1, Jolpica, Open-Meteo. Non-commercial use only.
- Never commit API keys (use `.env`, gitignored). Never commit `data/`.

## Domain glossary
- **Stint:** laps on one set of tyres.
- **Pit loss:** time lost to a stop (lane plus stationary time).
- **SC / VSC:** Safety Car / Virtual Safety Car.
- **Clean-air lap:** interval to the car ahead > 2 s, not an in/out lap, green flag.
- **Overtake Mode:** the 2026 extra-power aid when within 1 s at the detection point.
- **Cold-start circuit:** no historical data (Madring 2026, Sepang 2026).
