# F1 Strategy

A live F1 race companion: replay or live timing for all 22 cars, a circuit map, tyre/pit/finish
predictions, Monte Carlo position odds and strategy recommendations. Personal portfolio project,
non-commercial.

**Current milestone: [M1 — Watch](docs/plan/phase-1.md) is code-complete** (T1–T10) — replay any
ingested race with all 22 cars moving on the circuit map, a timing tower, pit panel and event
banner. No predictions yet; see `docs/f1-strategy-foundation.md` §9 for the full milestone list
(M2–M6) and `docs/backlog.md` for what was deliberately deferred.

Read `CLAUDE.md` first for the documentation hierarchy, engineering rules and current scope.

## Status and how to read this repo

Every piece of M1 is written, and as much of it as this development environment could execute was
actually run — not just read for correctness:

| Layer | Verified how |
|---|---|
| `f1core` (registry, snapshot, config) | Written and reasoned through carefully; blocked from running here — Pydantic needs Python ≥3.10 to resolve its field types, and this machine only had 3.9 during development. |
| `f1ingest` (adapters, pipeline, replay) | **Executed against real, live OpenF1/Jolpica data** during development (see T4/T5/T7 below) and against recorded fixtures in CI. 41+ tests pass locally. |
| `f1track` (circuit geometry) | **Executed against real Monza 2025 telemetry.** Median projection error on a held-out lap: 0.092 m (target was <5 m). |
| `f1state` (race state) | Executed via fake, duck-typed events (avoids the `f1core` Python-version blocker). Property-tested with `hypothesis`. |
| `f1api` (REST + WebSocket) | **Executed for real**, including a live WebSocket test that receives a real position frame — the exact check T8 asks for. |
| `web` (Angular frontend) | Written and statically checked (import/export resolution, brace balance) by hand-rolled scripts; **never executed** — this environment has no Node/npm. Treat it as unverified until you run `npm install && ng test`. |

Three real bugs were caught and fixed by actually running things rather than just reading code:
OpenF1's location telemetry turned out to be in decimetres, not metres (a 10x unit bug); the API's
DB-backed routes were silently ignoring an injected test database; and a `@for` loop variable
shadowed a same-named component signal in the session picker. None of these would have been caught
by review alone. Full details are in the commit history.

**No screenshot or GIF of the replay yet** (T10 asks for one): this development environment never
had a working `uv`/Node/Docker toolchain, so the app has never actually run end-to-end. Once you
have it running locally (see Setup below), please add one here — `make replay SESSION=<key>
SPEED=10` against the Monza or Madring fixture is the quickest way to get something worth
capturing.

## Stack

- **Backend:** Python 3.12, `uv` workspace, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic,
  psycopg 3, redis-py, FastF1, httpx, NumPy, SciPy.
- **Storage:** PostgreSQL 16 + TimescaleDB, Redis 7 (Streams).
- **Frontend:** Angular (standalone components + signals), Canvas 2D for the track map.
- Everything runs with `docker compose up`.

## Setup

1. **Toolchain** (macOS, via Homebrew):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install uv node
   brew install --cask docker   # then open Docker Desktop once and grant it permissions
   ```
2. **Env file:**
   ```bash
   cp .env.example .env
   ```
3. **Backend workspace:**
   ```bash
   cd backend && uv sync --all-packages --dev
   ```
4. **Frontend deps:**
   ```bash
   cd web && npm install
   ```
5. **Start the stack:**
   ```bash
   make up
   ```
   `GET http://localhost:8000/health` should return `{"status": "ok"}`, and
   `http://localhost:4200` should load the session picker.
6. **Apply migrations, then ingest a fixture race:**
   ```bash
   make migrate
   make ingest SEASON=2025 ROUND=16   # 2025 Italian GP (Monza) — the primary fixture
   make ingest SEASON=2026 ROUND=14   # 2026 Spanish GP (Madring) — cold-start circuit
   ```
7. **Watch it:** open `http://localhost:4200`, pick the ingested session, choose a speed, press
   Play. `make replay SESSION=<key> SPEED=10` does the same thing from the CLI, without the UI.

## Common commands

```bash
make up            # docker compose up -d
make test          # backend + frontend tests
make lint          # ruff + mypy + eslint
make migrate       # apply Alembic migrations
make ingest SEASON=2026 ROUND=14
make replay SESSION=<key> SPEED=10
make types         # regenerate TS types from the OpenAPI schema (needs Node)
```

## Repository layout

```
config/             # season/circuit/variable definitions — config over code (CLAUDE.md rule 1)
backend/            # uv workspace
  f1core/           # variable registry, value precedence, snapshots, config loaders
  f1ingest/         # OpenF1/Jolpica/FastF1 adapters, DB schema, replay adapter + clock
  f1state/          # race state builder (domain events -> RaceState)
  f1track/          # circuit geometry builder + projection (pure numpy/scipy)
  f1api/            # FastAPI: sessions, circuits, live replay control, WebSocket stream
  f1models/ f1engine/ f1calib/   # placeholders for M2+ (tyre/pace models, Monte Carlo, calibration)
web/                # Angular frontend: session picker, track map, timing tower, pit panel, event banner
tests/              # unit/ property/ replay/ fixtures/ — shared across all backend packages
docs/               # foundation, design, engine spec, driver/circuit intel, the phase-1 plan, backlog
data/               # local cache, gitignored — never commit raw session data
```

## Data sources and licensing

OpenF1 (historical is free; live is a paid, non-commercial-only subscription), FastF1, Jolpica and
Open-Meteo. Non-commercial use only — see `docs/f1-strategy-research.md` §11 for details. Never
commit API keys; they belong in `.env`, which is gitignored.
