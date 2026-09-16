# Strategy Engine — Detailed Specification (v1)

Companion to `f1-strategy-design.md`, §7. Target standard: something a professional race strategy group would take seriously.

## 1. Design principles

1. **Bring your own data.** Every model sits behind an interface. Public-data models are the default implementation; a team plugs in its own tyre, pace and pit models built on its private telemetry, without touching the engine. This is what makes the engine sellable (§12).
2. **Policies, not plans.** Real strategy is conditional: "Plan A: box lap 24, but box immediately under an SC after lap 18; if #4 pits first, cover." The engine evaluates **closed-loop policies**, not fixed pit laps.
3. **Honest uncertainty.** Sample model-parameter uncertainty per run, not just lap noise. Calibrated probabilities are the product.
4. **Deterministic and reproducible.** Same state, same model version and same seed produce identical output. Every report can be replayed and audited.
5. **Explainable.** Every recommendation comes with the conditions under which it wins or loses.
6. **Fast.** Quick answer in about 1 s, refined answer in about 5 s, on a single workstation.

## 2. Interfaces

```python
class EngineInput:
    state: RaceState                  # from race state service
    models: ModelBundle               # versioned
    overrides: Overrides              # user damage, opponent hints, constraints
    config: EngineConfig              # runs, candidates, objective, seed

class ModelBundle(Protocol):
    pace: PaceModel
    tyre: TyreModel
    overtake: OvertakeModel
    pit: PitModel
    events: EventModel                # SC / VSC / red flag / DNF
    weather: WeatherModel
    opponents: OpponentPolicyModel
    points: PointsTable

class TyreModel(Protocol):
    def sample_params(self, rng, runs, cars, compounds) -> TyreParams: ...
    def lap_delta(self, p: TyreParams, compound, age, track_temp, wetness, push) -> ndarray: ...
```

All model methods are **vectorised**: they take and return arrays shaped `[runs, cars]`. The core loop never calls Python per car.

## 3. Simulation state

Arrays of shape `[R, C]` (R runs, C = 20 cars) unless noted:

| Array | Meaning |
|---|---|
| `cum_time` | Race time since start (s) |
| `laps_done` | Completed laps |
| `order` | Running order (indices into cars) |
| `compound`, `tyre_age` | Current tyre state |
| `compounds_used` | Bitmask for the two-compound rule |
| `stops` | Pit stops made |
| `pace_offset` | Sampled base pace (parameter uncertainty) |
| `tyre_params` | Sampled degradation parameters |
| `damage_pen` | Pace penalty (s/lap) |
| `dirty_air_laps` | Consecutive laps within ~1 s behind (drives thermal degradation) |
| `retired` | Boolean |
| `policy_state` | Per-car policy memory (planned pit lap, committed flags) |
| `track_status` `[R]` | GREEN / VSC / SC / RED |
| `status_laps_left` `[R]` | Remaining laps of the neutralisation |
| `wetness` `[R]` | 0 = dry, 1 = full wet |
| `weather_scenario` `[R]` | Sampled rain onset, intensity and duration |

Run initialisation copies the live `RaceState` into every run, then samples the per-run parameters (pace, tyre, opponent policies, weather scenario).

## 4. The lap step

For each lap from `current_lap + 1` to `total_laps`:

```
1.  events.step(track_status, status_laps_left, rng)       # SC/VSC/red transitions
2.  weather.step(wetness, weather_scenario, lap)
3.  decisions = policies.decide(state)                     # our candidate + opponents
4.  t = natural_lap_time(state)                            # §5
5.  t += pit_cost(decisions, state)                        # §7
6.  apply_neutralisation(t, state)                         # SC/VSC timing, gap compression
7.  resolve_positions(t, state)                            # §6, Numba kernel
8.  dnf = events.sample_dnf(state); maybe_trigger_sc(dnf)
9.  update tyre_age, compounds_used, dirty_air_laps, laps_done
```

After the final lap: finishing order is by `(laps_done desc, cum_time asc)`. Unmet two-compound rules get the regulatory penalty. Apply the points table. Lapped cars finish when the leader takes the flag.

## 5. Lap time model

```
t = base(car) + pace_offset
  + tyre.lap_delta(compound, age, track_temp, wetness, push)
  - fuel_k × laps_done
  + dirty_air(interval_ahead) + thermal_deg(dirty_air_laps)
  + weather_penalty(compound, wetness)
  + damage_pen
  + out_lap_penalty (if pitted last lap)
  + ε,  ε ~ N(0, σ_car)
```

**Pace (`PaceModel`).**
- The prior comes from qualifying and practice long runs, corrected for fuel and tyre.
- In the race, a Kalman filter updates each car's base pace from green, clean-air laps (interval > 2 s, no pit in/out, no SC).
- The posterior mean and variance are sampled once per run. This is what turns pace uncertainty into finishing-position uncertainty.

**Tyres (`TyreModel`).**
```
delta(age) = offset_c + b_c × age + k_c × max(0, age − cliff_c)² , scaled by f(track_temp)
```
- Hierarchical fit: compound → circuit → car, partially pooled, so sparse circuits borrow strength from similar ones.
- In race, our own stints update `b_c` and `cliff_c` live.
- `push` ∈ {manage, normal, push} trades pace for degradation. Policies can set it, for example to extend a stint.

**Dirty air.** Time loss plus extra degradation when running within ~1–1.5 s of the car ahead. Both are fitted from historical follow-versus-clean lap pairs.

## 6. Position resolution (the core of traffic and overtaking)

Numba kernel, parallel over runs:

```
for r in prange(R):
    prev = order[r]                                     # order at start of lap
    for idx in 1..C-1:
        i = prev[idx]; j = car directly ahead on track (not in pit lane, not retired)
        proposed = cum_time[r,i] + t[r,i]
        ahead    = cum_time[r,j] + t[r,j]
        if proposed < ahead + MIN_GAP:                  # i is faster and catches j
            if track_status[r] != GREEN: hold(i, behind j)
            else:
                p = overtake.prob(circuit, pace_delta, tyre_age_delta,
                                  compound_delta, drs=interval<1.0, wetness)
                if rng() < p:  swap; add battle_cost to both
                else:          cum_time[r,i] = ahead + MIN_GAP   # held up
    re-sort order[r] by cum_time
```

**Overtake model.** Logistic regression with a circuit random effect, trained on the `overtake` table:
```
logit p = β0[circuit] + β1·pace_delta + β2·tyre_age_delta + β3·compound_delta + β4·drs + β5·wetness
```
- Also fitted: **battle cost** (time both cars lose while fighting) and **multi-lap attempts**, where the chance of passing grows with consecutive laps of attempts.
- Pit-lane cars are skipped: their rejoin position is resolved from cumulative time, and the rejoin places them into traffic. This is how undercut, overcut and "pitting into traffic" come out of the model without special-casing.
- **Lapping backmarkers** costs a small, sampled time loss for the lapping car (blue-flag delay).

## 7. Pit stops (`PitModel`)

```
pit_cost = lane_loss[circuit] × status_factor(track_status)
         + stationary ~ Mixture(LogNormal(team), p_slow × SlowStop)
         + double_stack_cost (if teammate pitted same lap)
```
- `status_factor`: SC ≈ 0.4–0.5, VSC ≈ 0.6–0.7 (fitted per circuit).
- Red flag: a free tyre change for everyone, and the compound rule counts.
- The next lap gets an out-lap penalty (cold tyres), fitted per compound.

## 8. Race events (`EventModel`)

- **Track status** is a per-circuit Markov chain.
  - GREEN → SC/VSC hazard is higher on lap 1, in the wet, and right after a DNF or incident.
  - SC and VSC durations are sampled from their historical distributions.
  - During SC, the field compresses to a minimum gap and overtaking is disabled. At the restart, extra overtaking chance is given for a lap.
- **DNF.** Per-team reliability hazard plus incident hazard, which scales with battle count and wetness. A DNF can trigger SC or VSC, with probability depending on track location (circuit prior).
- **Damage.** A small chance after a failed battle; it draws a penalty distribution. Policies may choose a repair stop.

## 9. Weather (`WeatherModel`)

- At the start of each run, sample a **rain scenario** from the forecast: onset lap, peak intensity, duration, dry-out rate. Use forecast ensembles when available.
- `wetness` evolves from the scenario; the track dries at a rate depending on intensity, temperature and cars running.
- **Crossover curves**: lap-time penalty per compound as a function of wetness, fitted from historical mixed races. This defines when slicks-to-inters and inters-to-slicks switches pay off.

## 10. Policies

### 10.1 Our candidates
A candidate is a parameterised policy:

```yaml
id: planA_L24_H
pit_plan:        [{ window: [23, 25], compound: HARD }]
sc_rule:         { pit_if_sc: true, min_tyre_age: 8, max_laps_to_plan: 12, compound: HARD }
vsc_rule:        { pit_if_vsc: true, min_tyre_age: 12 }
cover_rule:      { rivals: [4, 81], if_gap_lt: 2.5, react_within: 1 }
rain_rule:       { to_inter_at_wetness: 0.35, to_slick_at_wetness: 0.15 }
push_profile:    { stint1: manage, stint2: normal }
```

**Candidate generation:**
1. Enumerate a parameter grid: window × compound × stop count × SC/VSC rule variants × cover on/off.
2. Prune with the deterministic dynamic-programming optimizer (clean-air race time). Keep any candidate within X seconds of the best, plus all "event-response" variants.
3. Typical result: 30–80 candidates.

### 10.2 Opponent model
Every opponent gets a policy of the same form, **sampled per run** from `OpponentPolicyModel`:
- **Prior:** pit window centred on its own tyre optimum (from its tyre state), plus team tendencies learned from history (aggressive undercut, SC response rate, stop-count preference).
- **Bayesian update during the race:** if a car stays out past its expected window, shift its distribution later and raise its "going long / one-stop" probability.
- **Reactive rules:** cover the car ahead or behind; pit under SC if the tyre age exceeds a threshold; react to our stop.
- **User hints** (e.g. "Ferrari will two-stop") override the prior.

Opponents react to what we do in each run, so our pit stop can trigger their cover. The simulation is interactive, not a replay of fixed opponent plans.

## 11. Search, scoring, statistics

### 11.1 Successive halving (best-arm identification)
```
round 1: all candidates × 200 runs   → keep best 50%
round 2: survivors × 400 runs        → keep best 50%
round 3: survivors × 1,000 runs
final:   top 5 × 4,000 runs          → report
```
- Round 1 results are pushed immediately as the "quick" report.
- **Common random numbers:** run `r` uses the same seeds (SC timing, weather, opponent draws) for every candidate. Comparisons are therefore **paired**, which dramatically reduces the runs needed to separate candidates.

### 11.2 Metrics per candidate
- Position histogram → P(P1), P(top 3), P(top 5), P(top 10), P(DNF)
- **E[points]**, with a standard error from the paired runs
- E[position], and the 10th/90th percentiles of position
- Paired difference versus the best: mean ΔE[points] and P(candidate beats best)

### 11.3 Objectives (user-selectable)
- `max_expected_points` (default)
- `max_prob(top_k)`, e.g. go for the podium when the championship situation demands it
- `championship`: maximise the expected **points differential against named rivals**
- A risk-averse variant: mean minus λ × the lower-tail conditional value at risk (CVaR) of points

### 11.4 Stopping rule
The recommendation is "confident" when P(best beats runner-up) > 0.9. Otherwise the UI shows the choice as a **toss-up**, with the deciding factors.

## 12. Explainability

For every run, log compact tags: SC occurred (and lap), rain onset, undercut attempted and succeeded, positions gained or lost in pit cycle, laps held up, battle count.

The engine then computes conditional statistics and turns the largest effects into insights:
- "Plan A wins in 71% of runs; loses mainly when SC occurs after lap 40 (P = 0.22)."
- "Undercut on #4 succeeds in 64% of runs; needs out-lap within 0.8 s of model."
- "Main uncertainty driver: our hard-tyre degradation (sensitivity 1.9 pts per 0.02 s/lap)."

**Sensitivity analysis.** Re-run the top candidates with one model parameter perturbed at a time, using common random numbers. This ranks which assumptions matter, which tells the strategist what to watch.

## 13. Performance

| Item | Estimate |
|---|---|
| Car-lap steps per full refine | ~40 candidates × ~1,000 avg runs × 20 cars × 40 laps ≈ 32M |
| Numba throughput (parallel, 8–16 cores) | tens of millions of car-lap steps per second |
| Refined report | target < 5 s |
| Quick report | 40 × 200 runs, target < 1 s |

Other measures:
- **Pre-sampled random tensors** per report make seeds reproducible and cheap.
- **Cancellation:** the engine checks `state_version` between rounds and aborts if a newer state has arrived.
- If a GPU becomes necessary, the kernel ports to CuPy or JAX. The interfaces stay the same.

## 14. Output

```json
{
  "state_version": "L23.E412", "model_version": "2026.18-bahrain-v3",
  "seed": 918273, "quality": "refined", "runs": 4000,
  "objective": "max_expected_points",
  "recommendation": {
    "id": "planA_L24_H", "summary": "Box lap 24 for Hards; box early under SC after lap 18",
    "expected_points": 11.2, "points_se": 0.08,
    "expected_position": 4.3, "p10_p90": [2, 7],
    "probs": { "p1": 0.04, "top3": 0.31, "top5": 0.80, "top10": 0.97, "dnf": 0.03 },
    "position_hist": [0.04,0.12,0.15,0.27,0.22,0.10,0.05,0.03,0.01,0.01],
    "p_beats_runner_up": 0.93,
    "insights": ["..."],
    "sensitivities": [{ "param": "tyre.b_HARD.our_car", "pts_per_unit": -1.9 }]
  },
  "alternatives": [ ... ],
  "confidence": "confident"
}
```

## 15. Testing and validation

**Property and physics tests:**
- Equal cars on a circuit with β0 → −∞ never pass each other.
- A car 1 s/lap faster passes within a few laps on an easy circuit.
- The undercut gain grows with the tyre-age delta and shrinks with pit-loss variance.
- An SC reduces the pit-stop cost and compresses gaps.
- Two-compound rule enforcement and penalties work.

**Determinism.** Identical input produces byte-identical output.

**Backtests** (replay, 2023–2025, every lap):
- Brier score and reliability curves for P(top k)
- Mean absolute error of predicted finishing position, per lap into the race
- **Decision quality:** the counterfactual E[points] of our recommendation versus the team's actual call, under the same model. Report this carefully, since the counterfactual is model-dependent.

**Benchmark suite** for the latency budget.

## 16. Build order

1. Deterministic single-car kernel with tyres, fuel and pit stops (port of the prototype) + tests
2. Full-field kernel with position resolution and a fixed overtake probability
3. Fitted overtake, pit and tyre models from DB data
4. Parameter-uncertainty sampling + position distributions + calibration backtest
5. Policies (SC/VSC/cover rules), opponent model
6. Successive halving + common random numbers + metrics + objectives
7. Events (SC, VSC, red flag, DNF), weather scenarios, damage
8. Explainability + sensitivity analysis
