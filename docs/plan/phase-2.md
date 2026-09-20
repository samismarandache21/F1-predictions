# Phase 2 — M2 "Predict pace" (implementation plan)

**Demo goal:** while replaying a race, every driver has a live tyre-degradation estimate, a
predicted lap time for the next lap, and an expected finish time/order — all updating every lap,
each one showing whether it's observed, estimated, or a prior, per
`docs/f1-strategy-foundation.md` §4.2.

Needs covered (§3 of the foundation doc): P1 (tyre degradation), P2 (lap time prediction), P3
(expected finish time), P9 (recompute on every lap), V4 (degradation chart), V5 (predicted finish
time/order display). P4–P8 (pit prediction, Monte Carlo, strategy, chaos events) stay out of scope
— see M3–M5.

## Decisions (defaults; change here if needed)

| Topic | Decision |
|---|---|
| **Architecture** | M1's `f1state.RaceState` is plain dataclasses, not `f1core`'s registry/Snapshot — the right call then, since M1 had only `observed` values and precedence was moot. M2 is the first place `overridden > observed > estimated > predicted > prior` actually matters (an estimated deg rate overriding a circuit's prior, for instance), so the *new* prediction variables go through a real `f1core` orchestrator for the first time. `f1state.RaceState` is not refactored to sit on top of `Snapshot` — that's a bigger, riskier change to already-tested M1 code for no M2 requirement. Instead, `f1state.RaceState`/`CarState` gain plain fields mirroring each prediction Snapshot's *resolved* (winning) values, the same pattern already used for `team`/`team_colour` (T9). Revisit a full merge only if a later milestone needs it. |
| Degradation model form | `t_tyre(age) = k0 + k1·age`, cliff (`s·max(0, age − cliff)`) held out of the fit and fixed at a prior (`cliff_lap`, generic default 20 laps). **Revised during T2**: validated live against the real Monza 2025 fixture (session_key=9912, driver 1's 37-lap opening stint, which never reaches its cliff) — jointly fitting `k0, k1, cliff-hinge-slope` on a single stint is unstable (the 3-parameter fit came out with a negative base slope offset by a large hinge term). A cliff needs either more laps than a typical stint gives or a mined prior (research.md §3.2); estimating it is `docs/backlog.md`. |
| Fuel correction | Fixed prior: 0.05 s/lap improvement per lap of race distance (Pitwall's calibrated default, research.md §3.4/§10.5), folded out before fitting degradation. Not yet calibrated per-circuit — flagged in code, not hidden. |
| Fit method | **Revised during T2**: ordinary least squares (`numpy.linalg.lstsq`), not weighted, refit on the growing set of clean-air laps in the current stint each time a new one completes. Weighting by recency was in the original plan but added no value once the cliff was pulled out of the fit (see above) — plain OLS is simpler and just as good for a 2-parameter fit. Not a Kalman filter yet — design.md/engine-spec.md describe one as a later live-refinement; a straight refit is fully deterministic and enough to demo P1. Kalman filter is `docs/backlog.md`. |
| Clean-air lap definition | Exactly `CLAUDE.md`'s glossary: interval to the car ahead > 2 s, not an in/out lap, green flag. |
| Minimum laps before "estimated" | 5 clean-air laps in the current stint. Below that, the prior wins (wider uncertainty), per CLAUDE.md rule 7. |
| Pace model | EWMA (α configurable, default 0.3) of fuel- and tyre-corrected clean-air lap times per driver. Seeded from a flat, weak prior (no quali/practice data is ingested in M1/M2) — every driver starts equal; the EWMA converges within a handful of laps. Per-driver skill priors are `docs/f1-driver-ratings.md` territory, explicitly backlogged. |
| Finish-time prediction scope | **Extrapolates the current compound/stint's degradation trend to the end of the race, assuming no further pit stops.** This is a deliberate M2-only simplification — pit-stop prediction is M3 (P4/P5). The UI must show this assumption, not hide it (a driver who is clearly about to pit will otherwise get a nonsense finish time). |
| Degradation priors per circuit | New optional `tyre_deg_prior` map on circuit config (`{compound: {k0, k1}}`). Monza/Madring start without one (cold start / no compound-specific data yet) and fall back to a single generic prior — never fabricated per-compound numbers we don't have (foundation doc §2: "do not hard-code soft degrades fastest"). |
| Recompute trigger | Per-driver dirty-flag on that driver's own `lap_completed` event (cheap, local, matches P9's "< 2 s deterministic" budget trivially at this scale). A broader recompute-everyone-on-critical-event path is stubbed but not load-bearing until M5's chaos events exist. |
| Uncertainty | Every predicted/estimated value carries an `uncertainty` (σ), per `f1core.Value`. Widens automatically when falling back to a prior. No fabricated false precision. |

## Tasks

Each task: implement → tests → `make lint test` → short summary.

### T1 — `f1core`: the orchestrator
- `f1core/orchestrator.py`: given a `VariableRegistry`, a `DependencyGraph`, and a list of
  registered `Component`s (the `Component` protocol from foundation.md §4.5), run components in
  topological order over a `Snapshot`, respecting dirty-flags from `DependencyGraph.downstream()`.
  Loads which components are active from `config/pipelines/default.yaml` (currently `components:
  []`; M2 is the first thing that populates it).
- Extend `config/variables/`: `car.tyre.deg_rate` (car_stint, `_s_per_lap`), `car.tyre.deg_cliff_lap`
  (car_stint), `car.pace.base_s` (car), `car.lap.time_pred` (car_lap, kind `predicted`, distinct
  from the M1 `car.lap.time_s` observed var — a future lap's prediction and a completed lap's
  observation are different variables, not the same one with different kinds racing each other),
  `car.race.finish_time_pred` (car).
- **Done when:** unit tests show a registered no-op/identity component runs in the right order,
  only dirty components recompute after a targeted update, and an unregistered pipeline (empty
  `components: []`, i.e. today's M1 config) is a correct no-op.

### T2 — `f1models`: tyre degradation estimator (P1) — done
- `backend/f1models/src/f1models/degradation_math.py`: pure NumPy core (no `f1core` dependency, so
  testable ahead of the real 3.12 toolchain) — `fuel_corrected_lap_time`, `fit_linear_degradation`
  (2-parameter OLS, see the revised Decisions rows above), `clamp_degradation_rate` (clips to
  `[0.0, 0.22]` s/lap, research.md §3.6).
- `backend/f1models/src/f1models/tyre.py`: `TyreDegEstimator` component wrapping it — filters a
  driver's current-stint laps to clean-air-only, falls back to `DegradationPrior` (generic:
  `k1=0.08`, `cliff_lap=20`) under 5 clean laps, else fits `car.tyre.deg_rate` as `kind=estimated`;
  `car.tyre.deg_cliff_lap` always stays `kind=prior` in M2 v1.
- **Done:** `tests/unit/f1models/test_degradation_math.py` (runs on this dev machine) validates the
  fit against the real Monza 2025 fixture
  (`tests/fixtures/openf1/monza_2025_driver1_stint1_laps.json`, session_key=9912, driver 1's
  opening stint) — the naive uncorrected slope comes out negative (confounded by fuel burn,
  research.md §3.6/§12 #1), the fuel-corrected slope comes out ≈ +0.028 s/lap, within the plausible
  clamp range — plus synthetic-slope-recovery and clamp-boundary tests.
  `tests/unit/f1models/test_tyre.py` covers the `Component` wrapper (prior fallback, clean-air
  filtering, current-stint-only filtering) but needs real `f1core.Value`/`Snapshot` construction,
  so — like `f1core`'s own suite — it isn't runnable until the project's real Python 3.12 toolchain
  is installed; written and hand-traced against `f1core.snapshot`/`values`/`registry`'s actual code.

### T3 — `f1models`: pace estimator — done
- `backend/f1models/src/f1models/pace_math.py`: pure core (no `f1core` dependency) —
  `tyre_corrected_lap_time` (subtracts estimated wear) and `ewma` (seeded by the first value
  itself — the flat, weak prior the Decisions table calls for, not a fabricated circuit-specific
  constant).
- `backend/f1models/src/f1models/pace.py`: `PaceEstimator` component — reads a driver's whole
  `car.lap.observation` history (not just the current stint: `car.pace.base_s` is car-scoped), fuel-
  and tyre-corrects each clean-air lap, EWMAs them (α=0.3 default), falls back to `kind=prior` under
  3 clean laps. Tyre correction uses the *current* `car.tyre.deg_rate` applied uniformly across a
  driver's whole history (no per-stint deg_rate history is kept) — a deliberate M2 v1 approximation,
  written into `predictions.yaml`'s `car.pace.base_s` description rather than hidden.
- Also fixed while wiring this up: `config/variables/predictions.yaml`'s `depends_on` on
  `car.tyre.deg_rate`/`car.tyre.deg_cliff_lap` still pointed at the old M1 `car.lap.time_s`/
  `car.tyre.compound`/`car.tyre.age_laps` vars instead of the new `car.lap.observation` bundle T1
  introduced — harmless for the orchestrator (edges also come from `car.lap.observation.affects`,
  which was already correct) but misleading. Corrected, and added `car.tyre.deg_rate` to
  `car.pace.base_s`'s `depends_on`/`affects` so the orchestrator actually runs `TyreDegEstimator`
  before `PaceEstimator` for a given scope_id.
- **Done:** `tests/unit/f1models/test_pace_math.py` (runs on this dev machine) includes the exact
  property test the original done-when asked for — a driver stepping 2 s/lap faster has their EWMA
  move monotonically towards the new pace, arriving within 0.05 s well before 15 laps but not on lap
  1 — plus fixed-point and single-value edge cases. `tests/unit/f1models/test_pace.py` covers the
  `Component` wrapper (prior fallback, clean-air filtering, the deg_rate-fallback path) the same way
  `test_tyre.py` does: written and hand-traced, not runnable until the real 3.12 toolchain lands.
  Shared `f1core` fixtures for both Component-test files moved into
  `tests/unit/f1models/conftest.py`, with the `f1core` imports deferred into each fixture body so
  loading this conftest doesn't break collection for the pure-math test files in the same
  directory.

### T4 — `f1engine`: lap time and finish time predictors (P2, P3) — done
- `backend/f1engine/src/f1engine/prediction_math.py`: pure core (no `f1core` dependency) —
  `predict_lap_time_s` (next lap = pace + tyre delta at the projected tyre age − the fuel benefit at
  that lap number; inverts f1models' fuel/tyre corrections) and `predict_finish_time_s` (real
  elapsed time over laps completed so far, plus a predicted lap time for every remaining lap under
  the "no more stops" M2 assumption, see Decisions). Deliberately does **not** apply
  `deg_cliff_lap`'s cliff-acceleration term — the fit is linear-only (T2), so there's no estimated
  magnitude for it to apply; tracked as a prior for M3+, applying it is `docs/backlog.md`.
- `backend/f1engine/src/f1engine/predictors.py`: `LapTimePredictor` (→ `car.lap.time_pred`) and
  `DeterministicRacePredictor` (→ `car.race.finish_time_pred`) Components wrapping the above, both
  `kind=predicted`, falling back to the generic tyre-degradation prior when `car.tyre.deg_rate`
  hasn't resolved yet (mirrors `f1models.pace.PaceEstimator`'s fallback). The predicted running
  order (sorting resolved finish times across all 22 drivers) is explicitly **not** built here — a
  Component's `compute()` only ever sees one driver's `scope_id` at a time, so cross-driver sorting
  belongs at the assembly layer instead; that's T5/T6's job, not `f1engine`'s.
- **Done:** `tests/unit/f1engine/test_prediction_math.py` (runs on this dev machine) gives the
  exact summed finish time on synthetic pace/deg inputs the done-when asked for, plus a check against
  the real Monza fixture (same 37-lap driver-1 stint, extrapolated to the real 53-lap race distance)
  landing in a physically sane 75–100 minute window. `tests/unit/f1engine/test_predictors.py` covers
  the `Component` wrapper the same way `f1models/test_tyre.py` does: written and hand-traced, not
  runnable until the real 3.12 toolchain lands.

### T5 — `f1state`/`f1core`: wire recompute into the live pipeline (P9) — done
- `backend/f1state/src/f1state/predictions.py` (new): `PredictionPipeline` — constructs the real T1
  `Orchestrator`/`DependencyGraph`/`VariableRegistry` plus the M2 Components (`TyreDegEstimator`,
  `PaceEstimator`, `LapTimePredictor`, `DeterministicRacePredictor`) once, and holds one running
  `f1core.Snapshot` across the whole session (keyed by driver via scope_id, so one Snapshot serves
  all 22 cars). `on_lap_completed(car, event, total_laps=...)` builds the `car.lap.observation`
  Value straight off the `lap_completed` event — `is_clean_air` reads the event's own
  `is_pit_out_lap`/`is_pit_in_lap`/`interval_s`/`track_status` fields directly (no heuristic needed:
  f1ingest already derives these per-lap) — recomputes via the orchestrator, and returns whatever
  subset of the five prediction var_ids has resolved. Also seeds `race.total_laps` (from `RaceState`,
  which already tracks it) since nothing else in this per-driver pipeline would ever set it, and
  degrades gracefully (returns `{}`) when `event.lap_time_s` is `None` (a known OpenF1 gap) rather
  than feeding a fit or a race-time sum a `None`.
- `f1state/state.py`: `CarState` gains `deg_rate_s_per_lap`, `deg_rate_kind`, `deg_uncertainty`,
  `predicted_lap_time_s`, `predicted_finish_time_s`, `prediction_kind`. One shared `prediction_kind`
  covers both `predicted_*` fields (not two separate kind fields) since `car.lap.time_pred`/
  `car.race.finish_time_pred` each allow only `kind=predicted` in M2 v1 — there's no per-field
  provenance to distinguish yet; `deg_rate_kind` is the one that's actually meaningful
  (`prior`/`estimated`).
- `f1state/builder.py`: `RaceStateBuilder.apply_predictions(state, driver, resolved)` mirrors a
  driver's resolved Values onto `CarState`, reading only duck-typed `.data`/`.kind`/`.uncertainty` —
  never constructing or importing a real `f1core.Value` — so it stays testable ahead of the real
  3.12 toolchain, same as `apply`'s event handling. A driver with no new resolved values this lap
  (e.g. still below every Component's min-clean-laps threshold) keeps their previous fields rather
  than being reset to `None`.
- `f1api/live.py`: `ReplaySession` takes an optional `predictions: PredictionPipeline | None = None`
  (default `None` keeps every existing test's behaviour identical); on each `LapCompletedTrigger`
  from `builder.apply()`, it calls `predictions.on_lap_completed(...)` and mirrors the result via
  `apply_predictions`. `LiveReplayManager.create()` constructs the real `PredictionPipeline` (lazy
  import, same pattern as its other f1core-touching lines).
- **Done:** `tests/unit/f1api/test_live_session.py` (runs on this dev machine) covers the wiring
  end-to-end with a fully duck-typed fake `PredictionPipeline` — proving `consume()` drives it on
  `lap_completed` and skips it for `location_update`, and that passing no pipeline at all reproduces
  M1's exact prior behaviour. `tests/unit/f1state/test_builder.py`'s new `apply_predictions` tests
  also run for real (no f1core needed to read a duck-typed Value). `tests/unit/f1state/test_predictions.py`
  covers `PredictionPipeline` itself: its `_is_clean_air` test runs for real (pure logic, no f1core);
  everything that constructs a real `PredictionPipeline` is written and hand-traced only, failing at
  the same `enum.StrEnum` import this whole session has hit everywhere else in `f1core` — not a new
  gap, just surfaced as a test *failure* here instead of a collection *error*, because this module's
  f1core imports are lazy enough that the file itself still collects. The "Explain" path exists as
  `PredictionPipeline.explain(var_id, driver)` (delegates to `Snapshot.explain`); it isn't wired to
  an HTTP endpoint yet — that's T6/backlog, not this task.

### T6 — `f1api`: expose predictions — done
- `f1api/schemas.py`: `CarStateOut` gains the same six fields T5 added to `CarState`
  (`deg_rate_s_per_lap`, `deg_rate_kind`, `deg_uncertainty`, `predicted_lap_time_s`,
  `predicted_finish_time_s`, `prediction_kind`), all `Optional`, mirrored 1:1 in
  `from_car_state`. No `LiveFrameOut`/`RaceStateOut` change needed — both already nest
  `CarStateOut`, so the WS stream and `GET /live/{id}/state` pick this up automatically, exactly as
  planned (no new endpoint).
- **Done:** `tests/unit/f1api/test_live_router.py` (runs for real on this dev machine — f1api's
  whole stack is testable on 3.9, unlike most of `f1core`) gained
  `test_websocket_frame_includes_a_populated_prediction` (a car with all six fields set comes
  through the WS frame unchanged) and `test_websocket_frame_has_null_predictions_for_a_car_with_none_yet`
  (a car with no predictions yet serializes them as `null`, not a missing key or a crash). All 11
  tests in the file pass. `web/src/app/core/api-types.ts` (the hand-authored stand-in for `make
  types`' generated output) is **not** updated here — that's T7's job, since it's the first task that
  actually consumes these fields on the frontend.

### T7 — frontend: V4 (degradation chart) and V5 (predicted finish/order) — done
- Backend gap closed first: CarStateOut only ever carried the *latest* lap's fields, not full lap
  history, and `is_clean_air` (needed for "observed clean-air laps vs. the fitted curve") was
  computed inside `f1state.predictions.PredictionPipeline` and then discarded — never reached the
  frontend. Added `car.lap.observation` to `PredictionPipeline`'s returned values (read via the
  `observation` Value directly, not `Snapshot.get`, since it lives under the `"{driver}:{lap}"`
  scope_id convention, not the bare driver one everything else uses) and a new
  `CarState.last_lap_is_clean_air` field, mirrored through `apply_predictions` and
  `CarStateOut`/`api-types.ts` the same way as T5/T6's other fields. This is completing what T7
  itself already required, not new scope.
- `web/src/app/degradation-chart/`: `degradation-history.ts` (pure, no Angular) — since the backend
  never streams lap-by-lap history, `DegradationHistoryTracker` accumulates one point per completed
  lap out of the same ~4 Hz WS frames the rest of the UI already consumes (mirroring how
  `track-map/interpolation.ts` builds its own render buffer rather than needing the backend to
  buffer positions), reset on a stint change so it never mixes tyres. `fittedLinePreview` draws a
  two-point line through the mean of the *clean-air* points at the reported `deg_rate_s_per_lap` —
  explicitly documented as a display aid anchored to the resolved slope, not a re-fit of
  `f1models.degradation_math`'s real model (the frontend never sees the raw fit inputs).
  `degradation-chart.component.ts`: an SVG scatter (clean laps solid, dirty laps dim) plus the fit
  line, for the followed driver, badging `deg_rate_kind` ("estimated"/"prior").
- `web/src/app/timing-tower/sort-cars.ts`: `sortCarsByPredictedFinish`/`predictedPositionsByDriver`
  — the predicted running order has to be computed here, not in `f1engine`, since
  `DeterministicRacePredictor.compute()` only ever sees one driver's `scope_id` per call (see
  `f1engine/predictors.py`'s module docstring) and can't rank across all 22 cars itself. Two new
  timing-tower columns: "Pred. pos" (ranked, colour-coded gain/loss vs. current position) and "Pred.
  finish" (formatted time plus the same estimated/prior badge as the degradation chart).
- **Done:** written and statically checked the same way as T9's frontend work (import/export
  resolution + brace-balance scripts across all 25 `src/app/**/*.ts` files, all clean) — still no
  Node in this environment, so nothing here has actually been compiled or run; treat as unverified
  until `npm install && ng test && ng serve` can. Pure-logic specs
  (`degradation-history.spec.ts`, extended `sort-cars.spec.ts`) are written to the same standard as
  `interpolation.spec.ts`/`geometry.spec.ts` and would run under `ng test` once Node is available.
  Backend side (the `last_lap_is_clean_air` plumbing) *does* run for real here: `test_builder.py`,
  `test_live_router.py` gained passing assertions for it, full suite still 132 passed / 8 skipped /
  5 known hand-traced failures / 11 known collection errors (all pre-existing `f1core` Python-version
  gaps, no new regressions).

### T8 — validation — done
- `tests/replay/test_backtest_m2.py` (new, runs for real on this dev machine — pure NumPy, no
  `f1core`): walk-forward backtest against the real Monza fixture (`tests/fixtures/openf1/
  monza_2025_driver1_stint1_laps.json`, driver 1's 37-lap opening stint) — each lap's prediction
  only ever uses laps seen before it, exactly like the live pipeline would. Reimplements
  `TyreDegEstimator`/`PaceEstimator`/`LapTimePredictor`'s exact algorithms in pure form (`_fit_deg_rate`/
  `_fit_pace`), since driving the real Components still needs Python ≥ 3.11; flagged in the module
  docstring as something that needs updating by hand if `tyre.py`/`pace.py` ever change, with no way
  to enforce that mechanically here.
- **Real, honestly-reported results:**
  - One-lap-ahead prediction error: **prior phase** (laps 3-6, before 5 clean laps accumulate) MAE
    ≈ 0.91 s; **estimated phase** (laps 7-36) MAE ≈ 0.14 s. The gap is the whole point of the
    kind/uncertainty system, and it held up on real data.
  - **Where the model is clearly wrong** (as asked for): the walk-forward degradation-rate fit sits
    at exactly `0.0` (clamped) from lap 7 through lap 25 — the true Monza signal (T2's full-stint
    fit: ≈ +0.028 s/lap) is too weak relative to lap-to-lap noise to detect from a short early-stint
    sample; it only starts climbing once ~19 laps of history exist. A finish-time prediction made
    from lap 20's data (predicting the cumulative time through lap 36) consequently comes out
    **3.2% low** (2898.9 s predicted vs. 2994.6 s actual) — the model was still assuming
    near-zero wear at exactly the point a user mid-race would most want a finish-time estimate.
    Recorded as a known M2 v1 limitation, not hidden; a mined/circuit-level prior for `k1` (already
    on the Decisions table as future work, research.md §3.2) would fix this by giving the fit a
    running start instead of assuming zero.
  - **Madring (cold start):** genuinely no real lap data exists (it hasn't raced) — see
    `config/circuits/madring.yaml`'s already-null priors. Backtesting prediction *accuracy* there is
    impossible by definition; what the two `test_cold_start_*` tests validate instead is that the
    system doesn't pretend otherwise — the config has every degradation-relevant field left `null`,
    and the fallback path with zero laps of history resolves to exactly the documented generic
    prior, never an attempted fit on nothing.
- Also promoted `tyre.py`'s/`pace.py`'s fallback/threshold constants (`GENERIC_PRIOR_K1_S_PER_LAP`,
  `MIN_CLEAN_LAPS_FOR_ESTIMATE` ×2, uncertainty levels) into `degradation_math.py`/`pace_math.py` —
  they're needed by this backtest too, and duplicating magic numbers between the pure module and
  its Component wrapper (or worse, hand-copying them into the test) would violate CLAUDE.md rule 1.
  `tyre.py`/`pace.py` now import them from there; no behaviour change.
- Full suite: 139 passed, 8 skipped (no local DB/Redis), 5 known hand-traced failures + 13 known
  collection errors (all pre-existing `f1core` Python-version gaps — 2 new ones from `tests/
  property/`, swept for the first time this session, same cause), no new regressions.

### T9 — docs and backlog — done
- `README.md`: milestone banner now reads M1 + M2 code-complete; status table gains rows for the
  new `f1models`/`f1engine` packages and updates `f1core`/`f1state`/`f1api` for what M2 added to
  each; a new "M2's honest validation" paragraph surfaces T8's real backtest numbers (including the
  3.2% mid-stint underestimate) at the top level, not just buried in the plan doc; repository layout
  section updated (`f1models`/`f1engine` are no longer placeholders; `f1calib` still is).
- `docs/backlog.md`: new "Deferred during Phase 2" section — Kalman filter refitting, estimating a
  real degradation cliff slope (with the T8 backtest finding as the concrete motivation), per-circuit
  fuel-effect calibration, driver-skill priors from `docs/f1-driver-ratings.md`, real uncertainty
  propagation (currently a simple additive upper bound), the frontend's client-side-only lap history
  (no backend endpoint for full race history), and `api-types.ts` drifting further from
  `f1api/schemas.py`. Collected from every `docs/backlog.md` cross-reference actually left in M2's
  code/docstrings (grepped for, not reconstructed from memory), not invented fresh.
- M2 ("Predict pace") is now fully done: T1–T9 all complete. Next milestone is M3 (pit-stop
  prediction) per `docs/f1-strategy-foundation.md` §9 — not started, per CLAUDE.md rule 12.

## Out of scope for Phase 2
Pit-stop prediction (M3), Monte Carlo / position odds / strategy (M4), SC/VSC/DNF/weather event
modelling (M5), live OpenF1 (M6). No new fixture races. No changes to M1's observed-data pipeline
beyond the additive `CarState` fields in T5.

## Risks to watch
- Confounded fits: fuel burn and track evolution can make a naive `lap_time ~ tyre_age` slope
  negative (research.md §3.6/§12 #1). The fuel correction in T2 exists specifically to guard
  against this; a property test should assert the fitted `k1` never comes out negative beyond
  noise.
- Cold-start circuits (Madring) have no compound-specific prior yet — predictions there will
  carry `kind=prior` and wide uncertainty for longer than at Monza. That's correct behaviour, not
  a bug; don't be tempted to narrow it artificially.
- The "no more stops" finish-time assumption will visibly diverge from reality for anyone who
  pits again after predictions start. This is expected and must stay visible in the UI, not
  smoothed over.
