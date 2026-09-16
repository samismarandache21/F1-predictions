# F1 Strategy — Driver Ratings: True Potential, Racecraft & Reputation (v1)

Companion to `f1-driver-circuit-intel.md`. Snapshot: 16 Sep 2026.

Goal: estimate **how good each driver really is**, separated from the car, across **several seasons**, and on the same scale for all 22 drivers. That means:
- one-lap pace (qualifying);
- race pace and tyre management;
- how hard they are to pass, and how well they pass others;
- driving standards: fair versus overly aggressive, using objective records plus expert and fan opinion (weighted).

---

## 1. Core idea: teammates are the only fair comparison, so connect them

Two drivers in different cars can't be compared directly. Teammates share a car, so the **teammate gap** isolates the driver.

Drivers change teams over the years, which links the teammate pairs into a **network**. For example: Verstappen–Tsunoda (Red Bull), Tsunoda–Hadjar (Racing Bulls), Hadjar–Lawson (Racing Bulls), Lawson–Verstappen (Red Bull), and further links back through Pérez, Ricciardo, Sainz, Norris and others.

Solving the whole network at once puts every driver on **one scale**.

### Worked example: 2025 Red Bull family (qualifying, median gaps)

Edges from The Race's final 2025 qualifying comparisons (median gap, number of sessions):

| Edge (same car) | Median gap | n |
|---|---|---|
| Verstappen ahead of Tsunoda | 0.547 s | 27 |
| Verstappen ahead of Lawson | 0.813 s | 3 |
| Hadjar ahead of Lawson | 0.206 s | 27 |
| Tsunoda ahead of Hadjar | 0.197 s | 3 |

These four edges form a loop, and the loop doesn't close. Via Tsunoda, Hadjar is 0.744 s off Verstappen; via Lawson, he is 0.607 s off. The 0.137 s mismatch comes from small samples (3 sessions) and different circuits.

A weighted least-squares fit resolves it. Deficit to Verstappen: **Tsunoda 0.54 s, Hadjar 0.68 s, Lawson 0.88 s**. The error is pushed onto the low-sample edges.

Our real model does this for **all drivers and all seasons at once**, in % gap rather than seconds, with uncertainty on every estimate.

### Model

```
gap_pct(i, j, session) = skill_q[i, season] − skill_q[j, season] + noise
skill_q[i, season]     = skill_q[i, season−1] + drift       # skill evolves; young drivers improve
noise ~ Student-t                                          # robust to crashes/traffic outliers
```

- **Data:** 2018–2026 via FastF1/Jolpica. The network needs several years to be connected; 2026 and 2025 are weighted highest.
- **Exclusions:** wet sessions (modelled as a separate `wet_skill`), laps affected by mechanical issues or yellow flags, and gaps above 2 % (flagged, not silently dropped).
- **Output:** each driver's qualifying pace relative to the grid, with a credible interval ("true one-lap potential"), plus a trend line over time.

The same network method is applied to **race pace** (fuel- and tyre-corrected clean-air laps) and to **tyre degradation** (the driver effect in the degradation model).

---

## 2. Qualifying: data we already have

### 2025 final (The Race: GP + sprint qualifying; median gap, where both drivers ran the same segment)

| Pair | H2H | Median gap |
|---|---|---|
| Norris vs Piastri | 15–15 | Norris +0.008 s |
| Leclerc vs Hamilton | 23–7 | Leclerc +0.190 s |
| Verstappen vs Tsunoda | 26–1 | Verstappen +0.547 s |
| Verstappen vs Lawson | 3–0 | Verstappen +0.813 s |
| Russell vs Antonelli | 25–5 | Russell +0.350 s |
| Alonso vs Stroll | 29–1 | Alonso +0.374 s |
| Gasly vs Colapinto | 17–5 | Gasly +0.253 s |
| Gasly vs Doohan | 6–2 | Gasly +0.460 s |
| Bearman vs Ocon | 17–12 | Bearman +0.159 s |
| Hadjar vs Lawson | 21–6 | Hadjar +0.206 s |
| Tsunoda vs Hadjar | 2–1 | Tsunoda +0.197 s |
| Sainz vs Albon | 17–12 | Sainz +0.085 s |
| Bortoleto vs Hülkenberg | 15–14 | Bortoleto +0.063 s (median; the average favours Hülkenberg) |

### 2024 (head-to-head only; gaps to be computed)

| Pair | Result |
|---|---|
| Russell vs Hamilton | Russell 19–5 |
| Norris vs Piastri | Norris 21–3 |
| Hülkenberg vs Magnussen | Hülkenberg 16–6 |
| Bottas vs Zhou | Bottas 21–3 |
| Leclerc vs Sainz | Leclerc ahead (score to compute) |
| Albon vs Colapinto, Bearman stints, and others | To compute |

The 2023 Albon vs Sargeant pairing was 22–0.

### 2026 so far (PlanetF1, GP qualifying)

| Pair | Result |
|---|---|
| Antonelli vs Russell | 8–6 |
| Gasly vs Colapinto | 11–3 (Colapinto has narrowed the average gap) |
| Bottas vs Pérez | 7–7 |
| Hülkenberg vs Bortoleto | Hülkenberg led early; Bortoleto has since recovered |

### What this already suggests (hypotheses for the model to test)
- **Antonelli's jump.** He lost the 2025 qualifying head-to-head 5–25 to Russell, and leads 8–6 in 2026. This is either genuine growth or a car that suits him better. The drift term in the model captures this.
- **Hamilton's decline is not a single-car story.** He was beaten clearly by Russell (2024) and by Leclerc (2025) in two different cars, which makes it a stronger signal.
- **Norris and Piastri are almost equal** over one lap in 2025, after Norris dominated in 2024 (21–3). Piastri improved.
- **Midfield pairs are within 0.1 s** (Sainz/Albon, Bortoleto/Hülkenberg), so ranking them needs the network, not just head-to-heads.

---

## 3. Overtaking and being overtaken

### Definitions matter

Published 2025 overtake counts disagree a lot:
- One count has Bearman top with 128 overtakes, followed by Albon and Stroll, with the McLarens and Alpines lowest.
- An independent count of on-track passes only (excluding lap-1 and pit-cycle changes) puts Hamilton top with 52. By that count, Bearman made 2.14× as many passes as teammate Ocon from almost the same average grid slot, and there was essentially **no correlation between grid position and passes per race**.

**Lesson:** raw counts mostly measure opportunity and definition. We define our own:

| Metric | Definition |
|---|---|
| `attack_opps` | Laps spent within 1.0 s of the car ahead at the Overtake Mode detection point (2026), or in DRS range (≤2025) |
| `pass_rate` | On-track passes ÷ `attack_opps` |
| `defend_opps` | Laps with a car within 1.0 s behind |
| `hold_rate` | 1 − (on-track passes conceded ÷ `defend_opps`) |
| `lap1_net` | Positions gained on lap 1 vs grid |
| `restart_net` | Positions gained within 2 laps of an SC/VSC restart |

Excluded from on-track passes: pit-cycle swaps, retirements, blue-flag moves, team orders (detected from radio and race control where possible).

### Pairwise model (this gives "relations between all drivers")

```
P(pass | attacker a, defender d) = σ( attack[a] − defend[d]
                                      + β_pace·pace_delta + β_tyre·tyre_age_delta
                                      + β_circuit[c] + β_mode·overtake_mode + β_era[e] )
```

- `attack[a]` and `defend[d]` are **driver skills**, estimated across every battle in every season.
- Because pace and tyre differences are controlled for, "Bearman passes a lot" becomes "Bearman passes more *than expected given his car advantage*."
- These parameters feed straight into the race simulator's overtaking step.

---

## 4. Driving standards and reputation

Reputation is split into three evidence tiers, weighted by reliability.

### Tier 1: Official record (strongest, objective)

- **Super licence penalty points** (rolling 12 months; 12 points means a race ban).
- **Stewards' decisions:** penalties, reprimands, at-fault collisions, track limits.
- **Reviews and re-rulings.** Sainz's 2025 Dutch GP points were removed after a successful right of review, when the incident was re-ruled a racing incident. The pipeline must handle these.

**Penalty points snapshot, April 2026** (The Race; values change as points expire, so the pipeline recomputes them from stewards' documents):

| Pts | Drivers |
|---|---|
| 10 | Bearman |
| 6 | Stroll |
| 5 | Antonelli |
| 4 | Piastri, Sainz |
| 3 | Lawson, Albon, Hamilton, Verstappen |
| 2 | Bortoleto, Gasly |
| 1 | Leclerc, Colapinto, Ocon |
| 0 | Russell, Norris, Hadjar, Hülkenberg, Alonso, Lindblad, Bottas, Pérez |

Context: Magnussen became the first driver banned under the points system, in 2024.

**Derived metrics:**
- `incidents_at_fault_per_100_battles`: at-fault incidents divided by the number of close battles. This normalises for drivers who simply fight more.
- `defensive_infringements`: moving under braking, more than one change of direction, forcing a rival off track.
- `procedural_infringements`: red flags, yellow flags, pit entry. These are kept separate, because they are not racecraft aggression.

### Tier 2: Expert opinion (strong, but subjective)

**Team principals' top 10, 2024** (formula1.com, points):
1. Verstappen 250
2. Norris 175
3. Leclerc 121
4. Piastri 113
5. Sainz 110
6. Russell 86
7. Hamilton 54
8. Hülkenberg 39
9. Alonso 27
10. Gasly 21

**2025 season, four separate polls:**
- The four polls were team principals, drivers, Motorsport.com journalists, and Autosport readers. Verstappen topped all four. Norris, Russell, Piastri and Leclerc followed closely.
- **Team principals:** 1. Verstappen, 2. Norris, 3. Piastri, 4. Russell, 5. Alonso, 6. Sainz. They ranked Leclerc below Alonso and Sainz.
- **Drivers:** 1. Verstappen, 2. Norris, 3. Russell.
- **Midfield:** Hadjar was the only midfield driver to appear in all four top 10s.
- **Absent from all four top 10s:** Hamilton, Lawson, Ocon, Stroll, Tsunoda and Bortoleto.

**Use in the model:**
- Converted to a per-season `expert_score` (average normalised rank points across polls). Team principals and drivers are weighted above journalists, and journalists above reader polls.
- A **weak prior** on overall driver quality, applied only where data is thin (rookies, returning drivers).
- Also a **validation check**: if our data-driven rating disagrees strongly with a consensus of experts, investigate before trusting either.

### Tier 3: Fan and community sentiment (weakest; useful for "aggression" perception)

Reddit couldn't be read directly from this chat. The plan is to collect it properly:
- **Sources:**
  - r/formula1 post-race and "driver of the day" threads;
  - r/F1Technical (more technical and more moderated);
  - comments from recognised experts, such as flaired users or known journalists, weighted higher.
- **Collection:** the official Reddit Data API. Check its terms for our usage, and store only aggregated scores, not raw user text.
- **Processing:**
  1. Identify which driver each comment is about.
  2. **Aspect-based sentiment** on fairness/cleanliness, aggression, racecraft, errors and pace.
  3. Aggregate per driver per race with time decay.
- **Bias controls:**
  - popularity and nationality bias: normalise within driver, compare against their own baseline;
  - recency spikes after controversial incidents;
  - brigading: cap the influence of any single thread.
- **Output:** `perceived_aggression` and `perceived_fairness`. These are **display-only** unless they agree with Tier 1.

### Combining the tiers

```
driving_standards_score = 0.6·Tier1 + 0.3·Tier2 + 0.1·Tier3   (initial weights, tuned by backtest)
```

**How it affects the simulator.** It adjusts the defender's aggression, which raises both `hold_rate` and the collision probability in battles, and the probability of penalties.

**Shown in the UI with sources.** It is never presented as a verdict on a person's character.

---

## 5. Full driver rating vector

Each driver gets a vector per season, each value with an uncertainty:

| Skill | Main evidence | Prior when data is thin |
|---|---|---|
| `quali_pace` | Teammate network (§1) | F2/F3 network, expert score |
| `race_pace` | Corrected clean-air laps, network | quali_pace |
| `tyre_mgmt` | Degradation driver effect vs teammate | Team average |
| `consistency` | σ of corrected laps | Grid average |
| `attack` / `defend` | Pairwise overtaking model (§3) | Grid average |
| `starts` | `lap1_net` vs expected | Grid average |
| `restarts` | `restart_net` | Grid average |
| `wet_skill` | Wet sessions, network | race_pace |
| `error_rate` | Offs, spins, at-fault incidents per race distance | Grid average |
| `aggression` | Tier 1 + 2 + 3 (§4) | Grid average |
| `circuit_affinity` | Per-circuit residuals, heavily shrunk | 0 |

**Era handling.** Each skill has an era offset for 2026, because the new rules may favour different skills. Seasons 2018–2025 inform *relative* ability; 2026 data dominates as it accumulates.

---

## 6. What the app shows (driver page)

- A radar chart of the skill vector with confidence bands, compared against the teammate and the grid median.
- Teammate network graph (who has been compared to whom).
- Qualifying and race pace trends by season.
- Pass and hold rates with a pace-adjusted "vs expected".
- Driving standards panel: penalty points timeline, at-fault incidents, expert poll history, community sentiment (clearly labelled).
- Per-race attribution: driver, strategy, car or luck.

---

## 7. Data backlog

| Item | Source | Priority |
|---|---|---|
| Qualifying laps 2018–2026 (segment-matched) | FastF1 / Jolpica | M |
| Race laps + intervals 2018–2026 | FastF1 (+ OpenF1 2023+) | M |
| Stewards' decisions & penalty points | FIA documents, race control messages | M |
| Team principal / driver poll history 2019–2025 | formula1.com articles (manual entry, small) | S |
| Expert rankings (Autosport, The Race, BBC) | Manual entry per season | C |
| F2/F3 results & quali for rookies | FIA F2/F3 results | S |
| Reddit sentiment | Reddit Data API | C (last) |

---

## Sources
- The Race: final 2025 teammate qualifying scores; 2026 penalty points list (Apr 2026)
- PlanetF1: 2024/2025/2026 teammate qualifying head-to-heads
- Formula1.com: team bosses' top 10 (2024, 2025), drivers' top 10 (2025)
- Motorsport.com / Autosport: combined 2025 rankings
- GPblog: 2025 overtake counts; FormulaDream: 2025 on-track pass analysis
- RacingNews365: penalty points detail and the Sainz review
