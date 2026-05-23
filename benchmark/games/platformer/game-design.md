---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: core
name: "Embergrave"
short_pitch: "A precision platformer where you pilot a moth through dark vertical caves, navigating by your own dimming ember."
genre_tags: [platformer, precision, single-player]
status: draft
version: 0.1.0
last_updated: 2026-05-23
target_platforms_neutral: [desktop, handheld]
pillars:
  - "Every jump is a commitment; hesitation dims the ember"
  - "The cave is the puzzle; light is the lens"
  - "Death is cheap; progress is sticky"
non_goals:
  - "Multiplayer"
  - "Procedural level generation"
  - "Combat"
  - "Story-driven cutscenes"
player_experience_goals:
  primary: [sensation, challenge]
  secondary: [discovery]
  explicit_non_goals: [fellowship, narrative, submission]
core_loop_ref: "{loops.flight}"
files:
  pillars: gdd/pillars.md
  loops: gdd/loops.md
  mechanics: gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  economy_balance: gdd/economy-balance.md
  distributions: gdd/systems/distributions.md
  physics: gdd/systems/physics.md
  feel: gdd/feel.md
  levels: gdd/content/levels.md
implementation_pointers:
  movement: "src/embergrave/movement/**/*"
  physics: "src/embergrave/physics/**/*"
  levels: "src/embergrave/levels/**/*"
  ember: "src/embergrave/ember/**/*"
---

# Embergrave

> A precision platformer where you pilot a moth through dark vertical caves, navigating by your own dimming ember.

## High Concept

You are a moth, palm-sized, drawn to dying light. The world is a single collapsing volcano shaft, lit only by the ember you carry — and only as long as you keep moving. Hesitate, and the ember dims; dim too far, and you cannot see the next ledge. Each level is a single tight cave segment, hand-crafted, ~3 minutes target. Death sends you to the last checkpoint instantly. Across ~40 levels spanning four regions you climb from the lava-flooded base to the summit. No combat. No NPCs. The cave is the entire game, and the moth's six-frame jump arc is the entire vocabulary.

## Pillars & Non-Goals

Three pillars, four non-goals (see frontmatter). Both lists are immutable for the life of the project. The non-goals are listed because every comparable game is tempted into them; this one refuses. Combat is the loudest refusal — most platformers grow combat as a difficulty escalator; Embergrave grows it through traversal geometry alone.

## Player Experience Goals

MDA aesthetics: **sensation** (kinesthetic precision of input-to-motion-to-light) and **challenge** (difficulty-of-mastery) are primary; **discovery** (route variants, hidden embers) is secondary. **Submission** (zone-out auto-play), **fellowship** (social), and **narrative** (story-driven) are explicit non-goals — Embergrave is meant to be played with full attention, alone, with nothing happening in the negative space.

## Core Gameplay Loop

The core loop is `{loops.flight}` — the moment-to-moment per-frame input/physics/state loop, roughly 5–10 seconds per traversal attempt before the moth dies or reaches a checkpoint. Three loops nest at three timescales: `{loops.flight}` inside `{loops.level}` inside `{loops.expedition}`. See `gdd/loops.md` for the full machinery and `gdd/economy-balance.md` for the numbers that make the difficulty curve.

## Universal Surface

The full design surface lives in subfiles, linked via the `files:` map above. The agent's reading order from a cold context:

1. `gdd/pillars.md` — the three immutable principles.
2. `gdd/loops.md` — the three nested loops.
3. `gdd/mechanics.md` — entities, verbs, resources, states, events.
4. `gdd/architecture-invariants.md` — codebase contract the agent must respect.
5. `gdd/content/levels.md` + one example from `content/levels/*.yaml` — enough to implement a new level.

`gdd/feel.md`, `gdd/systems/distributions.md`, `gdd/economy-balance.md` are pulled on demand.

## How to Use This Document (for the Agent)

- **YAML is normative.** Compile against tokens; prose is rationale.
- **Tokens win on conflict.** If numbers in `gdd/economy-balance.md` disagree with prose anywhere, the numbers are correct.
- **Distributions are minimal and named.** Embergrave has almost no gameplay RNG — the platformer's commitment to precision means every outcome must be deterministic from input. The one declared distribution (`{distributions.ember_flicker_jitter}`) is cosmetic-only. Never invent ad-hoc randomness in the simulation layer.
- **Invariants are contracts.** Before writing code that touches physics, position, or simulation state, read `gdd/architecture-invariants.md`. Fixed-point integer state and fixed-timestep simulation are the load-bearing invariants — see `{invariants.fixed_point_simulation_state}` and `{invariants.fixed_timestep_simulation}`.
- **Use the `files:` map for navigation.** Don't pull every subfile into context — open only what the task needs. The full set of ~40 level YAML files in `content/levels/` is browsed on demand; the schema in `gdd/content/levels.md` plus one example is enough for most new-level authoring.

## Glossary

- **Ember** — the moth's light source AND the player's mobility resource. Depletes during airborne maneuvers; refills via collected ember pickups in-level.
- **Checkpoint** — a position in a level where the moth respawns on death. Levels carry 1–5 checkpoints; checkpoint count is a balance lever for difficulty.
- **Region** — a thematic group of levels sharing visual palette and mechanical emphasis. The four regions in order: caverns, fault lines, hot springs, summit.
- **Flight** — the moment-loop term for one continuous attempt from spawn (or checkpoint) to death or next checkpoint. Typical flight: 5–10 seconds.
- **Tier** — per-level difficulty integer, 1 (introductory) to 5 (post-summit). Distinct from region.
