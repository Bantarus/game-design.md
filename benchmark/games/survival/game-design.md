---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: core
name: "Driftwood"
short_pitch: "A 30-minute survival game about shipwreck on a small island: gather, craft, build the signal pyre, get rescued."
genre_tags: [survival, crafting, single-player]
status: draft
version: 0.2.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop, handheld]
pillars:
  - "The graph is the game"
  - "Time pressure, not difficulty pressure"
  - "A real island, not a procedurally-generated one"
non_goals:
  - "Combat"
  - "Procedural generation"
  - "Metagame progression across runs"
  - "Multiplayer"
player_experience_goals:
  primary: [challenge, expression]
  secondary: [discovery]
  explicit_non_goals: [fellowship, submission, narrative]
core_loop_ref: "{loops.day}"
files:
  pillars: gdd/pillars.md
  loops: gdd/loops.md
  clocks: gdd/clocks.md
  mechanics: gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  economy_balance: gdd/economy-balance.md
  distributions: gdd/systems/distributions.md
  world_time: gdd/systems/world_time.md
  feel: gdd/feel.md
  recipes: gdd/content/recipes.md
implementation_pointers:
  world: "src/driftwood/world/**/*"
  recipes: "src/driftwood/recipes/**/*"
  inventory: "src/driftwood/inventory/**/*"
  time: "src/driftwood/time/**/*"
---

# Driftwood

> A 30-minute survival game about shipwreck on a small island: gather, craft, build the signal pyre, get rescued.

## High Concept

You wake up on a beach with a belt knife and a cabin trunk. A rescue ship's route passes the island's signal point every five days. The whole game is the next five in-game days — six minutes of wall-clock per day, thirty minutes per run — during which you gather wood, stone, fiber, and flint; craft tools and crafting stations along a recipe tree; and assemble + light the signal pyre at the island's high point by sunset on Day 5. No combat, no story-driven moments, no procedural generation, no metagame progression — the same hand-authored island every run, with the player's only carry-over being knowledge of where things are.

## Pillars & Non-Goals

Three pillars, four non-goals (see frontmatter). The pillars are immutable for the life of the project. **The graph is the game** captures the core fantasy: reasoning about the recipe dependency tree is the player's actual gameplay. **Time pressure, not difficulty pressure** distinguishes this from action-survival genres — there are no enemies and no skill challenges; the entire challenge is that the five-day deadline does not give you slack for inefficient routes. **A real island** rejects the procedural-generation default of the survival genre: the island is hand-designed and learning it pays off across runs.

## Player Experience Goals

MDA aesthetics: **challenge** (route-planning under deadline) and **expression** (the player's plan IS their gameplay — which recipes to prioritize in which order is their authored solution) are primary; **discovery** (learning the island's geography across runs) is secondary. **Submission**, **fellowship**, and **narrative** are explicit non-goals — Driftwood is meant to be played with full attention, alone, with no story beats interrupting the planning.

## Core Gameplay Loop

The core loop is `{loops.day}` — the in-game day, ~6 minutes wall-clock, where the player executes a planned sequence of actions (gather → craft → eat → sleep) against the day's day-part timer. Three loops nest at three timescales: `{loops.action}` inside `{loops.day}` inside `{loops.run}`. See `gdd/loops.md` for the full machinery and `gdd/economy-balance.md` for the numbers that make the deadline genuinely tight.

## Universal Surface

The full design surface lives in subfiles, linked via the `files:` map above. The agent's reading order from a cold context:

1. `gdd/pillars.md` — the three immutable principles.
2. `gdd/loops.md` — the three nested loops, including the in-game day rhythm.
3. `gdd/mechanics.md` — entities, verbs, resources, states, events.
4. `gdd/architecture-invariants.md` — codebase contract the agent must respect.
5. `gdd/content/recipes.md` + one example from `content/recipes/*.yaml` — enough to implement a new recipe.

`gdd/systems/world_time.md` (day-rhythm subsystem), `gdd/systems/distributions.md` (minimal RNG surface), `gdd/feel.md`, and `gdd/economy-balance.md` are pulled on demand.

## How to Use This Document (for the Agent)

- **YAML is normative.** Compile against tokens; prose is rationale.
- **Tokens win on conflict.** If numbers in `gdd/economy-balance.md` disagree with prose anywhere, the numbers are correct.
- **Distributions are minimal.** Driftwood is a low-RNG survival game: gathering yields are deterministic per node, recipes have no failure chance, fishing always yields the same catch. The one declared distribution (`{distributions.berry_bush_renewal_offset}`) is for staggering berry-bush renewal across the island's six bushes; it does not affect any single bush's yield.
- **Recipes are data, not code.** The full recipe set lives in `content/recipes/*.yaml`. A new recipe is authored as one YAML file conforming to the schema in `gdd/content/recipes.md` — no Python (or whatever) needed.
- **Invariants are contracts.** Before writing code that touches inventory, world state, save/load, or the day timer, read `gdd/architecture-invariants.md`. Integer-only resource quantities, decoupled in-game vs. wall-clock time, and lossless save round-trip are the load-bearing invariants.
- **Use the `files:` map for navigation.** Don't pull every subfile into context — open only what the task needs.

## Glossary

- **Day-part** — one of `morning | afternoon | evening | night`. The in-game day is divided into these four parts; verbs are restricted by part (sleep only at night, fishing tidepools only at low tide which lines up with morning, etc.).
- **In-game hour** — the unit of meter decay. There are 24 in-game hours per day, ~15 wall-clock seconds per in-game hour.
- **Recipe** — a fixed (inputs → output) transformation. Each recipe is one YAML file in `content/recipes/`; recipes are immutable at runtime.
- **Crafting station** — a built world object (campfire, sawhorse, still) that is the *site* of certain recipes. The station itself is built via a recipe; subsequent recipes that require it can only be invoked when the player is adjacent.
- **Pyre** — the signal pyre; the win-condition craftable, assembled at the island's high point and lit at sunset on Day 5.
- **Run** — one playthrough, ~30 wall-clock minutes, five in-game days. A run resets on death or on rescue; no progression carries to the next run except player knowledge.
