# F1 Strategy Optimizer — System Design (v1)

## 1. Goal

For a chosen car ("our car"), recommend the race strategy that **maximises expected championship points**, and show the **probability distribution of finishing positions** for each candidate strategy (e.g. P(win), P(top 3), P(top 5), P(points)). Recommendations update live as the race unfolds: laps, gaps, tyres, pit stops, safety cars, weather and damage.

The prototype optimizer answered "what is the fastest plan in clean air?". This system answers the question a strategist actually faces: **"given everyone else on track, what plan gives us the best finishing position?"** Those differ, because track position, traffic and overtaking difficulty often matter more than raw pace.

## 2. Requirements

### Functional
1. Ingest historical data (2023+) and live timing during a session.
2. Maintain an up-to-date **race state** for all 20 cars.
3. Calibrate models from history: tyre degradation, driver/car pace, pit loss, overtaking difficulty per track, safety car likelihood, weather effects.
4. Simulate the rest of the race thousands of times per candidate strategy, for all cars.
5. Output per strategy: expected points, expected position, full position distribution, and key risks (e.g. "exposed to undercut from car 16").
6. Recompute on every completed lap and immediately on key events (SC/VSC, rain start, retirement, damage).
7. Accept **manual inputs** from the user: damage and its pace cost, opponent strategy guesses, and forced constraints ("must pit within 3 laps").
8. **Replay mode:** run any past race as if live. This is how we develop and test without paying for live data, and how we backtest.

### Non-functional
| Concern | Target |
|---|---|
| Latency: new lap → updated recommendation | < 5 s (live data itself arrives ~3 s behind) |
| Simulation budget | ~20 candidates × 2,000 runs per update |
| Availability | Best effort (personal project); must degrade gracefully if a feed drops |
| Cost | Free tiers + OpenF1 live subscription only when needed |
| Usage | Personal, educational, non-commercial (matches data-source terms) |

### Constraints and assumptions
- Solo developer; strong in .NET/Angular/Java, Python is the natural fit for the data and simulation work.
- No team-internal data: no fuel loads, tyre temperatures, or damage telemetry. These are **estimated or entered manually**.
- Opponent strategies are unknown and must be **predicted probabilistically**.

## 3. Data sources

| Source | What we use | Mode | Notes |
|---|---|---|---|
| **OpenF1** | Laps, sector times, intervals/gaps, positions, pit stops, stints/compounds, race control (flags, SC, incidents), weather (track/air temp, rainfall), team radio | Historical (free, 2023+) and live (paid subscription, ~3 s delay) | Primary source. Non-commercial use only. |
| **FastF1** | Cleaned historical laps, tyre life, telemetry | Historical | Best for calibration datasets. Caches locally. |
| **Jolpica (Ergast successor)** | Results, grids, standings, calendar | Historical | Championship context, points tables. |
| **Open-Meteo** | Hourly rain probability and intensity at circuit coordinates | Forecast | OpenF1 gives current weather only; forecasts drive "rain in 10 laps" scenarios. |
| **User input** | Damage, opponent strategy hints, constraints | Live | Via dashboard. |

**Damage has no data feed.** It is estimated from three signals: race control incident messages involving our car, sudden unexplained pace loss versus the model, and unscheduled pit stops. The user can confirm the estimate or override it with a pace penalty.

## 4. Architecture

Two planes:
- **Data plane:** get data in, clean it, and keep the truth about the race.
- **Decision plane:** turn that truth into strategies and probabilities.

### 4.1 Components

**Ingestion service** (Python)
- One adapter per source behind a common interface: `SourceAdapter.stream() -> Iterator[RawEvent]`.
- `OpenF1LiveAdapter` polls or subscribes to live endpoints; `ReplayAdapter` replays a stored historical session at 1×–50× speed using the original timestamps. The rest of the system cannot tell the two apart. This is the key design choice for testability.
- A normalizer converts raw payloads into **domain events** (§5) and publishes them to the bus.
- Deduplicates by `(session, driver, lap, type)` and tolerates out-of-order arrival.

**Event bus** (Redis Streams)
- Topics: `timing`, `pit`, `race_control`, `weather`, `manual_input`.
- Chosen over Kafka: one container, persistent enough, consumer groups included. Revisit only if we ever go multi-user at scale.

**Race state service** (Python)
- Consumes events and maintains the authoritative `RaceState` snapshot in Redis (§6).
- Emits `state.lap_completed` and `state.critical_event` triggers.
- Runs a **pace residual monitor**: if a car is slower than the model predicts by more than a threshold for N laps, it raises `suspected_damage` or `suspected_issue`.

**Storage** (PostgreSQL + TimescaleDB)
- Holds the event log, laps, stints, pit stops, weather, and results for every ingested session.
- Serves as the calibration dataset and the replay source.

**Model calibration** (offline batch, Python)
- Runs after each race weekend and on demand. Produces versioned model artifacts (JSON/Parquet) in a model store:
  - tyre degradation per compound × circuit × track temperature band
  - driver/car base pace (from practice long runs and qualifying, updated live in race)
  - pit loss distribution per circuit (lane time + stationary time)
  - overtaking model per circuit
  - SC/VSC hazard per circuit, DNF hazard per team
  - wet/intermediate/slick crossover model

**Strategy engine** (Python, NumPy + Numba)
- Candidate generator → Monte Carlo race simulator → scorer (§7).
- Stateless: input is `RaceState + model version + user overrides`, output is `StrategyReport`. This makes it easy to scale horizontally and to test.

**API gateway** (FastAPI)
- REST for queries and commands, WebSocket for pushing live reports (§8).
- Option later: a .NET BFF with SignalR if you want the backend in your main stack. Not needed for v1.

**Dashboard** (Angular)
- Live timing tower, gap chart, strategy cards with finish-position distributions, what-if panel, damage/override input.

### 4.2 Live update flow

```
OpenF1 live ──► Ingestion ──► Redis Streams ──► Race state
                                                   │ lap completed / SC / rain / damage
                                                   ▼
                              Strategy engine ◄── model store
                                   │ StrategyReport (versioned by lap)
                                   ▼
                              API gateway ──WebSocket──► Dashboard
                                   ▲
                 Dashboard ──REST (overrides, what-if)──┘
```

Rules:
- Each report is tagged with `state_version` (lap + event sequence). The UI drops stale reports.
- A critical event **cancels** any in-flight run and starts a new one.
- Two-stage compute: a fast pass (200 runs) is pushed within ~1 s, then refined (2,000+ runs) and pushed again.

## 5. Domain events

```json
{ "type": "lap_completed", "session_key": 9158, "driver": 16, "lap": 23,
  "lap_time": 94.312, "sectors": [30.1, 34.0, 30.2], "position": 4,
  "gap_to_leader": 12.4, "interval": 1.1, "ts": "2026-09-20T13:42:10Z" }

{ "type": "pit_stop", "driver": 16, "lap": 24, "pit_lane_time": 21.8,
  "new_compound": "HARD", "new_tyre_age": 0 }

{ "type": "race_control", "category": "SafetyCar", "status": "DEPLOYED", "lap": 31 }

{ "type": "weather", "track_temp": 38.5, "air_temp": 27.1, "rainfall": false,
  "forecast": [{ "minutes_ahead": 15, "rain_prob": 0.4, "intensity_mm_h": 0.8 }] }

{ "type": "manual_input", "kind": "damage", "driver": 16,
  "pace_penalty_s": 0.35, "source": "user" }
```

## 6. Race state

```
RaceState
  session, circuit, lap, total_laps, track_status (GREEN|SC|VSC|RED),
  weather { track_temp, rain_now, forecast[] }
  cars[20] {
    driver, team, position, gap_to_leader, interval_ahead,
    compound, tyre_age, stints_so_far, compounds_used,
    pit_stops, in_pit, retired,
    pace_estimate { base, uncertainty },
    damage { suspected: bool, penalty_s, confirmed_by_user },
    predicted_strategy { distribution over next pit lap and compound }
  }
  our_driver
  state_version
```

## 7. Strategy engine

### 7.1 Candidate generation
Instead of enumerating every possible full-race plan, generate a small set of plausible plans from the current state:
- **Pit window:** pit this lap, or at +1, +2, … up to the tyre cliff.
- **Compound choice:** only compounds still available and rule-legal (two dry compounds unless wet running).
- **Stop count:** remaining stops 0–2.
- **Event responses:** pit under this SC or stay out; switch to intermediates now or wait.

The deterministic DP from the prototype pre-ranks candidates by clean-air pace. Only the top ~20 go to full simulation.

### 7.2 Monte Carlo race simulation
Each run simulates **all 20 cars, lap by lap**, from the current state to the flag.

**Lap time model** per car per lap:
```
t = base_pace(driver, car)
  + tyre(compound, age, track_temp)       # fitted deg curve incl. cliff
  - fuel_effect × lap
  + dirty_air(gap_ahead)                   # penalty when < ~1.5 s behind
  + weather(compound, wetness)             # slick-in-wet / wet-in-dry penalty
  + damage_penalty
  + noise ~ N(0, σ_driver)
```

**Track position and overtaking.** Cars are processed in running order. If car B's natural lap would put it ahead of car A in front:
```
P(pass) = sigmoid( β0(circuit)            # overtaking difficulty (Monaco very low)
                 + β1 × pace_delta
                 + β2 × tyre_age_delta
                 + β3 × compound_delta
                 + β4 × DRS_available )
```
- Pass succeeds: swap positions, with a small time cost for both cars.
- Pass fails: B is held at A's lap time plus a minimum gap, and pays the dirty-air penalty. This is what makes **traffic** and **undercut/overcut** emerge naturally rather than being hard-coded.

**Pit stops.** Stationary time plus lane time are sampled from the circuit distribution, with a small probability of a slow stop. The car rejoins where its new cumulative time places it. The model applies extra cost for rejoining into traffic and a cold-tyre out-lap.

**Random events**, sampled per lap:
- SC/VSC: per-circuit hazard. The pit loss is reduced during these periods, and the field bunches up (gaps compressed).
- Rain: sampled from the forecast. It changes grip, and cars switch tyres based on the crossover model.
- DNF: hazard per team; a DNF can itself trigger an SC.
- Damage: small probability after a failed close pass.

**Opponent behaviour.** Each opponent follows a sampled strategy drawn from its `predicted_strategy` distribution. The rules: pit near the cliff, cover a rival's undercut when within ~2 s, and pit under SC if tyre age exceeds a threshold. Opponents also react to our pit stop, which makes the simulation interactive rather than static.

**Variance reduction.** All candidates use the same random seeds (common random numbers). Differences between strategies then reflect the strategy, not luck.

**Performance.** 20 candidates × 2,000 runs × 20 cars × ~40 remaining laps ≈ 32M car-lap steps. This is feasible in under 5 s with runs vectorised in NumPy and the pass logic in Numba. It parallelises across candidates.

### 7.3 Scoring
For each candidate:
- finish position histogram → P(P1), P(top 3), P(top 5), P(top 10)
- **expected points** using the points table (the primary objective)
- expected position, and the 10th/90th percentile of position
- risk profile selectable by the user: `max_expected_points` (default), `max_P(podium)`, or `min_P(out_of_points)`

The engine returns the best candidate and the 3–5 runner-ups, each with a short explanation generated from simulation statistics, e.g. "undercut on car 4 succeeds in 64% of runs" or "exposed if SC after lap 40".

### 7.4 Probability quality
Probabilities are only useful if they are **calibrated**: events given 30% should happen about 30% of the time. Validation (§10) measures this directly.

## 8. API

REST:
```
GET  /sessions?year=2025                     list sessions
POST /replays        {session_key, speed}    start replay → live_id
GET  /live/{id}/state                        current RaceState
GET  /live/{id}/strategies                   latest StrategyReport
POST /live/{id}/overrides                    damage, opponent hints, constraints
POST /live/{id}/what-if  {candidate, events} simulate a user-defined plan / scenario
POST /config/our-driver  {driver}
```

WebSocket `/live/{id}/stream` pushes:
```json
{ "type": "strategy_report", "state_version": "L23.E412", "quality": "refined",
  "recommendation": {
    "id": "pit_L24_HARD",
    "label": "Box lap 24 → Hard to end",
    "expected_points": 11.2, "expected_position": 4.3,
    "probs": { "p1": 0.04, "top3": 0.31, "top5": 0.80, "points": 0.97 },
    "position_hist": [0.04, 0.12, 0.15, 0.27, 0.22, 0.10, 0.05, 0.03, 0.01, 0.01],
    "insights": ["Undercut on #4 succeeds in 64% of runs"]
  },
  "alternatives": [ ... ] }
```
Plus `race_state` deltas and `alert` messages (SC deployed, suspected damage).

## 9. Data model (core tables)

```
session(session_key PK, year, circuit_id, type, date_start, total_laps)
circuit(circuit_id PK, name, lat, lon, pit_loss_mean, pit_loss_sd, overtake_beta0, sc_hazard)
driver_session(session_key, driver_no, team, grid_pos)
lap(session_key, driver_no, lap_no, lap_time, s1, s2, s3, position,
    gap_to_leader, interval, compound, tyre_age, track_status, ts)   -- hypertable
pit_stop(session_key, driver_no, lap_no, lane_time, stationary_time, compound_in, compound_out)
race_control(session_key, ts, lap_no, category, flag, message, driver_no NULL)
weather(session_key, ts, track_temp, air_temp, humidity, rainfall, wind_speed)  -- hypertable
overtake(session_key, lap_no, attacker, defender, success, pace_delta, tyre_delta, drs)
model_artifact(version PK, created_at, kind, circuit_id NULL, params JSONB, metrics JSONB)
strategy_report(live_id, state_version, created_at, payload JSONB)
```

The `overtake` table is derived by detecting position changes between consecutive laps, excluding pit-stop and retirement effects. It is the training data for the overtaking model.

## 10. Validation and backtesting

- **Replay backtests** on 2023–2025 races, run at every lap:
  - **Calibration:** reliability curves and Brier score for P(top N).
  - **Accuracy:** mean absolute error of predicted versus actual finishing position.
  - **Strategy value:** compare our recommendation with what the team actually did, and with the simulated counterfactual.
- **Unit tests** for the simulator's physics: a faster car eventually passes, a Monaco-like circuit rarely allows passes, the undercut works when the tyre delta is large.
- **Performance tests** to hold the 5 s latency budget.

## 11. Trade-offs and decisions

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Backend language | Python | .NET | FastF1/NumPy/Numba ecosystem; the sim is the core. A .NET BFF can be added later. |
| Bus | Redis Streams | Kafka | Simpler to run solo; enough throughput. |
| DB | Postgres + Timescale | Mongo, plain files | Relational joins for calibration; time-series performance. |
| Optimization | Candidate set + Monte Carlo | Full DP/RL | Handles interaction and uncertainty; explainable. RL could be explored later. |
| Live data | OpenF1 paid live + replay for dev | Scraping the F1 live timing feed | Stable, documented, fewer terms-of-use risks. |
| Opponent model | Rule-based + probabilistic | Game-theoretic | Good enough for v1; game theory is a later upgrade. |

## 12. Risks

- **Licensing:** OpenF1 is for non-commercial use; any commercial use needs a licence.
- **Hidden information:** fuel, tyre temperatures and real damage are unknown, so uncertainty will be wide. Showing it honestly beats false precision.
- **Weather** is the largest single error source; forecasts at circuit scale are coarse.
- **Overfitting per circuit:** only a few races per track per year. Share parameters across similar circuits (hierarchical model).
- **Latency spikes** during SC periods, when every car pits at once.

## 13. Roadmap

| Phase | Deliverable |
|---|---|
| **1. Data foundation** | Docker setup (Postgres/Timescale, Redis). OpenF1 + FastF1 ingestion into the DB for 2023–2025. Replay adapter. |
| **2. Race state + dashboard skeleton** | Race state service, FastAPI + WebSocket, Angular timing tower driven by replay. |
| **3. Calibration v1** | Tyre degradation, pace, pit loss, overtaking model, SC hazard. Model store. |
| **4. Simulator v1** | Full-field Monte Carlo in dry conditions with traffic, overtaking and pit stops. Finish distributions. |
| **5. Optimizer + live loop** | Candidate generation, expected-points scoring, two-stage recompute, strategy cards in the UI. |
| **6. Events** | SC/VSC, DNF, weather with forecast, damage detection plus manual override. |
| **7. Backtesting + calibration report** | Reliability curves, accuracy metrics, tuning. |
| **8. Live** | OpenF1 live adapter for real race weekends. |

## 14. Revisit as it grows

- Opponent modeling (game theory, learning team tendencies)
- Multi-user support (auth, per-user sessions) → maybe Kafka and a separate BFF
- GPU / Rust simulator core if the candidate or run count grows
- Qualifying and sprint strategy modes
