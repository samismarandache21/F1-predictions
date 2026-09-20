# Backlog

Ideas and scope creep deferred during Phase 1 and Phase 2, per CLAUDE.md rule 12 ("don't expand
scope — put ideas here instead"). Nothing here should be built until its milestone (see
`docs/f1-strategy-foundation.md` §9) is reached.

## Deferred during Phase 2 (M2 "Predict pace")

- **Kalman filter for pace/degradation refitting.** design.md/engine-spec.md describe one as a
  later live-refinement; M2 v1 uses a plain refit-on-every-new-lap instead (fully deterministic,
  enough to demo P1/P2). Revisit once a live-refinement need actually shows up — see
  `docs/plan/phase-2.md`'s Decisions table ("Fit method").
- **Estimating a real tyre-degradation cliff slope.** M2 v1's fit is linear-only
  (`f1models.degradation_math.fit_linear_degradation`); `car.tyre.deg_cliff_lap` is tracked as a
  fixed prior but never fed into a prediction, because a single stint's laps can't identify a
  3-parameter linear+cliff model reliably (validated live against the real Monza fixture during
  T2 — see that module's docstring). T8's backtest found this is exactly why a mid-stint finish-time
  prediction came out 3.2% low: the fit has no way to anticipate wear it hasn't seen evidence of
  yet. Needs either a cross-stint/mined circuit-level prior for `k1` (research.md §3.2) or enough
  laps in a single stint to identify the cliff directly — whichever a future milestone can supply.
- **Per-circuit fuel-effect calibration.** `FUEL_EFFECT_S_PER_LAP = 0.05` (Pitwall's generic
  default, research.md §3.4/§10.5) is used everywhere; no circuit-specific value exists yet.
- **Driver-skill priors from `docs/f1-driver-ratings.md`.** `car.pace.base_s`'s EWMA currently
  starts every driver from a flat, equal prior (seeded by their own first lap) — no use is made of
  the ratings doc's per-driver metrics to seed a more informed starting pace.
- **Real uncertainty propagation.** `f1engine.predictors`'s `_DEFAULT_UNCERTAINTY_S`/the additive
  `pace.uncertainty + deg_rate.uncertainty` combination is a simple upper bound, not a calibrated
  error-propagation model.
- Frontend `DegradationHistoryTracker` (V4, `web/src/app/degradation-chart/`) accumulates lap
  history purely client-side from WS frames, since the backend has never streamed full lap history
  to the frontend. Switching the followed driver mid-replay only shows history accumulated since
  the page loaded, not the whole race so far — fine for a live companion, but worth a proper
  backend history endpoint if a "show me this driver's whole race" view is ever wanted.
- `web/src/app/core/api-types.ts` has grown further out of sync with `f1api/schemas.py` (M2 added
  six more `CarStateOut` fields by hand) — see the existing `make types` entry below, now more
  pressing.

## Deferred during Phase 1 (M1 "Watch")

- Third fixture race (wet or SC-affected) for T4 — not yet chosen. Candidates should be picked
  from a 2025 or 2026 race with a confirmed SC/VSC/rain period, per `docs/plan/phase-1.md`.
- Live OpenF1 subscription (M6) — costed and paid for only once M1–M5 are demoed.
- Reddit sentiment ingestion for driver ratings (`docs/f1-driver-ratings.md` §4, Tier 3) — lowest
  priority data source; needs its own ToS review before building.
- RL/NN opponent or decision policies (`docs/f1-strategy-research.md` §10.6) — only after the
  deterministic + Monte Carlo engine (M4) is validated.
- GPU/Rust simulator core — only if candidate/run counts in the Monte Carlo engine outgrow NumPy/Numba.
- Multi-user support (auth, per-user sessions) — out of scope for a personal/portfolio project.
- Qualifying and sprint strategy modes.
- Exact 2026 tyre-set allocations, red-flag tyre-change rule wording, and per-circuit SC/VSC rates
  recomputed from race-control data — open questions listed in `docs/f1-strategy-research.md` §16.
- Frontend (T9) shows car numbers, not 3-letter driver codes (VER, HAM): RaceState has no driver
  name/code field, only car number. Would need the same config-lookup pattern used for
  `team`/`team_colour` (`SeasonConfig` already has `.code` per driver) — skipped to avoid a third
  round of touching T6/T8 mid-T9; car numbers are a reasonable primary identifier on their own.
- Explicit "follow driver" dropdown: currently click-a-row-in-the-timing-tower. Works, but a
  dedicated selector (e.g. in the replay controls bar) would be more discoverable.
- Pit lane path rendering on the track map: `f1track.build_circuit_geometry` supports it
  (`pit_lane_samples`), but no fixture with a real in/out-lap trace has been extracted yet, and
  the API/frontend don't surface it. Ghost cars following it is explicitly M4 scope anyway.
- `make types` has never actually been run (no Node in this dev environment) — `web/src/app/core/api-types.ts`
  is a hand-authored stand-in matching `f1api/schemas.py` field-for-field. Delete it and regenerate
  once Node is available; anything reviewing frontend correctness should treat these types as
  unverified against the real OpenAPI schema until then.
