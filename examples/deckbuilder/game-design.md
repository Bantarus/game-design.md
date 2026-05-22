---
spec: game-design.md
spec_version: 0.1.1
file_type: core
name: "Ember Ascent"
short_pitch: "A 30-minute deckbuilder roguelike where every turn you reshape a hand of fire to climb a collapsing volcano."
genre_tags: [deckbuilder, roguelike, single-player]
status: draft
version: 0.4.2
last_updated: "2026-05-21"
target_platforms_neutral: [desktop, handheld]
pillars:
  - "Every turn, a meaningful hand-shape decision"
  - "Synergy between burn and bellow is discoverable, not memorizable"
  - "A run is short enough to finish on a lunch break"
non_goals:
  - "Multiplayer"
  - "Real-time combat"
  - "Persistent meta-progression unlocks (the run is the meta)"
player_experience_goals:
  primary: [challenge, expression]
  secondary: [discovery]
  explicit_non_goals: [submission, fellowship]
core_loop_ref: "{loops.combat_turn}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  combat:                  gdd/systems/combat.md
  progression:             gdd/systems/progression.md
  economy_balance:         gdd/economy-balance.md
  feel:                    gdd/feel.md
  verification:            gdd/verification.md
  glossary:                gdd/glossary.md
  content_index:           gdd/content/_index.md
  cards:                   gdd/content/cards.md
  enemies:                 gdd/content/enemies.md
implementation_pointers:
  combat_loop: "src/ember_ascent/combat/**/*.py"
  card_system: "src/ember_ascent/cards/**/*.py"
  rng:         "src/ember_ascent/rng/**/*.py"
  states:      "src/ember_ascent/states/**/*.py"
---

# Ember Ascent

> A 30-minute deckbuilder roguelike where every turn you reshape a hand of fire to climb a collapsing volcano.

## High Concept

You are a salamander rider climbing a collapsing volcano. The deck is your breath: every card is a way of *shaping fire*. The interesting decisions are not "which card is best" but "which hand-shape do I sculpt this turn from what I drew." Each run is ~30 minutes, fully deterministic given the seed, and ends when you reach the caldera (win), die (lose), or stop the collapse early via a rare scripted event.

## Pillars & Non-Goals

Three pillars, three non-goals (see frontmatter). Both lists are immutable for the life of the project under the v0.1.1 stability guarantee (§8 of `docs/spec.md`). The non-goals are listed because every comparable game is tempted into them; this one refuses.

## Player Experience Goals

The MDA aesthetics in the frontmatter: **challenge** and **expression** are primary; **discovery** is secondary. **Submission** (zone-out play) and **fellowship** (social play) are explicit non-goals — Ember Ascent is meant to make you think hard for thirty minutes, alone.

## Core Gameplay Loop

The core loop is `{loops.combat_turn}` — a ~45-second moment loop of *draw → play → end turn*. Three loops nest at three timescales: `{loops.combat_turn}` inside `{loops.encounter}` inside `{loops.run}`. See `gdd/loops.md` for the full machinery and `gdd/economy-balance.md` for the numbers that make a turn feel like a turn.

## Universal Surface

The full design surface lives in subfiles, linked via the `files:` map above. The agent's reading order from a cold context:

1. `gdd/pillars.md` — the three immutable principles.
2. `gdd/loops.md` — the three nested loops.
3. `gdd/mechanics.md` — entities, verbs, resources, states.
4. `gdd/architecture-invariants.md` — codebase contract the agent must respect (engine-neutral).
5. `gdd/content/cards.md` + one example from `content/cards/*.yaml` — enough to implement a new card.

`gdd/systems/*`, `gdd/feel.md`, `gdd/economy-balance.md` are pulled on demand. `gdd/verification.md` is for the dynamic loop; ignore it until balance work.

## How to Use This Document (for the Agent)

- **YAML is normative.** Compile against tokens; prose is rationale.
- **Tokens win on conflict.** If numbers in `gdd/economy-balance.md` disagree with prose anywhere, the numbers are correct.
- **Distributions are named.** Never invent ad-hoc randomness — every roll resolves through `{distributions.<id>}`.
- **Invariants are contracts.** Before writing code that touches damage, state, or RNG, read `gdd/architecture-invariants.md`. Those invariants are how the design tells you which assumptions the code must satisfy.
- **Use the `files:` map for navigation.** Don't pull every subfile into context — open only what the task needs.

## Glossary

See `gdd/glossary.md`.
