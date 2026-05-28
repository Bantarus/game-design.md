---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: "Untitled Survival"
short_pitch: "A short pitch for your action-economy survival game — one sentence, ≤280 chars."
genre_tags: [survival, crafting, single-player]
status: draft
version: 0.1.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop]
pillars:
  - "Pillar 1 — the time-investment decision the player makes each action"
  - "Pillar 2 — the inventory/crafting decision that compounds over time"
  - "Pillar 3 — the survival constraint that gives meaning to time itself"
non_goals:
  - "Combat as the primary mechanic"
player_experience_goals:
  primary: [challenge, discovery]
  secondary: [expression]
core_loop_ref: "{loops.action}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  clocks:                  gdd/clocks.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  economy_balance:         gdd/economy-balance.md
  content_index:           gdd/content/_index.md
  recipes:                 gdd/content/recipes.md
---

# Untitled Survival

> A short pitch for your action-economy survival game — one sentence, ≤280 chars.

<!--
STARTER NOTE — delete this comment block once you've made the tree your own.

Descriptive scaffold extracted from the canonical survival example
(benchmark/games/survival/, "Driftwood"). Not a prescriptive contract —
delete what doesn't fit. Lint-clean as-is.

Carries forward from the canonical survival:
- A `clocks:` namespace (F-010 v0.3) with a `world_time` clock in
  `per_verb_delta` mode — each player action advances world time by an
  amount declared on the verb's `time_cost.in_game_minutes`. Driftwood was
  the canonical case for `per_verb_delta` mode.
- An `inventory` instance_container (F-008 v0.3) — N owned item instances,
  each with per-instance durability + quantity + charges.
- A `recipes` content_collection for crafting.

This starter exercises BOTH F-008 and F-010 closures — the combination is
what makes action-economy survival games tractable in the spec.
-->

## High Concept

State the premise in 2-4 sentences. What's the survival pressure? What's the
crafting depth? What makes time investment feel meaningful?

## Pillars & Non-Goals

The three pillars are immutable for the life of the project.

## Player Experience Goals

`challenge` + `discovery` is the survival/crafting pairing — you survive AND
you discover what's possible.

## Core Gameplay Loop

`{loops.action}` — the per-action moment loop. Each action advances the
`{clocks.world_time}` clock by the action's declared time cost. The
`{loops.day_cycle}` session loop is the day/night rhythm.

## How to Use This Document (for the Agent)

- Each verb declares its `time_cost.in_game_minutes` — the world clock reads
  this value at apply-time per spec §3 (D-012 + F-010 binding).
- Inventory items are instances with per-instance durability + quantity.
- Distributions are named — gathering yields, weather, hazards all reference
  named distributions.
