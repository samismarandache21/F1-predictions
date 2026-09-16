# F1 Strategy — Driver & Circuit Intelligence (v1)

Snapshot date: **16 Sep 2026**, after round 14 (Spanish GP, Madring) of 23.

Purpose: define **what we know and measure about each driver and circuit**, so the models get good priors and the app can explain *why* a result happened: driver, strategy, car or luck.

> **Important.** The numbers below are a baseline from published race results. Finishing positions mix driver skill, car performance, strategy, reliability and luck. The real metrics (§5) must be computed from lap-level data by our pipeline. Treat everything here as a **starting prior and a test fixture**, not as a verdict on any driver.

---

## 1. 2026 season context

| Fact | Model impact |
|---|---|
| 11 teams, 22 cars (Cadillac new) | Grid size from config |
| DRS replaced by Overtake Mode (extra electrical power within 1 s at a detection point) plus Boost Mode and active aero | New overtaking features; 2023–25 overtaking stats only partially transferable |
| Bahrain and Saudi Arabia cancelled; Bahrain GP relocated to **Sepang (Malaysia)**, 2–4 Oct → 23 rounds | Sepang has **no modern telemetry** (last F1 race 2017): full cold start |
| **Madring** (Madrid) new in 2026; **Zandvoort's final race** was 2026 | Madring has one race of data |
| Hadjar (Red Bull) injured from round 12 → Lawson moved to Red Bull, Tsunoda into Racing Bulls | **Driver–car assignment changes mid-season.** Teammate comparisons must be per-race, not per-season |
| Points: 25-18-15-12-10-8-6-4-2-1, no fastest-lap point | `config/seasons/2026.yaml` |

---

## 2. Calendar

| Rd | Event | Circuit | Type | Status | Data available |
|---|---|---|---|---|---|
| 1 | Australia | Albert Park | Street/park | Done | 2023+ |
| 2 | China (sprint) | Shanghai | Permanent | Done | 2024+ |
| 3 | Japan | Suzuka | Permanent | Done | 2023+ |
| 4 | Miami (sprint) | Miami Autodrome | Temporary | Done | 2023+ |
| 5 | Canada (sprint) | Gilles Villeneuve | Semi-permanent | Done | 2023+ |
| 6 | Monaco | Monte Carlo | Street | Done | 2023+ |
| 7 | Barcelona-Catalunya | Catalunya | Permanent | Done | 2023+ |
| 8 | Austria | Red Bull Ring | Permanent | Done | 2023+ |
| 9 | Britain (sprint) | Silverstone | Permanent | Done | 2023+ |
| 10 | Belgium | Spa-Francorchamps | Permanent | Done | 2023+ |
| 11 | Hungary | Hungaroring | Permanent | Done | 2023+ |
| 12 | Netherlands (sprint) | Zandvoort | Permanent | Done (final edition) | 2023+ |
| 13 | Italy | Monza | Permanent | Done | 2023+ |
| 14 | Spain | **Madring** | Street/hybrid | Done | **2026 only** |
| 15 | Azerbaijan | Baku | Street | Next (26–27 Sep; sources differ on day) | 2023+ |
| 16 | Bahrain GP **in Malaysia** | **Sepang** | Permanent | 2–4 Oct | **None (modern era)** |
| 17 | Singapore (sprint) | Marina Bay | Street | 11 Oct | 2023+ |
| 18 | United States | COTA | Permanent | Upcoming | 2023+ |
| 19 | Mexico City | Hermanos Rodríguez | Permanent (high altitude) | Upcoming | 2023+ |
| 20 | São Paulo | Interlagos | Permanent | Upcoming | 2023+ |
| 21 | Las Vegas | Las Vegas Strip | Street | Upcoming | 2023+ |
| 22 | Qatar | Lusail | Permanent | Upcoming | 2023+ |
| 23 | Abu Dhabi | Yas Marina | Permanent | Upcoming | 2023+ |

Sprint weekends are listed as reported; verify them against the official schedule when writing the config.

**Cold-start circuits** (Madring, Sepang) use:
- circuit-type priors (street vs permanent, high vs low degradation);
- the first practice session's data, which is enough to build the track geometry and a first degradation estimate;
- heavier uncertainty in all predictions.

---

## 3. Grid and driver context

Titles and debut years are pre-2026 career facts. Standings are after round 14.

| Team | Driver | F1 debut | Titles | 2026 pos | Pts |
|---|---|---|---|---|---|
| Mercedes | Kimi Antonelli | 2025 | 0 | 1 | 292 |
| Mercedes | George Russell | 2019 | 0 | 2 | 211 |
| Ferrari | Lewis Hamilton | 2007 | 7 | 3 | 191 |
| Ferrari | Charles Leclerc | 2018 | 0 | 5 | 167 |
| McLaren | Lando Norris | 2019 | 1 (2025) | 4 | 186 |
| McLaren | Oscar Piastri | 2023 | 0 | 7 | 120 |
| Red Bull | Max Verstappen | 2015 | 4 | 6 | 145 |
| Red Bull | Isack Hadjar (injured from Rd 12) | 2025 | 0 | 8 | 71 |
| Red Bull → *from Rd 12* | Liam Lawson (Racing Bulls Rd 1–11) | 2023 | 0 | 9 | 59 |
| Racing Bulls | Arvid Lindblad (rookie) | 2026 | 0 | 11 | 31 |
| Racing Bulls → *from Rd 12* | Yuki Tsunoda (reserve) | 2021 | 0 | 20 | 1 |
| Alpine | Pierre Gasly | 2017 | 0 | 10 | 41 |
| Alpine | Franco Colapinto | 2024 | 0 | 12 | 27 |
| Haas | Oliver Bearman | 2024 | 0 | 13 | 18 |
| Haas | Esteban Ocon | 2016 | 0 | 18 | 3 |
| Audi | Gabriel Bortoleto | 2025 | 0 | 14 | 10 |
| Audi | Nico Hülkenberg | 2010 | 0 | 15 | 7 |
| Williams | Carlos Sainz | 2015 | 0 | 16 | 6 |
| Williams | Alex Albon | 2019 | 0 | 17 | 5 |
| Aston Martin | Fernando Alonso | 2001 | 2 | 19 | 3 |
| Aston Martin | Lance Stroll | 2017 | 0 | 21 | 0 |
| Cadillac | Valtteri Bottas | 2013 | 0 | 22 | 0 |
| Cadillac | Sergio Pérez | 2011 | 0 | — | *verify* |

**Constructors:** Mercedes leads with 503 points, 145 ahead of Ferrari; Mercedes has 10 wins.

**Experience notes relevant to modeling:**
- *Returning after a year out:* Bottas and Pérez did not race in 2025.
- *Low recent track experience:* Tsunoda, whose first 2026 race was round 12; Lindblad, a rookie with F2 track experience only; Antonelli, Bortoleto and Hadjar, each in their second season.
- *Everyone* is new to the 2026 cars. Experience still matters (circuit knowledge, racecraft, tyre feel) but transfers imperfectly.

---

## 4. 2026 results snapshot (rounds 1–14)

Derived from the published round-by-round standings table (race classifications). Sprint results are not included.

"Avg fin" is the average classified finishing position. DNS entries are excluded from starts.

| Driver | Starts | Classified | DNF | Avg fin | Best | Top-10 |
|---|---|---|---|---|---|---|
| Antonelli | 14 | 14 | 0 | 3.5 | 1 | 12 |
| Russell | 14 | 12 | 2 | 3.8 | 1 | 11 |
| Norris | 13 | 11 | 2 | 3.8 | 1 | 11 |
| Hamilton | 14 | 13 | 1 | 3.9 | 1 | 13 |
| Leclerc | 14 | 12 | 2 | 5.1 | 1 | 11 |
| Verstappen | 14 | 11 | 3 | 5.3 | 2 | 10 |
| Piastri | 12 | 11 | 1 | 5.8 | 2 | 9 |
| Hadjar | 11 | 9 | 2 | 6.3 | 3 | 8 |
| Lawson | 14 | 13 | 1 | 8.5 | 5 | 10 |
| Gasly | 14 | 13 | 1 | 9.2 | 6 | 9 |
| Lindblad | 13 | 13 | 0 | 9.8 | 6 | 9 |
| Colapinto | 14 | 14 | 0 | 11.1 | 6 | 8 |
| Bortoleto | 13 | 13 | 0 | 11.1 | 8 | 3 |
| Hülkenberg | 13 | 10 | 3 | 11.1 | 8 | 3 |
| Tsunoda | 3 | 3 | 0 | 11.7 | 10 | 1 |
| Bearman | 14 | 11 | 3 | 12.7 | 5 | 3 |
| Ocon | 14 | 13 | 1 | 13.3 | 9 | 2 |
| Sainz | 14 | 12 | 2 | 13.8 | 9 | 3 |
| Albon | 13 | 10 | 3 | 14.8 | 8 | 2 |
| Alonso | 14 | 9 | 5 | 15.3 | 9 | 2 |
| Stroll | 14 | 4 | 10 | 16.0 | 13 | 0 |
| Bottas / Pérez | — | — | — | — | — | — |

Bottas and Pérez: fill in from the ingested data.

### Teammate head-to-head (races where both were classified)

| Pairing | Rounds | H2H |
|---|---|---|
| Antonelli vs Russell | 1–14 | 8–4 |
| Hamilton vs Leclerc | 1–14 | 6–5 |
| Norris vs Piastri | 1–14 | 6–3 |
| Verstappen vs Hadjar | 1–11 | 6–1 |
| Verstappen vs Lawson | 12–14 | 2–0 |
| Lawson vs Lindblad | 1–11 | 7–2 |
| Lindblad vs Tsunoda | 12–14 | 2–1 |
| Gasly vs Colapinto | 1–14 | 9–4 |
| Bearman vs Ocon | 1–14 | 8–3 |
| Hülkenberg vs Bortoleto | 1–14 | 5–4 |
| Sainz vs Albon | 1–14 | 4–4 |
| Alonso vs Stroll | 1–14 | 2–1 |

### What this snapshot can and cannot tell us

- **Reliability vs driver error is not visible here.** Stroll has 10 DNFs in 14 starts, and Alonso has 5 in the same car. That points toward a car or reliability problem, but only the classification reason and race control messages can confirm it.
- **Outliers are case studies for attribution (§6).** Examples:
  - Antonelli: P16 (Barcelona) and P15 (Britain) in an otherwise near-perfect season.
  - Verstappen: P20 (Britain).
  - Leclerc: P15 (Barcelona).

  Each could be a driver error, a strategy error, an incident or a car problem. Our tooling should be able to tell which.
- **Teammate head-to-heads have tiny samples** and ignore how the pair got there. They are used only as weak priors.

---

## 5. Metric catalogue

All metrics are computed per **driver × race** from lap-level data, then aggregated with **shrinkage** (§7).

### A. Pace
| Metric | Definition | Source |
|---|---|---|
| `quali_gap_tm` | (driver best Q time − teammate best Q time) / teammate time, % (same Q segment only) | OpenF1/FastF1 laps |
| `race_pace_tm` | Median of fuel- and tyre-corrected clean-air lap times vs teammate, same compound and stint phase | laps + stints + intervals |
| `race_pace_field` | Same correction, vs field median | same |
| `consistency` | σ of corrected clean-air lap times within a stint | same |

"Clean air" means interval to the car ahead > 2 s, not an in/out lap, and no SC/VSC or yellow in that lap.

### B. Tyre management
| Metric | Definition |
|---|---|
| `deg_rate` | Slope of corrected lap time vs tyre age per stint (s/lap) |
| `deg_rate_tm` | `deg_rate` − teammate's, same compound, overlapping laps (the **driver effect**, since the car is the same) |
| `stint_extension` | Stint length vs the field median for the same compound and race |
| `end_stint_drop` | Pace of the last 3 laps vs the stint median |
| `cliff_lap` | First tyre age where the residual jumps above threshold |

**Decomposition (hierarchical model):**
```
deg_rate = circuit×compound effect + team (car) effect + driver effect + noise
```
The **team effect** comes from both drivers pooled. The **driver effect** is the residual versus the teammate. This is how teammates reveal the car, and how skill in tyre management carries over to predictions.

### C. Racecraft
| Metric | Definition |
|---|---|
| `lap1_gain` | Grid position − position at end of lap 1 |
| `overtakes_made` / `overtakes_lost` | On-track position changes, excluding pit cycles, retirements and SC restarts (tagged separately) |
| `attack_conversion` | Of sequences where the driver spent ≥2 laps within 1 s of the car ahead (Overtake Mode range), the share ending in a pass within 5 laps |
| `defence_hold` | Mirror of `attack_conversion` for the car behind |
| `restart_gain` | Positions gained in the 2 laps after SC/VSC restarts |
| `pace_adjusted_gain` | Actual positions gained − gains expected from the pace advantage (from the overtake model) |

### D. Reliability and incidents
| Metric | Definition | Source |
|---|---|---|
| `dnf_cause` | Mechanical / accident / collision / other | Classification status + race control |
| `penalties` | Time or grid penalties, with the reason | Race control |
| `incidents_at_fault` | Collisions or unsafe releases where the driver was penalised | Race control |
| `track_limits` | Deleted laps and warnings | Race control |
| `offs` | Spins and off-track moments (race control messages + lap time spikes) | Race control + laps |

### E. Circuit affinity and experience
| Metric | Definition |
|---|---|
| `starts_at_circuit` | F1 race starts at this circuit (Jolpica) |
| `laps_at_circuit_era` | Laps driven there in 2026 machinery |
| `circuit_affinity` | Driver's `race_pace_tm` at this circuit − their season average, shrunk heavily toward 0 |
| `type_affinity` | The same, pooled over circuit clusters: street / high-speed / high-degradation / stop-start |
| `wet_pace_tm` | `race_pace_tm` on intermediate or wet laps only |

### F. Team operations
| Metric | Definition |
|---|---|
| `pit_stationary_median` | Stationary time median per team |
| `slow_stop_rate` | Share of stops above the team median plus a threshold |
| `strategy_reactivity` | Share of rivals' undercut attempts covered within 1 lap |
| `sc_pit_rate` | Share of SC/VSC periods in which the team pitted an eligible car |

---

## 6. Attribution: driver error vs strategy error vs car vs luck

For each driver in each race:

```
Δ = actual_finish − expected_finish(grid, pace model)
```

Then decompose Δ into components that sum to it:

| Component | How it is measured | Attributed to |
|---|---|---|
| Start / lap 1 | `lap1_gain` vs expected from grid slot | Driver (+ luck if lap-1 incident not at fault) |
| Pace deficit | Race pace vs model expectation for the car, using teammate as reference | Driver (if teammate is fine) or car/setup (if both are off) |
| Pit cycles | Positions lost or gained across each pit window vs the counterfactual best timing from the strategy engine | **Strategy** (+ pit crew for slow stops) |
| On-track battles | `pace_adjusted_gain` | Driver racecraft |
| SC/VSC timing | Gain or loss from when neutralisations fell relative to stops, vs expectation | Luck, unless the team failed to react (then strategy) |
| Incidents / penalties | At-fault vs not at fault, from race control | Driver or luck |
| DNF / technical | Classification cause | Car/reliability, or driver if accident at fault |

**Staging:**
- **v1 (heuristic):** rule-based decomposition from lap data and race control messages. Available from milestone M2.
- **v2 (counterfactual):** the Monte Carlo engine re-simulates the race with the optimal strategy and a "clean" driver. The strategy error is E[pos | actual plan] − E[pos | best plan]. Available from M4.

---

## 7. Making metrics trustworthy

- **Shrinkage.** Every per-driver metric uses empirical Bayes: `estimate = w·driver_mean + (1−w)·prior`, where `w = n/(n+k)`. Four races is not a trait.
- **Priors:**
  - team mean for the car;
  - career data from 2023–2025, down-weighted, for driver traits such as tyre management and racecraft (which transfer across rule sets better than car data does);
  - F2 data for rookies (Lindblad).
- **Mid-season changes.** Metrics are keyed by `(driver, team, race)`, so Lawson's Red Bull races don't pollute his Racing Bulls baseline.
- **Recency weighting.** Exponential decay, so upgrades and learning show up.
- **Confidence is always shown** next to every metric in the UI.

---

## 8. How the "follow a driver" flow uses this

1. **Pick a driver.** The app pins them and their **teammate**, who has the same car and is the best reference for car-level degradation and pace.
2. **Other 20 cars.** Public timing includes every car's lap times, so their degradation **is measured directly** during the race, not guessed. What we can't see is their fuel load, tyre temperatures and whether they're managing pace. Driver metrics fill those gaps:
   - *Early in a stint*, with few laps, the tyre-management prior drives the prediction.
   - *As laps accumulate*, the observed degradation takes over (Bayesian update).
   - *For future stints* on a compound a driver hasn't used yet today, the prior combines the team effect (from the teammate, if they've run it) with the driver effect.
3. **Racecraft and overtake metrics** set the pass probabilities between specific pairs of cars in the simulator.
4. **After the race**, the attribution report explains the result for the followed driver and their teammate.

---

## 9. Circuit profile (config fields)

```yaml
id: sepang
name: Sepang International Circuit
type: permanent            # street | permanent | hybrid
length_m: 5543
laps: TBD
pit_lane_loss_s: {prior: TBD, sd: TBD}
overtake_difficulty: {prior: TBD, source: prior}   # computed from data where available
sc_hazard_per_lap: {prior: TBD}
deg_class: {prior: high}   # tropical heat; confirm from FP data
weather: {rain_risk: high, forecast_source: open-meteo}
cluster: high_deg
data_since: 2026           # no modern-era telemetry
```

Priors are replaced by computed values as soon as data exists. Every field records whether it is `prior` or `estimated`.

---

## 10. Pipeline for this document

Job: `f1calib.driver_metrics` (runs after each race).
1. Ingest the race (laps, stints, pit stops, intervals, race control, weather, results).
2. Compute the §5 metrics per driver × race.
3. Update the shrunk aggregates and the hierarchical degradation model.
4. Run the attribution report (§6).
5. Regenerate this document's tables automatically (`docs/generated/driver-intel.md`), so it never goes stale.

---

## Sources (for the facts in §1–4)
- Standings and round-by-round classifications: f1-fansite.com 2026 standings (after round 14)
- Hadjar injury and driver swaps: Formula1.com, RaceFans, Motorsport.com (Aug 2026)
- Sepang hosting the Bahrain GP: Formula1.com, Sky Sports (Jul 2026)
- 2026 regulations (Overtake Mode, active aero, 22-car grid): Sky Sports, The National, GrandPrix247
