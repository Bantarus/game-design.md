---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: "Untitled Platformer"
short_pitch: "A short pitch for your real-time platformer — one sentence, ≤280 chars."
genre_tags: [platformer, precision, single-player]
status: draft
version: 0.1.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop, handheld]
pillars:
  - "Pillar 1 — the moment-to-moment movement that defines feel"
  - "Pillar 2 — the level-shape decision the level designer makes per screen"
  - "Pillar 3 — the constraint that keeps replayability high (death loop, time attack, etc.)"
non_goals:
  - "Turn-based combat"
player_experience_goals:
  primary: [challenge, sensation]
  secondary: [expression]
core_loop_ref: "{loops.physics_step}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  clocks:                  gdd/clocks.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  economy_balance:         gdd/economy-balance.md
  content_index:           gdd/content/_index.md
  levels:                  gdd/content/levels.md
---

# Untitled Platformer

> A short pitch for your real-time platformer — one sentence, ≤280 chars.

<!--
STARTER NOTE — delete this comment block once you've made the tree your own.

Descriptive scaffold extracted from the canonical platformer example
(benchmark/games/platformer/, "Embergrave"). Not a prescriptive contract —
delete what doesn't fit. Lint-clean as-is.

Carries forward from the canonical platformer:
- A `clocks:` namespace with a `physics` continuous clock at fixed timestep
  (F-010 v0.3 closure; Embergrave is one of the three trees that drove F-010).
- Real-time movement verbs (move, jump, dash) — player input drives intent,
  but time and physics advance regardless.
- A levels content_collection — each level is a static level design.

Does NOT carry:
- `instance_container:` — the canonical platformer doesn't need it (the
  player is a single actor; level entities are level-defined static placements,
  not instances with template-shared schema).
-->

## High Concept

State the premise in 2-4 sentences. What's the movement vocabulary? What
defines "feel" in this game?

## Pillars & Non-Goals

The three pillars are immutable for the life of the project.

## Player Experience Goals

`challenge` + `sensation` is the precision-platformer pairing — hard inputs
that feel good to land.

## Core Gameplay Loop

`{loops.physics_step}` — the per-frame moment loop driven by `{clocks.physics}`.
The `{loops.level_attempt}` session loop is one attempt at a level from start
to death-or-clear.

## How to Use This Document (for the Agent)

- YAML is normative; prose is rationale.
- Physics is clock-driven. Player input is sampled per-frame; the actual
  position/velocity updates happen in the physics tick.
- Distributions are named — even cosmetic jitter (particle directions, hazard
  variation) should use named distributions for replay determinism.
