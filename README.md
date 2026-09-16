# F1 Strategy

A live F1 race companion: replay or live timing for all 22 cars, a circuit map, tyre/pit/finish
predictions, Monte Carlo position odds and strategy recommendations. Personal portfolio project,
non-commercial.

**Current milestone:** [M1 — Watch](docs/plan/phase-1.md) — replay any race with all cars moving
on the circuit map, a timing tower, pit panel and event banner. No predictions yet; see
`docs/f1-strategy-foundation.md` §9 for the full milestone list (M2–M6).

Read `CLAUDE.md` first for the documentation hierarchy, engineering rules and current scope.

## Stack

- **Backend:** Python 3.12, `uv` workspace, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic,
  psycopg 3, redis-py, FastF1, httpx, NumPy.
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
5. **Run everything:**
   ```bash
   make up
   ```
   `GET http://localhost:8000/health` should return `{"status": "ok"}`, and
   `http://localhost:4200` should load the placeholder page.

## Common commands

```bash
make up            # docker compose up -d
make test          # backend + frontend tests
make lint          # ruff + mypy + eslint
make ingest SEASON=2026 ROUND=14
make replay SESSION=<key> SPEED=10
make types         # regenerate TS types from the OpenAPI schema
```

## Repository layout

```
config/            # season/circuit/variable definitions — config over code (CLAUDE.md rule 1)
backend/            # uv workspace: f1core, f1ingest, f1state, f1track, f1models, f1engine, f1calib, f1api
web/                # Angular frontend
tests/              # unit/ property/ replay/ — shared across all backend packages
docs/               # foundation, design, engine spec, driver/circuit intel, the phase-1 plan, backlog
data/               # local cache, gitignored — never commit raw session data
```

## Data sources and licensing

OpenF1 (historical is free; live is a paid, non-commercial-only subscription), FastF1, Jolpica and
Open-Meteo. Non-commercial use only — see `docs/f1-strategy-research.md` §11 for details. Never
commit API keys; they belong in `.env`, which is gitignored.
