# F1 Strategy — Foundation (v1)

This document defines **what we need** and **the skeleton everything hangs on**. The design doc and engine spec describe the machinery; this document describes the ground rules they must follow.

---

## 1. Vision

A live race companion that, for **all 22 drivers on any circuit**:
- shows every car moving on the circuit map, live or in replay;
- shows pit stops (when, how long) and live tyre degradation per driver;
- **predicts each driver's finish time and finishing position** (with probabilities) and updates the predictions every lap and on every event;
- simulates the rest of the race visually ("ghost cars" on the map);
- proposes and re-evaluates strategies as conditions change.

It is a demonstration and portfolio project, built so that every variable can be swapped, overridden or re-modelled without breaking the others.

---

## 2. The 2026 reality (drives the design)

| Fact | Consequence |
|---|---|
| 22 cars, 11 teams (Cadillac joined) | **Nothing hard-codes 20.** The grid comes from season config. |
| DRS is gone. Overtake Mode gives extra electrical power when within 1 s at a detection point; Boost Mode lets drivers spend energy anywhere within limits; active aero on every lap | The overtaking model uses `overtake_mode_available` instead of `drs`. **Energy** becomes a variable (approximated, since we have no battery telemetry). |
| New car concept (lighter, narrower tyres, big pace spread) | **2023–2025 data doesn't transfer directly.** Use it for structure (e.g. degradation curve shapes, pit loss, circuit overtaking difficulty ranking); fit levels on 2026 sessions. |
| New circuit (Madring) | The circuit geometry builder must work from a single session's data; there is no reliance on older data for a track. |

Rules like the points system, compound rules, grid size and overtaking aid all live in `config/seasons/<year>.yaml`, so 2027 is a config change rather than a rewrite.

---

## 3. Needs catalogue

Priority: **M** = must, **S** = should, **C** = could. The milestone numbers (M1–M6) refer to §9.

### Data
| ID | Need | Pri | MS |
|---|---|---|---|
| D1 | Ingest historical sessions (laps, sectors, positions, intervals, stints, pit stops, race control, weather, car locations) | M | M1 |
| D2 | Replay any stored session as if live, at variable speed | M | M1 |
| D3 | Live ingestion (OpenF1 live subscription) behind the same adapter interface | M | M6 |
| D4 | Season config: teams, drivers, colours, points, rules | M | M1 |
| D5 | Circuit catalogue: geometry, sectors, pit lane, rotation, pit loss, overtaking difficulty | M | M1 |
| D6 | Rain forecast per circuit | S | M5 |
| D7 | Data quality handling: gaps, duplicates, late or corrected data | M | M1 |

### Visualisation
| ID | Need | Pri | MS |
|---|---|---|---|
| V1 | Circuit map with all 22 cars moving smoothly (≥30 fps interpolation) | M | M1 |
| V2 | Timing tower: position, gap, interval, tyre + age, stops, last lap | M | M1 |
| V3 | Pit stop panel: per driver, lap, pit lane time, stationary time where available | M | M1 |
| V4 | Tyre degradation chart per driver/stint, observed vs predicted | M | M2 |
| V5 | Predicted finish time and position odds per driver | M | M2/M4 |
| V6 | Ghost simulation: predicted future positions on the map, scrubbable | S | M4 |
| V7 | Event banner (SC/VSC/red, retirement, rain) | M | M1 |
| V8 | Driver detail: lap history, stints, strategy options | S | M3 |

### Prediction and strategy
| ID | Need | Pri | MS |
|---|---|---|---|
| P1 | Live tyre degradation estimate per driver per stint (fuel-corrected) | M | M2 |
| P2 | Lap time prediction per driver for every remaining lap | M | M2 |
| P3 | Expected finish time per driver (deterministic) | M | M2 |
| P4 | Pit stop prediction: next stop lap and compound per driver (distribution) | M | M3 |
| P5 | Pit stop duration model (lane + stationary, SC/VSC effects) | M | M3 |
| P6 | Full-field Monte Carlo → finishing position probabilities for all 22 | M | M4 |
| P7 | Strategy recommendations for a selected driver | S | M4 |
| P8 | Events: SC/VSC/red, DNF, damage (detected + manual), weather | M | M5 |
| P9 | Recompute on every lap and immediately on critical events | M | M2+ |
| P10 | What-if: user overrides any variable and sees the effect | S | M4 |

### Non-functional
| ID | Need |
|---|---|
| NF1 | New lap → updated predictions: < 2 s deterministic, < 5 s Monte Carlo |
| NF2 | Replay is deterministic and reproducible (same seed → same output) |
| NF3 | Every displayed value has provenance: observed, estimated, predicted, or overridden, and from which model version |
| NF4 | Models, adapters and configs are swappable without touching the engine |
| NF5 | Runs locally with `docker compose up` |
| NF6 | Tested: unit, property (physics sanity), replay backtests |

---

## 4. The variable model (the foundation)

Everything in the race is a **variable**. Components never pass ad-hoc values to each other. They read and write variables through a **registry**, and declare which variables they consume and produce. The system then knows exactly what to recompute when anything changes, much like a spreadsheet.

### 4.1 Variable definition

```yaml
id: car.tyre.deg_rate            # dotted, unique
scope: car_stint                 # race | lap | car | car_lap | car_stint | circuit | season
dtype: float
unit: s_per_lap
kinds_allowed: [observed, estimated, predicted, overridden, prior]
depends_on: [car.lap.time_fuel_corrected, car.tyre.compound, weather.track_temp]
affects:    [car.lap.time_pred, strategy.pit_window]
description: Linear tyre degradation rate for the current stint.
```

### 4.2 Value kinds and precedence

Every stored value carries its **kind**. When several exist, the highest-precedence one wins:

```
overridden (user)  >  observed (data feed)  >  estimated (fitted from observed)  >  predicted (model)  >  prior (config/history)
```

Each value also records: `source`, `model_version`, `state_version`, `timestamp`, and an `uncertainty` (σ or a distribution) where relevant.

This handles the observed/predicted boundary cleanly. For laps already run, lap times are *observed*; for future laps they are *predicted*. When a lap completes, the observed value replaces the prediction, and the difference between them (the residual) feeds back into the *estimated* parameters.

### 4.3 Core variable catalogue

| Group | Variables (examples) | Kind |
|---|---|---|
| Season | grid size, points table, compound rules, overtake aid | prior (config) |
| Circuit | length, sector/mini-sector boundaries, geometry, pit lane loss, SC hazard, overtaking difficulty, fuel effect | prior / estimated |
| Weather | air/track temp, humidity, rainfall, wetness, forecast | observed / predicted |
| Race | lap, total laps, track status, elapsed time | observed |
| Car / driver | base pace, pace σ, reliability hazard, team pit crew stats | prior → estimated live |
| Car × lap | lap time, sectors, position, gap, interval, in/out lap, location (x, y), distance along track | observed / predicted |
| Tyres | compound, age, stint no., degradation rate, cliff lap, used-compound set | observed / estimated |
| Traffic / energy | dirty-air laps, overtake mode available, battle state, energy-state proxy | estimated |
| Pit | stop lap, pit lane time, stationary time, predicted next stop, predicted duration | observed / predicted |
| Damage | suspected, pace penalty, confirmed | estimated / overridden |
| Outputs | expected finish time, position distribution, E[points], recommended strategy | predicted |

### 4.4 Dependency graph and feedback loops

Components declare `inputs -> outputs`. The orchestrator builds a graph and orders it with a **topological sort**.

Real racing has loops: position → traffic → lap time → position. These are broken by **time**. Within a single lap the graph is acyclic; loop edges connect lap *n* to lap *n + 1* (the dashed lines in the diagram).

### 4.5 Components

```python
class Component(Protocol):
    name: str
    inputs: list[VarId]
    outputs: list[VarId]
    def compute(self, ctx: Snapshot) -> dict[VarId, Value]: ...
```

Examples: `TyreDegEstimator`, `PaceEstimator`, `LapTimePredictor`, `PitStopPredictor`, `PitDurationModel`, `PositionResolver`, `DeterministicRacePredictor`, `MonteCarloEngine`, `DamageDetector`, `StrategyOptimizer`.

Swapping a model means registering a different component with the same outputs; the config chooses which one is active.

### 4.6 Orchestration rules

1. An incoming event writes observed values, and **dirty-flags** everything downstream of them.
2. Only dirty components recompute, in topological order. A cheap tier (deterministic predictions) always runs; an expensive tier (Monte Carlo) runs async and is cancellable.
3. Every recompute produces an immutable, versioned **snapshot**. The UI subscribes to snapshots; stale results are discarded.
4. A user override is just a value with kind `overridden`. It triggers the same dirty-flag flow, so what-if analysis costs nothing extra.
5. **Explain API:** for any value, return its kind, source, inputs and model version. This answers "why is Verstappen predicted P3?"

---

## 5. Circuit map and car movement

**Building the geometry** (once per circuit, rebuildable):
1. Take location samples (x, y at ~3.7 Hz) from one clean lap of a single car.
2. Smooth and resample to a closed polyline, then compute cumulative distance `s`.
3. Mark the start/finish line, the sector boundaries (matched from timing) and the pit lane path (from a car's pit lap).
4. Store rotation and corner numbers for display.

The builder must work from a single session, which covers new tracks such as Madring.

**Live and replay positions:**
- Project each location sample onto the polyline to get `s`.
- Render with a small buffer (~300 ms) and interpolate along `s`, not in straight lines between points, so cars stay on the track at 60 fps.

**Simulated (ghost) positions:**
- For predicted laps, convert the predicted lap time into movement along the track using a per-circuit **speed profile**: the fraction of lap time spent in each segment, taken from historical telemetry.
- A pitting car follows the pit lane path for its predicted pit lane time.

**Rendering:** Canvas 2D in Angular (22 cars is trivial). WebGL only if we add trails or heatmaps later.

---

## 6. Tyres, pit stops, finish time — how they connect

**Tyre degradation (live).** For each driver's stint:
1. Correct lap times for fuel burn.
2. Drop in/out laps and laps affected by SC or traffic.
3. Fit the degradation curve, using the circuit/compound prior until enough laps exist (a Bayesian or Kalman update).

The results are a degradation rate, a predicted cliff lap, and an uncertainty band.

**Pit stops.**
- *Observed*: lap and pit lane duration (plus stationary time where available).
- *Predicted*: next stop lap distribution, derived from tyre state, the typical window and team tendencies. Duration comes from the circuit lane loss plus the team's stationary distribution, reduced under SC/VSC.

**Finish time and position.**
- The deterministic tier sums the predicted lap times plus predicted stops for each driver. This gives the expected finish time, and ranking by it gives the expected order.
- The Monte Carlo tier resolves traffic and events and yields a position distribution per driver. It also drives the ghost simulation: the median run, or a user-picked scenario.

---

## 7. Project structure (monorepo)

```
f1-strategy/
├─ docker-compose.yml             # postgres+timescale, redis, api, workers, web
├─ config/
│  ├─ seasons/2026.yaml           # teams, drivers, colours, points, rules
│  ├─ circuits/<circuit_id>.yaml  # metadata, priors; geometry in data store
│  ├─ variables/*.yaml            # variable registry definitions
│  └─ pipelines/default.yaml      # which components are active
├─ backend/                       # Python (uv workspace)
│  ├─ f1core/                     # variable registry, snapshot, graph, orchestrator, units, schemas
│  ├─ f1ingest/                   # adapters: openf1_hist, openf1_live, fastf1, jolpica, openmeteo, replay
│  ├─ f1state/                    # race state builder, event normalisation
│  ├─ f1track/                    # circuit geometry builder, projection, speed profiles
│  ├─ f1models/                   # tyre, pace, pit, overtake, energy, events, weather, damage
│  ├─ f1engine/                   # deterministic predictor, Monte Carlo (Numba), strategy
│  ├─ f1calib/                    # offline fitting jobs, model store
│  └─ f1api/                      # FastAPI: REST + WebSocket
├─ web/                           # Angular
│  └─ src/app/
│     ├─ core/                    # websocket client, snapshot store, generated API types
│     ├─ track-map/               # canvas renderer, interpolation, ghost layer
│     ├─ timing-tower/
│     ├─ pit-panel/
│     ├─ tyre-panel/
│     ├─ predictions/             # finish time, position odds
│     ├─ strategy/
│     └─ what-if/
├─ tests/
│  ├─ unit/  property/  replay/   # physics sanity + backtests
├─ notebooks/                     # exploration, model fitting
├─ data/                          # local cache (gitignored)
└─ docs/                          # design, engine spec, this document
```

**Contracts:**
- Pydantic models are the single source of truth. From them, FastAPI's OpenAPI output generates the TypeScript types for Angular, so the frontend and backend never drift apart.
- Variable definitions in YAML are validated at startup; unknown IDs fail fast.

---

## 8. Engineering rules

1. **Config over code:** season rules, circuits, active models.
2. **Everything goes through the registry.** No hidden globals, and no component reads another component's internals.
3. **Units are explicit** (seconds, laps, metres, °C) and checked.
4. **Every model is versioned.** Snapshots record which versions produced them.
5. **Determinism:** seeded RNG, replay clock, no reliance on wall-clock time in logic.
6. **Degrade gracefully:** missing data → fall back to the prior and show the uncertainty; never crash the pipeline.
7. **Test the physics:** property tests for faster-car-passes, SC-compresses-gaps, pit-resets-tyres, and similar invariants.

---

## 9. Milestones (each one is a demo)

| MS | Demo | Scope |
|---|---|---|
| **M1 — Watch** | Replay any 2026 race: 22 cars moving on the map, timing tower, pit panel, events | D1–D2, D4–D5, D7, V1–V3, V7, f1core skeleton |
| **M2 — Predict pace** | Live tyre degradation per driver, lap time predictions, expected finish time and order updating every lap | P1–P3, P9, V4–V5 |
| **M3 — Predict stops** | Predicted next stop lap/compound/duration for everyone; recomputed on each stop | P4–P5, V8 |
| **M4 — Simulate** | Monte Carlo position odds for all 22, ghost cars on the map, what-if overrides, strategy for a chosen driver | P6–P7, P10, V6 |
| **M5 — Chaos** | SC/VSC/red, DNFs, damage detection, rain | P8, D6 |
| **M6 — Live** | Real race weekend via OpenF1 live | D3 |

M1 is the foundation *and* the first thing that looks impressive. Every later milestone adds variables and components, not rewrites.

---

## 10. Open decisions

1. **Python version and tooling:** proposal is Python 3.12, `uv`, `ruff`, `pytest`, Numba.
2. **Angular version and state management:** proposal is Angular 18+ with signals; no NgRx unless it becomes necessary.
3. **Hosting:** local only for now, or a cheap VPS/Azure for the demo?
4. **Live data budget:** when to buy the OpenF1 live subscription (only needed for M6).
