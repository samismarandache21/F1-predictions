# F1 Race Strategy Engine — Research Knowledge Base

> **Purpose.** This README is the research foundation for an app that recommends the optimal race strategy in Formula 1 (pit timing, compound choice, undercut/overcut calls, Safety Car reactions, etc.). It collects what is publicly known about how F1 strategy works, how teams and researchers model it, which numbers matter, and where to get the data.
>
> **Last researched:** 15 September 2026 (mid-way through the 2026 season, the first year of the new technical regulations). Numbers marked *2026* come from partial-season analyses and should be refreshed as the season ends.
>
> **How to use this document.** Sections 1–9 describe the physics and rules the engine must encode. Section 10 covers optimisation and simulation methods. Section 11 lists data sources. Section 12 is a list of hard-won pitfalls from people who have already built these systems. Section 13 proposes an architecture and MVP plan. Section 15 lists every source.

---

## Table of contents

1. [The core strategy problem](#1-the-core-strategy-problem)
2. [The 2026 rulebook: what the engine must encode](#2-the-2026-rulebook-what-the-engine-must-encode)
3. [The lap-time model](#3-the-lap-time-model)
4. [Pit stops and pit-loss time](#4-pit-stops-and-pit-loss-time)
5. [Safety Car, VSC and red flags](#5-safety-car-vsc-and-red-flags)
6. [Undercut, overcut and other pit tactics](#6-undercut-overcut-and-other-pit-tactics)
7. [Overtaking difficulty, dirty air and track position](#7-overtaking-difficulty-dirty-air-and-track-position)
8. [Energy management (new in 2026)](#8-energy-management-new-in-2026)
9. [Weather and crossover points](#9-weather-and-crossover-points)
10. [Optimisation and simulation methods](#10-optimisation-and-simulation-methods)
11. [Data sources and licensing](#11-data-sources-and-licensing)
12. [Pitfalls and lessons learned](#12-pitfalls-and-lessons-learned)
13. [Proposed app architecture and MVP roadmap](#13-proposed-app-architecture-and-mvp-roadmap)
14. [Glossary](#14-glossary)
15. [Sources](#15-sources)
16. [Open questions / to verify](#16-open-questions--to-verify)

---

## 1. The core strategy problem

A pit stop costs time: the car is stationary, and the pit lane is speed-limited, so a driver loses roughly 20–25 seconds compared with staying on track. A pit stop also pays back time: fresh tyres are faster than worn ones. **Race strategy is the problem of balancing that cost against that benefit** so that the total race time is as short as possible — or, more precisely, so that the *finishing position* is as good as possible. (Heilmeier et al., *Virtual Strategy Engineer*, 2020.)

Those two objectives are not the same. In a race with no opponents, the best strategy is simply the one with the minimum total race time, and it can be solved with a small optimisation problem. In a real race, other cars, overtaking difficulty, traffic, Safety Cars and random events mean there is no single "optimal" strategy — only strategies with better or worse *distributions* of outcomes. That is why teams run race simulations (usually Monte Carlo) before and during the race, and why the app should ultimately output probabilities, not a single answer.

The decisions the engine has to make are:

| Decision | When | Inputs that matter most |
|---|---|---|
| Number of stops | Pre-race, revised live | Degradation rate, pit loss, SC probability, overtaking difficulty |
| Starting compound | Pre-race | Degradation, warm-up, start performance, tyre sets available |
| Stint lengths / pit laps | Pre-race plan + live | Degradation curve, cliff, fuel effect, traffic windows |
| Which compound at each stop | Live | Laps remaining, two-compound rule, sets available, track temp |
| Box now vs. box later (undercut/cover) | Live, lap-by-lap | Gap to rival, tyre-age delta, warm-up, traffic on exit |
| React to SC / VSC | Live, within seconds | Pit-loss discount, laps remaining, whether a stop is still owed |
| Weather switch (slick ↔ inter ↔ wet) | Live | Lap-time ratio vs. dry, radar, risk tolerance |

---

## 2. The 2026 rulebook: what the engine must encode

2026 is the biggest regulation reset in the sport's history: new chassis, new power units, active aerodynamics, new tyres. Any model trained on 2022–2025 data needs to be re-calibrated.

### 2.1 Tyres

| Rule / fact | Detail | Source |
|---|---|---|
| Dry compound range | Five slicks, **C1 (hardest) to C5 (softest)**. The C6 used in 2025 was dropped because Pirelli could not get a large enough lap-time gap between C5 and C6. | Pirelli press release; Motorsport.com (Nov 2025) |
| Design intent | Pirelli aimed for a wide, consistent lap-time delta between compounds to create more strategy options. (See §3.3 — the 2026 data suggests this did not fully happen.) | Pirelli |
| Weekend nomination | Pirelli picks **three** of the five compounds per event; they are labelled Hard / Medium / Soft regardless of C-number. Intermediates and full wets are always available. | RacingNews365; F1.com |
| Tyre size | Fronts 25 mm narrower and 15 mm smaller in diameter; rears 30 mm narrower and 10 mm smaller in diameter. 18-inch rims retained. | GPFans (FIA's Kris Degroot) |
| Wheel rims | No longer a single supplier — each team chooses its rim manufacturer, so rim designs differ between cars. | GPFans |
| Two-compound rule | In a dry race, every driver must use at least **two different dry compounds**, which forces at least one stop. All four tyres must be the same compound. The rule does not apply in sprints or if intermediates/wets are used. | RacingNews365; f1thedata.com |
| Starting tyre | **Free choice** for all drivers since 2022 (the old "start on your Q2 tyre" rule for the top 10 was abolished). | Autosport; The Race |
| Monaco special rule | 2025 had a mandatory minimum of three tyre sets (i.e. two stops) at Monaco. It was exploited by team-mates backing up the field, and **it was removed from the 2026 regulations**. | Motorsport.com (Feb 2026); F1.com |
| Weekend allocation | Historically 13 dry sets + 4 intermediate + 3 wet sets per car, with Pirelli nominating two mandatory race sets. Allocations have been trimmed in recent years for sustainability, and the Alternative Tyre Allocation is used on sprint weekends. **Verify exact 2026 set counts against the FIA Sporting Regulations.** | Pirelli (2016 rules); F1pedia |

> **Engine implication:** model compounds *relatively* (S/M/H) per race, but keep the absolute C-number as a feature — it carries information about how much stress the track puts on tyres (Heilmeier et al. used "hardest compound available at this track" as a track-severity category).

### 2.2 Aerodynamics and overtaking aids

DRS no longer exists. It is replaced by **Active Aero**: movable front *and* rear wing elements with a **Corner Mode** (high downforce) and a **Straight Mode** (low drag) that can be used by *every* car in designated zones on every lap — it is an efficiency tool, not an overtaking aid. Race control can enable a partial mode in the wet (front in Straight Mode, rear in Corner Mode). (The Race; F1 Chronicle.)

The overtaking aid is now **Overtake Mode** (formerly "Manual Override Mode"): a driver who is within **one second** of the car ahead at a detection point (nominally the last corner) gets extra electrical energy — about **+0.5 MJ** — to deploy on the following lap, all at once or spread across the lap. (The Race; Sky Sports; ESPN.) See §8 for the energy system.

### 2.3 Power unit, fuel and car

| Item | 2026 value | Source |
|---|---|---|
| Power split | Roughly 50% combustion / 50% electrical | Reuters via Flashscore; ESPN |
| Fuel | 100% sustainable fuel; energy-flow limit of 3,000 MJ/h replaces the old mass-flow limit | F1 Chronicle; F1 Briefing |
| Race fuel load | About **70 kg** (vs. up to 110 kg in 2014–2025) — so the fuel-weight penalty at the start is much smaller | F1 Chronicle |
| Refuelling | Banned since 2010 — pit stops are tyre-only (plus damage repair) | RacingNews365; Heilmeier et al. |
| Car size | Wheelbase −200 mm, width −100 mm, floor width −150 mm | ESPN |
| Minimum weight | About 30 kg lighter than 2025 (sources quote 768–770 kg; check the FIA Technical Regulations) | ESPN; F1 Briefing |
| Downforce / drag | Ground-effect tunnels removed; downforce down roughly 15–30%, drag down ~40% | ESPN |

### 2.4 Sporting format details that affect strategy

The grid is **22 cars** in 2026 (Cadillac joined as the 11th team), and Q1 and Q2 each eliminate six cars. Q3 is 13 minutes long. (Motorsport.com; F1pedia.) The bonus point for fastest lap was removed from 2025, which removes the old incentive for late "free" pit stops just to set a fast lap (f1thedata.com) — Heilmeier et al. had to filter those stops out of their training data for exactly that reason.

A Grand Prix is about 305 km (Monaco about 260 km) with a two-hour race-time limit, and at least two green-flag laps must be completed for points to be awarded (f1thedata.com). The pit-lane speed limit is 80 km/h by default but can be reduced (typically to 60 km/h at tight venues) by the Race Director on the Safety Delegate's recommendation (Sportskeeda, quoting Article 34.7).

---

## 3. The lap-time model

Every serious race simulator builds lap times out of additive components. This is the heart of the engine.

### 3.1 The standard decomposition

The TUM race simulation (Heilmeier, Graf, Lienkamp 2018; Heilmeier et al. 2020) computes the lap time of each driver in each lap `l` as:

```
t_lap(l) = t_base                       # track: fastest possible lap for the best car/driver
         + t_tire(a, c)                 # tyre degradation: tyre age a, compound c
         + t_fuel(l)                    # extra time from fuel mass still on board
         + t_car + t_driver             # car and driver pace offsets
         + t_grid(l, p_g)               # start loss depending on grid position (lap 1 only)
         + t_pit_inlap/outlap(l)        # pit-stop losses on in-lap and out-lap
```

Race time is the cumulative sum of lap times. Comparing cumulative times at the end of each lap tells the simulator whether an overtake could have happened, after which lap times are adjusted for the cars involved.

A modern extension (Pitwall, Santillana 2026) adds three things that matter a lot in practice: a **tyre cliff**, **Gaussian lap noise**, and an explicit **out-lap warm-up penalty**:

```
lap(t, a) = f0[t] + δ[t]·a + 1[a > k[t]]·s[t]·(a − k[t]) + ε,     ε ~ N(0, σ_lap²)

f0[t]  = base pace of compound t
δ[t]   = linear wear slope (s/lap per lap of tyre age)
k[t]   = cliff "knot" age (circuit- and compound-specific)
s[t]   = extra degradation per lap once past the cliff
σ_lap  ≈ 0.18 s (calibrated default)
```

### 3.2 Tyre degradation models

| Model | Formula | Pros | Cons |
|---|---|---|---|
| Linear | `t_tire = k0(c) + k1(c)·a` | Robust with sparse data; makes stint optimisation a small quadratic problem | Misses the cliff and early-stint effects |
| Linear + cliff (hinge) | as above + `s·max(0, a − k)` | Captures the "falling off a cliff" phase that decides many stops | Cliff parameters must be mined per circuit & compound |
| Quadratic / polynomial | `k0 + k1·a + k2·a²` | Smooth acceleration of wear | Extrapolates badly beyond observed stint lengths |
| Saturating | `A·(1 − exp(−a/τ))` | Physically plausible plateau | In one 2026 study τ was not identifiable from data |
| State-space / time-series | latent tyre state updated each lap | Probabilistic, updates live | More complex; needs careful tuning |
| ML on tyre energy | NN / XGBoost on telemetry-derived tyre energy | Very accurate with team telemetry | Needs data teams do not publish |

Key background on *why* tyres degrade: rubber is viscoelastic; grip falls both from **wear** (rubber physically lost) and from **thermal** effects (running outside the operating window, overheating). Overheating accelerates wear; a tyre running *below* its window slides, which triggers **graining** and **blistering**. Drivers can manage temperatures with lift-and-coast, and a well-balanced car degrades both axles at similar rates. (Catapult; F1 Chronicle; Autosport.)

Soft tyres start faster (smaller `k0`) but traditionally degrade faster (larger `k1`) than harder tyres, which is why the choice of compound depends on stint length. (Heilmeier et al. 2020.)

### 3.3 What the 2026 degradation data actually shows

F1 Chronicle's analysis of the first nine dry 2026 Grands Prix found a surprising result: **the traditional hierarchy inverted**. Median degradation was 0.071 s per lap of tyre age on the hard, 0.065 on the medium and 0.063 on the soft — the soft was the most durable. The spread between compounds (0.008 s/lap) was the narrowest of the ground-effect era, compared with 0.053 (2022), 0.011 (2023), 0.043 (2024) and 0.041 (2025). Over a 25-lap stint, that deg adds up to roughly 19–21 seconds against a fresh-tyre baseline. Austria was the most punishing measurable circuit at 0.097 s/lap. The proposed explanation is that the lighter, lower-downforce 2026 cars put less energy into the tyres, so harder compounds run below their window and slide, while softs now survive comfortably.

> **Engine implication:** do **not** hard-code "soft degrades fastest". Fit degradation per season, per circuit and per compound, and keep priors weak early in a new regulation cycle.

### 3.4 Fuel effect

Fuel burn makes the car lighter every lap, so lap times naturally improve through a stint even as tyres wear. A common rule of thumb is **0.25–0.40 s per lap for every 10 kg of fuel**, depending on the circuit (power- and braking-sensitive tracks like Spa or Monza penalise weight more than Monaco). (The Motorsport Metrics; thef1db.) A 2001 Prost team simulation for Barcelona used 0.32 s per 10 kg (F1technical forum). Treat these as priors to calibrate, not facts.

With about 70 kg of fuel in 2026, a 57-lap race burns roughly 1.2 kg per lap, so the fuel effect is on the order of **0.03–0.05 s of improvement per lap**. Pitwall's calibrated default is 0.05 s/lap, which it "folds out" of the raw degradation slope. Less fuel also means less tyre load, which reduces degradation (F1 Chronicle).

Heilmeier et al. note that in a no-opponent model the *order* of compounds does not matter if you ignore fuel mass and track evolution — a useful simplification for a first optimiser, but not for the full simulator.

### 3.5 Track evolution, warm-up and noise

The track gets faster as rubber is laid down, which also makes lap times fall through the race. Fresh tyres need time to reach operating temperature, so the **out-lap** is slower than the tyre's potential; the size of this warm-up penalty can decide an undercut on its own (see §6). Lap-to-lap variability (traffic, mistakes, wind, battery state) should be modelled as noise.

### 3.6 Warning: raw fits are confounded

This is the single most important modelling lesson found in the research, and it is covered in detail in §12. In short: if you fit `lap_time ~ tyre_age` naively, fuel burn and track evolution make the slope **negative** — tyres that "get faster forever" — and an optimiser will happily recommend impossible 50-lap soft stints. Pitwall fixes this by adding back a calibrated fuel effect and clamping the tyre-only wear slope to a physically plausible range of **0 to 0.22 s/lap**, plus a **maximum stint cap** per circuit and compound (no recommended stint may exceed what cars have actually completed there).

---

## 4. Pit stops and pit-loss time

### 4.1 What a pit stop really costs

A pit stop has three parts. The **stationary time** (wheels off, wheels on) is only about 2–2.5 seconds for a good crew — the record is 1.82 s (Red Bull, Brazil 2019). The **lane transit** at the speed limit is the big part. The third part is the **compromised in-lap and out-lap** (braking early for the pit entry, cold tyres on exit). (F1 Chronicle; Race Sundays.)

The standard way to measure the total cost:

```
pit_loss = (in_lap_time + out_lap_time) − 2 × reference_lap_time
```

where the reference is the driver's own clean pace on laps either side of the stop, excluding SC/VSC laps. (F1 Briefing; F1 Chronicle method.)

### 4.2 Measured pit-loss values

F1 Chronicle measured 2,106 green-flag stops from 2022–2026, using medians rather than means because disaster stops (up to ~50 s) distort averages.

| Circuit | 2026 median loss (s) | 2026 "clean stop" (10th pct, s) | Note |
|---|---|---|---|
| Miami | 19.7 | 17.7 | Cheapest measured 2026 stop |
| Silverstone | 20.9 | 19.6 | Longest lane to drive (29.1 s transit) but it bypasses a lot of track |
| Red Bull Ring | 21.5 | 20.0 | Quickest lane transit (21.6 s) |
| Monaco | 22.0 | 18.5 | Biggest gap between clean and typical: rejoining in traffic costs a lot |
| Barcelona | 23.8 | 22.1 | Dearest measured 2026 stop |

Across the whole 2022–2026 era, **Spa** is the cheapest place to stop (18.4 s median, because the lane cuts off La Source), while **Imola (28.1 s), Singapore (27.9 s) and Qatar (27.7 s)** are the most expensive. The all-circuit median barely moved through the regulation change: 22.58 s in 2022 and 22.07 s in 2026. Pit loss is set by lane length, speed limit and geometry — **it is the most stable constant in F1 strategy**.

Other useful facts: a lane's *transit time* is not its *cost*; what matters is transit minus the track distance the lane lets you skip. Zandvoort's limit was raised from 60 to 80 km/h specifically to cheapen stops and encourage more strategic variety, and the FIA has discussed the same lever elsewhere (F1 Chronicle; Sportskeeda).

### 4.3 Modelling pit stops

Model the stationary time with a **right-skewed** distribution (Pitwall uses a deterministic base plus exponential noise) so the slow-stop tail is represented. Keep per-circuit priors for median and clean-stop loss. Under SC/VSC the loss is multiplied by a discount factor (§5). Some four circuits in 2026 had too few clean green-flag stops to measure because their pit windows fell under Safety Cars — a reminder that per-circuit samples can be thin.

---

## 5. Safety Car, VSC and red flags

### 5.1 Why neutralisations change everything

Under a Full Course Yellow the cars on track slow down, but the pit lane speed limit does not change — so **the relative cost of a pit stop drops sharply**. Heilmeier et al. describe this as the key strategic fact about FCY phases, and show that the best pit lap during an FCY is the one where *both* the in-lap and the out-lap are covered by the neutralisation. In practice, most drivers pit on the **first lap** of an FCY: later, there is a risk the VSC ends while the car is in the pits, or (under SC) the field has already bunched up and positions are lost.

| Parameter | Value | Source |
|---|---|---|
| SC lap time vs. green | ~160% (Heilmeier) / calibrated 1.40 multiplier (Pitwall) | Heilmeier et al. 2020; Pitwall |
| VSC lap time vs. green | ~140% (Heilmeier) / calibrated 1.22 (Pitwall, bounds 1.10–1.35) | Heilmeier et al. 2020; Pitwall |
| Pit loss under SC | ~0.45 × green pit loss (≈ 10 s instead of ≈ 22 s) | Pitwall; thef1db |
| Pit loss under VSC | ~0.65 × green pit loss (bounds 0.45–0.85) | Pitwall |
| VSC duration | 1–3 laps (uniform) | Pitwall |
| VSCs per race | roughly 0.5–0.9 | Pitwall |
| Tyre ageing under FCY | Tyres are stressed less: Heilmeier's features slowed tyre-age progression by 50% under VSC and 75% under SC | Heilmeier et al. 2020 |

A VSC stop saves less than an SC stop but happens more often and ends sooner, which changes the option value of staying out. (Pitwall.)

### 5.2 Safety Car probability by circuit

The Safety Car probability is circuit-dependent and should be a per-circuit prior. Historical rough figures: **Singapore has had at least one SC in every race** (about 1.7 SCs per race on average), Monaco roughly 70%, Bahrain around 14%. Canada and Monaco have historically been high-SC venues; Hungary and Bahrain low. (F1BetUK, May 2026; Crash.net.) These come from betting/fan analyses — recompute them from timing data (race-control messages) before trusting them.

A simple and effective simulation model (Pitwall) draws an SC each lap with hazard:

```
p_SC(lap) = λ_SC(circuit) / laps_remaining        # λ = expected SCs remaining, circuit prior × calibrated multiplier
```

with VSC drawn the same way at its own rate; SC takes priority if both would fire.

### 5.3 Strategic playbook

Strategists pre-compute an **SC window**: the range of laps in which an SC-discounted stop would let the car reach the finish without stopping again. If the SC comes inside the window, switch to "Plan B" and pit immediately; if it comes too early, staying out may be better because a second stop would be needed anyway. A high SC probability can justify running *longer* on the first stint to "bank" the chance of a cheap stop. (Axiora; Pitwall.)

The app must also model **rivals pulling their stops forward** under SC/VSC — a rival simulator that ignores cheap-stop windows is systematically wrong about neutralised periods (Pitwall's "H17" component).

### 5.4 Red flags

Under a red flag, cars return to the pit lane and teams are generally allowed to change tyres, which can act as a "free" pit stop. **Verify the current wording of the 2026 Sporting Regulations** on tyre changes during suspensions and whether they count toward the two-compound requirement before encoding this.

---

## 6. Undercut, overcut and other pit tactics

### 6.1 The undercut

The undercut is used when a driver is fast enough to follow a rival but not to pass on track. The pursuer pits *first* and uses the pace of new tyres to gain enough time that, when the rival pits, the rival rejoins behind. It works best when the fresh-tyre advantage is large and the pursuer rejoins into clear air. (Heilmeier et al. 2020.) It is weakened by slow tyre warm-up, traffic on the out-lap, and very long pit lanes, and the defender can neutralise it by pitting on the next lap ("covering"). (thef1db; The Motorsport Metrics.)

A practical way to reason about it, for a defender who stays out one extra lap:

```
undercut_gain ≈ Σ over laps defender stays out of (pace_old_tyre − pace_new_tyre)
              − attacker_outlap_warmup_penalty
              + defender_outlap_warmup_penalty
              − attacker_traffic_loss
              + (defender_stationary_time − attacker_stationary_time)

undercut succeeds if  undercut_gain > gap_before_stop (+ safety margin)
```

**Worked example (illustrative numbers).** The attacker is 1.2 s behind. New tyres are worth 1.5 s/lap against the defender's worn set; both drivers lose 0.8 s warming up tyres on the out-lap; the defender pits one lap later. Gain ≈ 1.5 − 0.8 + 0.8 = 1.5 s > 1.2 s, so the undercut works — but only by 0.3 s, which a slightly slow stop could wipe out. If the defender switches to a hard tyre that warms up more slowly (say 1.5 s penalty), the gain grows to 2.2 s. This is why warm-up behaviour is as important as peak grip.

**What the data says.** In 2026, Barcelona had both the most expensive pit lane *and* the most undercuts (69 attempts, median gain 1.8 s), while cheap-stopping Miami saw almost none (median gain 0.3 s). The conclusion: **the circuit's tyre degradation decides whether undercuts happen; pit loss only prices them.** (F1 Chronicle.) Pitwall's logistic model of 2,134 historical undercut events (base success rate 25%) found the **gap before the stop** is by far the dominant predictor, while tyre-age difference adds little.

Real examples to use as test cases: Monaco 2026, where George Russell's 14.1 s stop (the cheapest in five seasons of data) produced a decisive undercut on Isack Hadjar (F1 Chronicle); Imola 2024, where Lando Norris's undercut on Max Verstappen dropped him into traffic behind Sergio Pérez and Verstappen held on by 0.725 s (SimRacing Pro, citing F1.com/ESPN).

### 6.2 The overcut

The overcut is the opposite: stay out while the rival pits, and use the rival's slow out-lap (cold tyres) or the traffic they rejoin into to keep or gain the position. It needs the staying driver to have clean air and tyres that are not falling off, so it is favoured by **low degradation**, slow warm-up of the new compound, and pit exits into traffic. (Grand Prix Pal; GP Explained; F1 Briefing.)

### 6.3 Other tactics the engine should know

| Tactic | Description |
|---|---|
| **Cover** | Pit the lap after a rival pits to neutralise their undercut. Heilmeier's VSE used two features for this: "pursuer changed tyres last lap" and "pursuer within 1.5 s". |
| **Go long / offset** | Run a much longer stint to have fresher tyres at the end than rivals. |
| **Free stop** | If the gap to the car behind exceeds the pit loss (plus margin), stop without losing position. Under SC the required gap roughly halves. |
| **Team-mate backing up the field** | One car slows the pack to open a pit window for the car ahead. This was exploited at Monaco in 2025 (Racing Bulls, Williams), which contributed to the mandatory two-stop rule being dropped for 2026. (Motorsport.com.) |
| **Short-fuelling** | Start lighter for pace early and save fuel later (less relevant with 70 kg races). |
| **Stop-count decision** | Teams try to minimise stops because each one risks a mistake and traffic; Pirelli's Mario Isola noted teams often still make one-stops work even when Pirelli brings softer or non-adjacent compounds. (Motorsport.com, Nov 2025.) |

---

## 7. Overtaking difficulty, dirty air and track position

### 7.1 Modelling pass probability

A car following closely loses time in **dirty air** (turbulent wake). Pitwall models this as a fixed per-lap loss inside a gap window (calibrated defaults: **0.35 s/lap** within **1.2 s**). Passing is then resolved either with a deterministic rule (pass only if the pace advantage exceeds a circuit threshold) or with a learned **overtake kernel**:

```
P(pass per battle-lap) = sigmoid( A_circuit + k_p · Δpace + k_t · Δtyre_age )
```

Fitted on 131,000 adjacent-car battles (4,142 clean passes, a 3.2% base rate), a car that is 1.0 s/lap faster passes with about **11%** probability per lap, and one that is 2.0 s/lap faster with about **27.5%**. The circuit offsets reproduce known difficulty: **hardest Monaco, Imola, Canada; easiest Qatar, Spa, Las Vegas**. (Pitwall.) A 2021 study of the Pirelli era documented order-of-magnitude differences in passes between street and power circuits (de Groote, *Journal of Sports Analytics*).

An important negative result: the learned kernel predicted individual passes better than the simple rule, but did **not** improve whole-race predictions once plugged into the simulator — **the size of the pace gaps between cars matters more than the exact shape of the pass model**.

### 7.2 What changed in 2026

Headline overtake counts rose sharply at the start of 2026: Australia 45 → 120, China 72 → 146, Japan 28 → 106 (F1 Fantasy / Motor Sport). But many of those passes were **energy "yo-yo" passes** — a car with a charged battery passes one with a depleted battery and is re-passed a lap later. Overtake counts are distorted by strategy variation, race disorder and cars out of position, so they are a poor proxy for real overtaking difficulty. (Motor Sport Magazine; The Race.) Overtake Mode is expected to help most at tracks with long straights and heavy braking, such as Monza, Spa and Las Vegas. (Silverstone.)

> **Engine implication:** when estimating overtaking difficulty from 2026 data, count only *sustained* position changes (e.g. still ahead N laps later), and treat battery state as a hidden variable.

### 7.3 Track position vs. raw pace

At high-difficulty circuits (Monaco, Singapore), the strategy that minimises race time is often *not* the one that maximises finishing position — being ahead on track is worth more than being faster. Pitwall flags such venues with a confidence gate rather than pretending its time-optimal plan is right there. (Pitwall.) Monaco also shows the biggest spread between a clean stop and a typical one because rejoining into a queue is so costly (F1 Chronicle).

---

## 8. Energy management (new in 2026)

The 2026 power units put much more emphasis on electrical energy, and drivers now control it through several named tools (F1.com; The Race; ESPN):

| Tool | What it does | Strategic relevance |
|---|---|---|
| **Boost** | Driver-triggered deployment of maximum combined power (or a team-configured profile), anywhere on track, to attack or defend | Battles; defending undercuts on the out-lap |
| **Overtake Mode** | Extra energy (≈ +0.5 MJ) on the next lap if within 1 s of the car ahead at the detection point | Replaces DRS as the overtaking aid |
| **Recharge** | Harvesting energy under braking, when lifting at the end of straights, and even in partial-throttle corners | A car that just harvested is vulnerable; one that saved is dangerous |
| **Active Aero** | Corner/Straight wing modes available to all | Efficiency, not an overtaking advantage |
| **Super clipping** | Battery top-up while still at full throttle with the wing still in Straight Mode | Part of lap-energy planning |

The big modelling problem is that **battery state of charge is not in the public timing data**. A car's lap time on a given lap depends on whether it deployed or harvested, which adds noise to degradation fits and makes overtake counts misleading (§7.2). Options for the app: treat energy as noise in v1; later, infer a latent energy state from speed-trap and mini-sector patterns (OpenF1 and FastF1 expose speed and sector data). Academic work on optimal energy allocation for hybrid F1 power units exists (Duhr et al., IEEE TVT 2023; Limebeer et al. 2014) if you want to go deeper.

---

## 9. Weather and crossover points

A **crossover point** is the moment when a different tyre type becomes faster. Pirelli's rule of thumb: if a normal slick lap is 100%, it is time to consider intermediates once lap times rise to about **110–112%**, and the same ratio applied to intermediate lap times signals the switch to full wets. Being on intermediates when slicks are right can cost 5–6 s per lap; being on slicks when it is too wet costs even more and risks aquaplaning. (Pirelli.)

| Tyre | Use | Water clearance (per tyre, at speed) |
|---|---|---|
| Slick | Dry | None |
| Intermediate (green) | Damp / drying track; works roughly between 20 and 50 °C track temperature | ~30 litres/s |
| Full wet (blue) | Standing water / heavy rain | ~85 litres/s |

(Source: F1-Fansite glossary.) On a drying track, the aim is to be first onto slicks; intermediates overheat and can grain or blister quickly as the track dries. Weather strategy is a forecast problem: the right call matches the next few minutes, not the current state, so radar and rain-probability inputs matter. Classic cautionary tales: Russia 2021 (Norris stayed on slicks as rain intensified; Hamilton pitted for inters at the right moment and won) and Turkey 2021 (Vettel's one-lap switch to slicks on a track that was not ready). (GP Explained; ESPN.)

> **Engine implication:** both academic simulators studied (TUM, Pitwall) exclude or gate wet races. Treat wet strategy as a **separate v2 module** with a lap-time-ratio trigger, radar input and a "first-mover" bonus/penalty.

---

## 10. Optimisation and simulation methods

### 10.1 Step 1 — Enumerate legal compound sequences

With three nominated compounds and the two-compound rule, and assuming order does not matter in a no-opponent model, Heilmeier et al. list the candidate "sets" for up to three stops:

```
1 stop : SM, SH, MH
2 stops: SSM, SSH, SMM, SMH, SHH, MMH, MHH
3 stops: SSSM, SSSH, SSMM, SSMH, SSHH, SMMM, SMMH, SMHH, SHHH, MMMH, MMHH, MHHH
→ 22 candidate sets per driver
```

In the 2014–2019 data, more than three stops essentially only happened in wet races or after technical problems. For the full simulator, order *does* matter (fuel, track evolution, warm-up), so expand each set into its permutations and respect the tyre sets actually available.

### 10.2 Step 2 — Optimal stint lengths

For each set, find the stint lengths that minimise total race time. Because grid loss and fuel loss do not depend on the strategy, and pit loss is fixed for a given number of stops, the objective reduces to the total tyre time loss. With the **linear** degradation model this has a closed form per stint (Heilmeier et al. 2020):

```
Σ_{a=1..α} (k0 + k1·a) = k0·α + k1·(α² + α)/2
```

which makes the whole problem a small **mixed-integer quadratic program** (Heilmeier used this; brute-force enumeration also works because races are only 50–78 laps). For two stints on compounds A and B over L laps, the continuous optimum for the first stint is approximately:

```
x* ≈ (k1_B · L + k0_B − k0_A) / (k1_A + k1_B)
```

(derived by setting the derivative of the total loss to zero; round and clamp to feasible stint caps). Heilmeier et al. also handle **used tyres** (non-zero starting age) by shifting the stint's age range.

### 10.3 Step 3 — How many stops? A quick sanity check

For N equal-length stints on a tyre with linear degradation slope `k1`, total degradation loss ≈ `k1·L²/(2N)`. Adding one more stop saves `k1·L²/(2N(N+1))` but costs one pit loss `P`. So:

```
add a stop if   k1 · L² / (2·N·(N+1))  >  P
```

**Example:** L = 57 laps, P = 22 s. With k1 = 0.07 s/lap (2026's typical figure), going from 2 to 3 stints saves ≈ 19 s < 22 s → **one-stop**. With k1 = 0.10 s/lap (Austria-like), it saves ≈ 27 s > 22 s → **two-stop**. This simple inequality explains why the paddock worried about 2026 becoming a "one-stop season" (F1 Chronicle). The real engine must add cliffs, compound offsets, traffic and SC probability on top.

### 10.4 Step 4 — Race simulation with opponents

A lap-discretised race simulation (TUM) advances every car lap by lap, computes lap times from §3, applies pit losses, checks for overtakes and applies interaction effects. Strategy engineers use it **before** the race (base strategy + what-if scenarios) and **during** the race (re-evaluating options from the current state). (Heilmeier et al.)

### 10.5 Step 5 — Monte Carlo for uncertainty

Randomise the things that are genuinely uncertain — accidents/failures, SC/VSC phases, start performance, lap-time variability, pit-stop duration — and run thousands of races to get a **distribution** of finishing positions. This shows how *robust* a strategy is, not just how fast it is on average. The TUM work introduced a "ghost car" approach to model SC effects realistically. (Heilmeier et al., *Applied Sciences* 2020.)

Pitwall's engineering choices are a good blueprint for a fast implementation:

| Technique | Why it matters |
|---|---|
| **Vectorised simulation** (N × C arrays, N = 2,000 replications, C = cars) | 10–50× faster than a scalar loop; a full-field re-simulation runs in seconds on one CPU |
| **Common random numbers (CRN)** | Compare "box now / +1 lap / +2 laps / stay out" under *identical* random SC, retirement and noise draws, so differences reflect strategy, not luck; stable deltas at N = 2,000 |
| **Bootstrap confidence intervals** | Resample the simulated results (B = 500) to attach 90% intervals to win/podium/points probabilities at no extra simulation cost |
| **Rival policy** | Assume rivals follow their pace-optimal remaining plan (and pull stops forward under SC). Known gap: rivals don't react to *your* undercut — the "covering game" is the main residual error |
| **Kalman filter on live pace** | A per-car two-state filter (pace offset + residual deg slope) so one contaminated lap can't swing the whole board |

**Calibrated starting parameters (Pitwall defaults, with search bounds):**

| Parameter | Default | Bounds |
|---|---|---|
| Lap noise σ | 0.18 s | 0.05–0.40 |
| Retirement probability per car | 0.07 | 0.00–0.15 |
| SC pace multiplier | 1.40 | 1.15–1.70 |
| SC pit-loss factor | 0.45 | 0.20–0.80 |
| VSC pace multiplier | 1.22 | 1.10–1.35 |
| VSC pit-loss factor | 0.65 | 0.45–0.85 |
| Dirty-air window | 1.2 s | 0.4–2.5 |
| Dirty-air loss | 0.35 s/lap | 0.0–0.8 |
| Grid spread per slot | 0.28 s | 0.0–1.5 |
| Fuel effect | 0.05 s/lap | 0.00–0.15 |

### 10.6 Step 6 — Automating decisions: ML and RL

| Approach | Summary | Source |
|---|---|---|
| **Virtual Strategy Engineer (supervised NN)** | Two neural networks called once per lap: the first decides *pit or not*, the second (only if pitting) chooses the compound. Trained on 2014–2019 timing data. Classification beat regression; features included race progress, tyre-age progress, relative compound, position (leader vs. pursuer), track category, FCY status (5 states), remaining planned stops, "pursuer pitted last lap" and "within 1.5 s". Only 3.1% of laps are tyre-change laps → heavy class imbalance → use F1 score, stratified splits. | Heilmeier et al., *Applied Sciences* 2020 |
| **Reinforcement learning VSE (DQN)** | Trained inside the race simulation, per race. Included in the open-source TUM repo. | TUMFTM/race-simulation |
| **RSRL (Mercedes-AMG + King's College London)** | RL agent with actions {no pit, pit soft, pit medium, pit hard}, trained against Mercedes' Monte Carlo simulator. On the 2023 Bahrain GP it averaged P5.33 vs. P5.63 for a fixed strategy and P5.86 for Mercedes' own probabilistic model. Training on more tracks made it worse on seen tracks but better on unseen ones. Uses TimeSHAP, decision-tree surrogates and counterfactuals for explainability. | Thomas et al., ACM SAC 2025 |
| **Tyre-energy forecasting** | Deep learning and XGBoost trained on Mercedes telemetry to forecast tyre energy (a driver of degradation), with explainability. | arXiv 2501.04067 |
| **State-space tyre model** | Probabilistic, interpretable degradation model evaluated on 19 races of 2025; beat an AR(1) baseline in most races. | Cappello & Hoegh, arXiv 2512.00640 |
| **Online planning / MCTS** | Planning in a Markov decision process with FCY events injected at runtime. | PRL Workshop 2021 |
| **Evolutionary algorithms** | Genetic algorithm for F1 strategy. | Bonomi, Turri, Iacca, GECCO 2023 |
| **Learning-based strategies** | Recent review and learning approach; notes teams typically rely on Monte Carlo and that lap-wise discretisation is standard. | arXiv 2512.21570 |

**Recommendation for the app:** start with deterministic optimisation (10.1–10.3) → add Monte Carlo evaluation with CRN (10.5) → only then consider an RL/NN policy for rivals or for fast live calls. Explainability matters: users (like strategists) need to know *why* the app says "box now".

### 10.7 Evaluating the engine

Use **held-out seasons** rather than random lap splits (Heilmeier et al. cite earlier sports-analytics work warning that plain cross-validation is inappropriate for time-ordered data). Pitwall's metrics are a good template: Brier score and expected calibration error for win/podium/points probabilities, Spearman rank correlation for finishing order, and **decision fidelity** (does the recommended stop count match what actually worked?). Its reported results: winner in top-3 predictions 90.3% over 155 races, held-out Brier 0.0745, Spearman ≈ 0.77. Adding stint-length caps and mined cliffs raised stop-count agreement from 59.5% to 69.0% and eliminated infeasible stint recommendations (from 90.5% of races to 0%).

---

## 11. Data sources and licensing

| Source | What you get | Access | Notes |
|---|---|---|---|
| **FastF1** (Python) | Lap timing, car telemetry and position, tyre data, weather, schedule, results; built-in Jolpica access; pandas DataFrames; caching | `pip install fastf1` | Sessions are ~50–100 MB each, cached locally. The de-facto standard for analysis. |
| **Jolpica-F1** | Ergast-compatible historical API (results, laps, pit stops, standings…) | `https://api.jolpi.ca/ergast/f1/` | Successor to Ergast, which shut down at the start of 2025. Requires a custom User-Agent (e.g. `MyApp/1.0 FastF1/x.y`). Rate-limited; database dumps available. |
| **OpenF1** | 18 endpoints: car data (3.7 Hz), laps, intervals (≈ every 4 s), positions, **stints**, **pit**, race control, weather, team radio, overtakes, standings | Free: historical data since 2023, 3 req/s and 30 req/min, no auth. Sponsor (€9.90/month): **live** data via REST, MQTT and WebSocket, 6 req/s | Live data ≈ 3 s behind real time; "live" = 30 min before to 30 min after a session. **Licensed CC BY-NC-SA 4.0 and intended for non-commercial use — contact them before any commercial product.** |
| **TUMFTM repositories** | Race simulation (Python, LGPL-3.0) with parameter files for 121 races (2014–2019), F1 timing database, race-track database, lap-time simulation | GitHub | Excellent reference implementation of §3 and §10. |
| **F1DB** | All-time F1 database (CSV, JSON, SQL, SQLite) | GitHub | Good for circuit metadata and history. |
| **fia-doc** | Parsers for official FIA PDF documents (entry lists, tyre compounds, classifications, lap times, pit stops) | GitHub / Python | Useful to cross-check compounds and pit data. |
| **Pirelli previews** | Compound nominations per event, circuit severity ratings, expected strategies | pirelli.com press area | Key pre-race input. |
| **FIA regulations** | Sporting and Technical Regulations (tyre rules, pit lane, SC procedures) | fia.com | Source of truth for rule encoding. |
| **Official live timing (SignalR)** | The stream FastF1's live module and Pitwall use | Unofficial access | Check Formula 1's terms before building on it. |
| **awesome-f1** | Curated list of APIs, datasets and tools | GitHub | Good discovery list. |

> ⚠️ **Licensing and trademarks.** F1, Formula 1, Grand Prix and related marks are trademarks of Formula One Licensing B.V. Community data sources are unofficial. If the app is ever commercial, you will need to review data licences (OpenF1 is non-commercial by default) and trademark use.

**Suggested minimum dataset per race:** laps (time, sectors, compound, tyre age, stint, pit in/out flags, track status), pit stops (duration, lap), race-control messages (SC/VSC/red flag with start/end), weather (air/track temp, rain), grid, classification, retirements.

---

## 12. Pitfalls and lessons learned

These come from people who have built and deployed strategy engines. Building them into the design from day one will save months.

**1. Naive degradation fits are confounded.** Fuel burn and track evolution make lap times fall, so a raw `lap_time ~ tyre_age` slope is often negative. Correct for fuel, clamp tyre wear to a plausible range (0–0.22 s/lap), exclude in-laps, out-laps and SC/VSC laps, and cap stint lengths at what has actually been achieved at that circuit. Without caps, one optimiser recommended an infeasible stint in 90.5% of races. (Pitwall.)

**2. Compound pace is confounded with race phase.** Softs are usually run early (heavy fuel, green track) and hards late (light fuel, rubbered track). Fitted per race, the soft was *not* the fastest compound in 18 of 24 races in 2025, with spreads up to 3.1 s/lap — which made the engine wrongly recommend "box onto the fast tyre" all the time. Pitwall projects fitted base paces onto a canonical soft ≤ medium ≤ hard ordering (gaps constrained to 0.3–1.2 s/lap) **for decisions only**; in one case this changed a box-now success probability from an inflated 72.9% to a realistic 23.4%. (Pitwall.) But remember §3.3: in 2026 the *degradation* ordering itself inverted, so don't over-constrain.

**3. Practice long runs don't transfer well to races.** A 2026 project (TrackShift / PITWALL on GitHub) found that degradation curves fitted on practice long runs got the *average* stop value roughly right but had essentially no correlation with stop-by-stop outcomes. The value of a stop rose until tyre age ~21–25 laps and then fell (a linear test would have wrongly reported "no effect"). Better predictors were the compound pair, **track temperature** (hotter track → fresh rubber worth more) and **measured traffic**.

**4. Calibration and decision quality are different objectives.** A component that makes the simulator more "realistic" can make probability forecasts worse, and vice versa. Pitwall runs two paths — a calibrated "oracle" path for probabilities and a "decision" path for recommendations — and only enables a component on a path after it wins a held-out test on *that* path's metric. (Pitwall.)

**5. Wrong priors from analogous races.** Seeding 2026 Silverstone from the 2025 British GP (a wet race) produced a 14 s/lap spread between dry compounds and a nonsense 89% win probability for a car 75 s behind. Fix: reject any prior where slick compounds are more than ~3–4 s/lap apart, and prefer the most recent **dry** running. (Pitwall.)

**6. Live state estimation breaks in ways backtests never show.** Out-lap contamination of a live pace estimate gave a P8 car a 55.8% win probability mid-race in Austria 2026. Use filtered pace estimates, exclude out-laps, and treat state bugs as first-class defects. (Pitwall.)

**7. Cold-start for new circuits and new regulations.** 2026 has no same-season history early on; new venues (e.g. the Madring in Madrid, which hosted its first Grand Prix in September 2026 amid driver warnings about heavy tyre degradation) have none at all. Use hierarchical priors (similar circuits, Pirelli severity ratings, compound C-numbers) and update from practice and live laps.

**8. Overtake counts lie.** Energy yo-yo passes in 2026 inflate the numbers. Use sustained position changes. (§7.2.)

**9. Invisible information.** Public data has no battery state, no fuel load, no tyre temperatures and no damage information. Mechanical failures are invisible until they show in lap times. Post-race penalties can reorder the result (a 5-second penalty at Silverstone 2026 dropped a car seven places behind an SC-bunched field). Model these as noise and be honest about uncertainty. (Pitwall.)

**10. Heavy class imbalance in decision data.** Only about 3% of laps are pit laps. Use precision/recall/F1, not accuracy. Filter out stops for damage, penalties and (pre-2025) fastest-lap attempts. (Heilmeier et al.)

**11. Rivals react.** Open-loop rival models ignore covering. Expect undercut advice to be optimistic until you model the defender's response. (Pitwall.)

**12. Use medians for pit loss.** Disaster stops (≈ 50 s) wreck averages. (F1 Chronicle.)

**13. Guard any language/explanation layer.** If the app uses an LLM to explain recommendations, it can invent drivers, gaps and compounds when the input state is sparse. Verify every factual claim against the engine state before showing it; Pitwall found this depended on the base model's instruction-following, not its size, and that sampling temperature and aggressive quantisation made it worse. (Pitwall.)

---

## 13. Proposed app architecture and MVP roadmap

### 13.1 Architecture

```
┌────────────────┐   ┌──────────────────┐   ┌──────────────────────┐   ┌───────────────────┐
│  Ingestion      │──▶│  Race-state store │──▶│  Models               │──▶│  Strategy engine   │
│  FastF1 / Jolpica│   │  laps, stints,    │   │  lap-time + deg/cliff │   │  plan search       │
│  OpenF1 (live)   │   │  pits, SC/VSC,    │   │  pit loss (per track) │   │  Monte Carlo (CRN) │
│  Pirelli, FIA    │   │  weather, grid    │   │  SC/VSC hazard        │   │  undercut window   │
└────────────────┘   └──────────────────┘   │  overtake / dirty air │   │  bootstrap CIs     │
                                              │  live Kalman pace     │   └─────────┬─────────┘
                                              └──────────────────────┘             │
                                                                                     ▼
                                                                         ┌──────────────────────┐
                                                                         │  API + UI             │
                                                                         │  plan, probabilities, │
                                                                         │  "why" explanations   │
                                                                         └──────────────────────┘
```

### 13.2 Core data model (sketch)

| Entity | Key fields |
|---|---|
| `Circuit` | laps, length, pit speed limit, pit-loss median & clean, SC prior, VSC prior, overtake difficulty offset, dirty-air loss, nominated compounds (C-numbers), deg priors per compound, cliff knots, max-stint caps, typical track temp |
| `Session` | season, round, circuit, type (race/sprint), weather timeline, track-status timeline |
| `CarState` | driver, team, position, gap ahead/behind, compound, tyre age, stint #, compounds used, sets remaining, pace offset (+ uncertainty) |
| `Strategy` | ordered stints `[{compound, start_lap, end_lap, new_or_used}]`, legality flags |
| `SimResult` | per-strategy distribution of finish positions, P(win/podium/points), expected race time, CIs |
| `Recommendation` | option (box now / +1 / +2 / stay), target compound, P(ahead of rival), Δ vs. stay, explanation |

### 13.3 MVP roadmap

| Phase | Scope | Done when |
|---|---|---|
| **0 — Data** | FastF1 + Jolpica ETL for 2022–2026 into a local store; clean laps (flag SC/VSC, in/out laps) | Any race can be replayed lap by lap |
| **1 — Pre-race planner (no opponents)** | Fuel-corrected linear deg + cliff per circuit/compound; pit-loss priors; enumerate legal sets; optimal stint lengths; stop-count check | Recommends a legal, feasible plan; stop count matches the real modal strategy in most held-out races |
| **2 — Monte Carlo** | Add SC/VSC hazard, lap noise, pit-stop noise, retirements, dirty air, pass model; vectorise; bootstrap CIs | Calibrated P(win/podium/points) on held-out season |
| **3 — Live mode** | OpenF1 live (check licence), state reconstruction, Kalman pace filter, undercut window with CRN, SC reaction | Recommendations update each lap within seconds |
| **4 — Rivals & tactics** | Rival pull-forward under SC, covering game, team-mate tactics | Undercut advice no longer systematically optimistic |
| **5 — Weather & energy** | Crossover model with radar input; latent battery-state estimate | Handles mixed-condition races with a confidence gate |
| **6 — Explanations** | Human-readable "why" for each call, fact-checked against engine state | No unsupported claims in explanations |

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **Deg** | Tyre degradation: lap time lost per lap of tyre age |
| **Wear vs. degradation** | Wear is rubber physically lost; degradation is the broader loss of performance (including thermal) |
| **Cliff** | Tyre age after which degradation suddenly accelerates |
| **Stint** | Laps run on one set of tyres |
| **Pit loss / pit delta** | Total race time lost by making a stop |
| **In-lap / out-lap** | Lap entering the pits / first lap after leaving them |
| **Undercut / overcut** | Gaining a position by pitting earlier / later than a rival |
| **Cover** | Pitting right after a rival to neutralise their undercut |
| **FCY** | Full Course Yellow: Safety Car (SC) or Virtual Safety Car (VSC) |
| **Crossover** | Point where a different tyre type becomes faster |
| **Dirty air** | Turbulent wake that costs a following car downforce and lap time |
| **Active Aero** | 2026 movable front/rear wings: Corner Mode and Straight Mode |
| **Overtake Mode** | 2026 extra-energy aid for a car within 1 s of the car ahead |
| **Boost / Recharge** | Driver-controlled energy deployment / harvesting |
| **CRN** | Common random numbers: same random draws across compared options |
| **Brier score** | Mean squared error of probability forecasts (lower is better) |
| **VSE** | Virtual Strategy Engineer (TUM's ML strategy agent) |

---

## 15. Sources

**Research papers and code**

| Source | Link |
|---|---|
| Heilmeier et al. — Virtual Strategy Engineer (Applied Sciences, 2020) | https://www.mdpi.com/2076-3417/10/21/7805 |
| Heilmeier et al. — Monte Carlo methods in race simulation (Applied Sciences, 2020) | https://portal.fis.tum.de/en/publications/application-of-monte-carlo-methods-to-consider-probabilistic-effe/ |
| Heilmeier et al. — A Race Simulation for Strategy Decisions (IEEE ITSC, 2018) | https://doi.org/10.1109/ITSC.2018.8570012 |
| TUMFTM race-simulation repository | https://github.com/TUMFTM/race-simulation |
| Santillana — Pitwall: calibrated real-time Monte Carlo engine (arXiv, Jul 2026) | https://arxiv.org/pdf/2607.06495 |
| Thomas et al. — Explainable RL for F1 Race Strategy (ACM SAC 2025) | https://arxiv.org/abs/2501.04068 |
| Explainable time-series prediction of tyre energy (Mercedes data) | https://arxiv.org/abs/2501.04067 |
| Cappello & Hoegh — State-space tyre degradation model | https://arxiv.org/pdf/2512.00640 |
| Towards Learning-Based Formula 1 Race Strategies | https://arxiv.org/pdf/2512.21570 |
| Online Planning for F1 Race Strategy Identification (PRL 2021) | https://prl-theworkshop.github.io/prl2021/papers/PRL2021_paper_1.pdf |
| TrackShift 2026 / PITWALL tyre-degradation project | https://github.com/OptimistOtaku/trackshift-26 |

**Rules, tyres and technical context**

| Source | Link |
|---|---|
| Pirelli — 2026 compound range | https://press.pirelli.com/the-range-of-compounds-for-the-2026-season-has-been-set/ |
| Motorsport.com — Pirelli drops C6 | https://www.motorsport.com/f1/news/pirelli-sets-f1-2026-compounds-abandons-c6/10779540/ |
| GPFans — 2026 tyre dimensions (FIA) | https://www.gpfans.com/en/f1-news/1075271/pirelli-fia-f1-2026-c6-soft-tyre-dropped/ |
| Motorsport.com — Monaco two-stop rule scrapped for 2026 | https://www.motorsport.com/f1/news/monaco-scraps-mandatory-two-stop-rule-for-2026-/10801049/ |
| Motorsport.com — Pirelli on mandatory stops | https://www.motorsport.com/f1/news/two-mandatory-pitstops-in-f1-pirelli-open-minded-about-2026-rule-change-discussion/10773216/ |
| RacingNews365 — F1 rules explained (2026) | https://racingnews365.com/f1-rules-explained |
| F1.com — Beginner's guide to 2026 regulations | https://www.formula1.com/en/latest/article/the-beginners-guide-to-the-2026-regulations.6j0tS0hrHG2T01tpmK6XYz |
| The Race — Key 2026 terms explained | https://www.the-race.com/formula-1/boost-overtake-mode-active-aero-recharge-key-2026-terms-explained/ |
| ESPN — 2026 terminology and car changes | https://www.espn.com/f1/story/_/id/47333501/formula-1-f1-new-terminology-explained-overtake-mode-boost-drs-how-affects-2026-racing-drivers-regulations-rules |
| F1 Chronicle — DRS replaced by Active Aero | https://f1chronicle.com/drs-replaced-by-active-aero-2026/ |
| F1 Chronicle — 2026 fuel flow and 70 kg allowance | https://f1chronicle.com/f1-fuel-flow-2026-explained/ |
| Autosport — Q2 tyre rule removed (2022) | https://autosport.com/all/news/f1-regulations-update-confirms-removal-of-q2-tyre-rule/8313153/ |
| Pirelli — slick/intermediate/wet crossover | https://www.pirelli.com/global/en-ww/race/racingspot/formula-1/when-it-s-time-to-change-from-slick-to-wet-tyres-in-formula-1-52943/ |
| F1-Fansite — Intermediates glossary | https://www.f1-fansite.com/glossary/intermediates/ |
| f1thedata.com — Rules quick reference | https://f1thedata.com/rules |
| F1pedia — 2026 Sporting Regulations summary | https://f1pedia.com/en/encyclopedia/regulations/2026/sporting |

**Strategy data and analysis**

| Source | Link |
|---|---|
| F1 Chronicle — Pit-stop time loss data (2,106 stops) | https://f1chronicle.com/f1-pit-stop-time-loss-data/ |
| F1 Chronicle — 2026 tyre degradation data | https://f1chronicle.com/2026-f1-tyre-degradation-data/ |
| Catapult — How tyre degradation impacts strategy | https://www.catapult.com/blog/how-tyre-degradation-affects-race-strategy |
| Autosport — Tyre saving explained | https://www.autosport.com/f1/news/f1-tyre-saving-what-why-how-is-it-done/10535074/ |
| thef1db — Pit stop strategy explainer | https://thef1db.com/blog/f1-pit-stop-strategy-explainer |
| SimRacing Pro — Undercut vs. overcut | https://simracing-pro.com/what-is-undercut-and-overcut/ |
| Grand Prix Pal — Compounds, undercut, overcut | https://www.grandprixpal.com/blog/f1-tyre-compounds-undercut-overcut-explained |
| The Motorsport Metrics — Fuel load and lap time | https://themotorsportmetrics.com/fuel-load-and-lap-time/ |
| F1BetUK — Safety car probability by circuit | https://f1betuk.com/articles/f1-safety-car-betting-circuit-data/ |
| Crash.net — Focus: the F1 Safety Car | https://www.crash.net/f1/feature/177814/1/focus-the-f1-safety-car |
| Motor Sport Magazine — Why overtake counts mislead | https://www.motorsportmagazine.com/articles/single-seaters/f1/why-f1s-fixation-on-overtaking-is-flawed/ |
| The Race — Problems with 2026 overtaking stats | https://www.the-race.com/formula-1/f1-overtaking-2026-big-increase-two-problems/ |
| Silverstone — Overtake Mode explained | https://www.silverstone.co.uk/news/overtake-mode-explained-f101-beginners-guide-f1s-new-overtaking-aid |

**Data**

| Source | Link |
|---|---|
| FastF1 docs | https://docs.fastf1.dev |
| Jolpica-F1 | https://github.com/jolpica/jolpica-f1 |
| OpenF1 | https://openf1.org |
| awesome-f1 | https://github.com/subinium/awesome-f1 |

---

## 16. Open questions / to verify

1. Exact 2026 dry/intermediate/wet **tyre set allocation** per weekend, and sprint-weekend allocation (check FIA Sporting Regulations).
2. Current **red-flag tyre-change** rule wording and interaction with the two-compound requirement.
3. Exact 2026 **minimum car weight** (sources quote 768 and 770 kg).
4. Full-season 2026 degradation and pit-loss tables (the figures here are mid-season; F1 Chronicle excluded Barcelona from its deg table pending investigation).
5. Per-circuit **SC/VSC rates** recomputed from race-control data rather than betting-site summaries.
6. Whether **battery state** can be inferred reliably from public speed-trap and mini-sector data.
7. **Commercial licensing** of live timing data if the app is ever monetised.
8. Whether the paddock-wide shift to one-stop races in 2026 prompts rule changes (e.g. pit-lane speed changes or mandatory stops) later in the season or for 2027.
