---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
pillars:
  - "Every replay is byte-identical given the seed"
  - "Decisions happen before the combat starts, not during"
  - "A tick is sub-second; an encounter is under a minute"
non_goals:
  - "Real-time player input during combat"
  - "Multiplayer"
  - "Procedurally-named units (every unit is hand-designed)"
---

## Tokens

See frontmatter. Pillars and non-goals are immutable for the project's life.

## Rationale

**Determinism.** Given the same seed and the same setup, the encounter must produce byte-identical state at every tick. This isn't a flavor goal — it's a contract that downstream features (replay sharing, balance regression tests, the verify adapter) all depend on. See `{invariants.deterministic_given_seed}`.

**Front-loaded decisions.** Auto-battlers fail when the player has nothing to do after setup. Lockstep keeps the player honest by making setup the *whole* game: 60 seconds of placement, 60 seconds of watching, and a verdict.

**Sub-minute encounters.** Median target is ~120 ticks at 100ms = 12 wall-clock seconds; encounter floor is 30s, ceiling 90s. Anything longer breaks the "20 encounters in a 20-minute campaign" promise.
