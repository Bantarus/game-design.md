---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: Lanternfall
short_pitch: "A dungeon crawler where your lantern's oil is the clock: descend, fight what the light reveals, and climb out before the flame gutters."
genre_tags: ["dungeon-crawler", rpg, "single-player"]
status: draft
version: 0.3.1
last_updated: "2026-04-24"
target_platforms_neutral: [desktop, handheld]
pillars:
  - Light is the only currency that matters
  - Every floor is a readable risk
  - Loot tells you what the dark is hiding
non_goals:
  - Multiplayer
  - Real-time twitch combat
  - Procedural narrative
player_experience_goals:
  primary: [challenge, discovery]
  secondary: [fantasy]
  explicit_non_goals: [fellowship]
core_loop_ref: "{loops.delve_turn}"
files:
  pillars: gdd/pillars.md
  loops: gdd/loops.md
  clocks: gdd/clocks.md
  mechanics: gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions: gdd/systems/distributions.md
  spawning: gdd/systems/spawning.md
  bosses: gdd/systems/bosses.md
  loot: gdd/systems/loot.md
  combat: gdd/systems/combat.md
  lantern: gdd/systems/lantern.md
  economy_balance: gdd/economy-balance.md
  feel: gdd/feel.md
  glossary: gdd/glossary.md
  content_index: gdd/content/_index.md
  items: gdd/content/items.md
  skills: gdd/content/skills.md
  monsters: gdd/content/monsters.md
  encounters: gdd/content/encounters.md
implementation_pointers:
  loot: "impl/lanternfall/loot/**/*.py"
  lantern: "impl/lanternfall/lantern/**/*.py"
  combat: "impl/lanternfall/combat/**/*.py"
  rng: "impl/lanternfall/rng/**/*.py"
---

# Lanternfall

> A dungeon crawler where your lantern's oil is the clock: descend, fight what the light reveals, and climb out before the flame gutters.

## High Concept

You are a lamplighter descending the Lanternfall catacombs. Every action burns oil from a single lantern; when it gutters, the expedition is over. Monsters, loot and bosses are authored content, a few hundred entries deep, and the interesting decision is always the same one: how much light is this worth?

## Pillars & Non-Goals

Three pillars and three non-goals (see frontmatter), immutable for the life of the project.

## Player Experience Goals

Challenge and discovery are primary; fantasy is secondary. Fellowship is an explicit non-goal: Lanternfall is a solitary descent.

## Core Gameplay Loop

The core loop is `{loops.delve_turn}`: strike, invoke a skill or use a relic, and watch the oil. It nests inside `{loops.floor_sweep}` and `{loops.expedition}`. See `gdd/loops.md`.

## Universal Surface

The design lives in subfiles, linked through the `files:` map. Content is external: 140 items, 90 skills, 60 monsters and 30 encounters under `content/<kind>/*.yaml`, each kind described by `gdd/content/<kind>.md`. Rules are split by system under `gdd/systems/`.

## How to Use This Document (for the Agent)

- **YAML is normative.** Token values are the truth; prose is rationale.
- **Content references are values.** A monster's `drops:` and `skills:`, an item's `grants:`, a skill's `roll:` and an encounter's `monsters:` are token references like any other.
- **Use the `files:` map.** Open only the subfiles a task needs.

## Glossary

See `gdd/glossary.md`.
