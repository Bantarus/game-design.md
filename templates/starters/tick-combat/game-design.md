---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: "Untitled Auto-Battler"
short_pitch: "A short pitch for your auto-battler — one sentence, ≤280 chars."
genre_tags: [auto-battler, tick-combat, single-player]
status: draft
version: 0.1.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop, mobile]
pillars:
  - "Pillar 1 — the deployment decision that determines the fight"
  - "Pillar 2 — the synergy or counter that rewards reading the enemy roster"
  - "Pillar 3 — the constraint that keeps single fights short and replayable"
non_goals:
  - "Direct player control of units during combat"
player_experience_goals:
  primary: [challenge, expression]
  secondary: [discovery]
core_loop_ref: "{loops.tick}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  clocks:                  gdd/clocks.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  economy_balance:         gdd/economy-balance.md
  content_index:           gdd/content/_index.md
  units:                   gdd/content/units.md
---

# Untitled Auto-Battler

> A short pitch for your auto-battler — one sentence, ≤280 chars.

<!--
STARTER NOTE — delete this comment block once you've made the tree your own.

Descriptive scaffold extracted from the canonical tick-combat example
(examples/tick-combat/). Not a prescriptive contract — delete what doesn't
fit, rename what does. Lint-clean as-is.

Carries forward from the canonical tick-combat:
- A `clocks:` namespace (F-010 v0.3 closure) with a `tick` continuous clock
  driving the combat resolution. The tick clock IS the moment loop — the
  loop's `clock:` field references it, the `sequence:` is empty.
- A `deployed_units` instance_container (F-008 v0.3) — each deployed unit is
  an instance carrying per-instance hp and lifecycle state.
- Three distinct rule firing modes: clock-driven (tick_resolution),
  verb-driven (start_combat / resolve_match).
- Cross-engine determinism contract: `prng:` pinned + reference vectors.

This starter has more vocabulary than the others because tick-combat is
where F-010 + F-008 + their interactions land most heavily.
-->

## High Concept

State the premise in 2-4 sentences. What's the deployment decision space?
What makes one roster beat another?

## Pillars & Non-Goals

The three pillars are immutable for the life of the project.

## Player Experience Goals

`challenge` + `expression` with `discovery` secondary is the auto-battler
norm — discoverable synergies via experimentation.

## Core Gameplay Loop

`{loops.tick}` — the per-tick moment loop driven by `{clocks.tick}`. See
`gdd/clocks.md` for the clock + `gdd/loops.md` for the loop. The
`{loops.match}` loop brackets one fight from deployment to resolution.

## How to Use This Document (for the Agent)

- The clock IS the moment loop. Time-driven rules attach to it via
  `given.driver: "{clocks.tick}"`; player verbs (deployment) drive the
  meta phase but not the in-fight resolution.
- Per-unit runtime state lives in `entities.deployed_units.per_instance_state`.
- All randomness named in `gdd/systems/distributions.md`.
