# Backlog

Ideas and scope creep deferred during Phase 1, per CLAUDE.md rule 12 ("don't expand scope — put
ideas here instead"). Nothing here should be built until its milestone (see
`docs/f1-strategy-foundation.md` §9) is reached.

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
