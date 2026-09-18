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
