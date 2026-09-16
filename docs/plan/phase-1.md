# Phase 1 — M1 "Watch" (implementation plan)

**Demo goal:** open the app, pick any 2025/2026 race, press play. All cars move on the circuit map. The timing tower, pit panel and event banner update live from the replay, at 1× to 50× speed.

No predictions in this phase. The foundations here (config, variable registry, ingestion, state, geometry) carry everything that comes later.

## Decisions (defaults; change here if needed)
| Topic | Decision |
|---|---|
| Python tooling | 3.12, uv workspace, ruff, mypy, pytest |
| DB | Postgres 16 + TimescaleDB; Alembic migrations |
| Bus | Redis 7 Streams |
| API | FastAPI, REST + WebSocket |
| Frontend | Angular latest stable, standalone components + signals, Canvas 2D |
| CI | GitHub Actions: lint + tests on each push, with no network access |
| Data sources | OpenF1 historical (primary for timing/location), FastF1 (fallback + cleaned laps), Jolpica (schedule/results) |
| Fixture races | 2025 Italian GP (well-known baseline); 2026 Spanish GP at Madring (cold start, 2026 rules); one wet or SC race (choose during T4) |
| Location data | Keep raw 3.7 Hz for fixtures; downsample to 1 Hz + track distance `s` for the bulk store |

## Tasks

Each task: implement → tests → `make lint test` → short summary.

### T1 — Repo scaffold
- Monorepo layout as in the foundation doc §7, including `Makefile`, `docker-compose.yml` (db, redis, api, worker, web), `.env.example`, `.gitignore` and the CI workflow.
- **Done when:** `make up` starts all services; `GET /health` returns OK; the Angular placeholder page loads; CI is green.

### T2 — Config
- `config/seasons/2026.yaml` (and `2025.yaml`): teams, drivers (number, code, name, team, colour), points table, rules (`grid_size`, `overtake_aid`, compound rules). Mid-season driver changes are expressed as `entries` per round range (e.g. Lawson at Red Bull from round 12).
- `config/circuits/*.yaml`: id, name, type, country, lat/lon, length, and priors marked `kind: prior`.
- Pydantic loaders with validation.
- **Done when:** a test verifies that the 2026 config yields 22 entries for every round, with the correct substitutes for rounds 12–14.

### T3 — `f1core`: variable registry skeleton
- YAML variable definitions (`config/variables/`), `VarId`, `Value(kind, source, model_version, state_version, ts, uncertainty)`, precedence resolution, `Snapshot` (immutable), dirty-flag graph with topological order, and an `Explain` API.
- Implement only the variables M1 needs: positions, gaps, laps, stints, pit, track status, weather, location.
- **Done when:** unit and property tests pass for precedence, topological order, cycle detection (rejected within a lap), and snapshot immutability.

### T4 — DB schema + ingestion
- Alembic migration for the tables in design doc §9, plus `location` (hypertable) and `ingest_log`.
- Adapters: `OpenF1Historical` (sessions, drivers, laps, stints, pit, position, intervals, race_control, weather, location), `Jolpica` (schedule, results), `FastF1` (fallback laps).
- Raw response cache, rate limiting, retries, idempotent upserts, a quarantine table for bad rows.
- CLI: `make ingest SEASON= ROUND=`, plus a whole-season command.
- **Done when:**
  - The fixture races ingest end-to-end.
  - A re-run changes nothing.
  - The 2026 rounds 1–14 classified results match `docs/f1-driver-circuit-intel.md` §4. Report any mismatches, since that table was transcribed by hand.

### T5 — Replay adapter + event bus
- `ReplayAdapter` reads stored data and emits normalised domain events (design doc §5) on a replay clock (speed 1–50×, pause, seek) to Redis Streams.
- **Done when:** replaying the same session twice gives an identical event sequence (hash test), and seek works.

### T6 — Race state service
- Consumes events and maintains the `RaceState` snapshot in Redis: positions, gaps, intervals, tyre compound and age, stints, pit history, track status, weather, retirements. Emits `lap_completed` and `critical_event`.
- **Done when:** at the end of a replay, the final state matches the stored classification; property tests hold (unique positions, monotonic lap counts).

### T7 — Track geometry (`f1track`)
- Build the circuit polyline from a clean lap's location samples: smoothing, resampling, cumulative `s`, start/finish line, sector marks, pit lane path, and rotation.
- Stored per circuit, with a version.
- Projection function from (x, y) to `s`.
- **Done when:** geometry builds for both fixture circuits, including Madring from its single 2026 session; projection error is under 5 m median on held-out laps.

### T8 — API
- `GET /sessions`, `GET /sessions/{key}`, `POST /replays`, `POST /replays/{id}/control` (play/pause/speed/seek), `GET /live/{id}/state`, `GET /circuits/{id}/geometry`.
- WebSocket `/live/{id}/stream` pushes state deltas and car positions at 4 Hz.
- OpenAPI → TS types (`make types`).
- **Done when:** the API tests pass, and a WebSocket smoke test receives position frames.

### T9 — Frontend
- **Session picker** and **replay controls**.
- **Track map:** Canvas, circuit polyline, 22 car dots in team colours with driver codes. Cars are interpolated along `s` at 60 fps with a 300 ms buffer, and pit-lane cars follow the pit path.
- **Timing tower:** position, driver, gap, interval, tyre + age, stops, last lap.
- **Pit panel:** stops per driver with lap, lane time and stationary time where available.
- **Event banner:** SC/VSC/red, retirements, weather changes.
- **Follow driver:** a selector that highlights the chosen driver and their teammate.
- Must be responsive, with light/dark themes.
- **Done when:** the demo goal is met for both fixture races, and there are component tests for the tower ordering and interpolation.

### T10 — Docs and demo
- Update the README with setup steps and a GIF or screenshot of the replay.
- Add `docs/backlog.md` with ideas deferred during Phase 1.

## Out of scope for Phase 1
Predictions, tyre-degradation fitting, Monte Carlo, strategy, driver ratings, live OpenF1, Reddit/sentiment, auth, deployment.

## Risks to watch
- 2026 data availability or format quirks in OpenF1/FastF1 → the adapters must tolerate missing fields.
- Location data volume → downsampling + hypertable compression.
- Rate limits → cache first, ingest in the background.
