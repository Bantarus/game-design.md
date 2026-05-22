---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: core
name: "Lockstep"
short_pitch: "A fixed-seed auto-battler: assemble a 5-unit squad, lock the formation, watch the tick."
genre_tags: [auto-battler, tactics, single-player]
status: prototyped
version: 0.2.0-alpha
last_updated: "2026-05-22"
target_platforms_neutral: [desktop, web]
pillars:
  - "Every replay is byte-identical given the seed"
  - "Decisions happen before the combat starts, not during"
  - "A tick is sub-second; an encounter is under a minute"
non_goals:
  - "Real-time player input during combat"
  - "Multiplayer"
  - "Procedurally-named units (every unit is hand-designed)"
player_experience_goals:
  primary: [challenge, expression]
  secondary: [discovery]
  explicit_non_goals: [submission, sensation]
core_loop_ref: "{loops.tick}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  economy_balance:         gdd/economy-balance.md
  verification:            gdd/verification.md
  content_index:           gdd/content/_index.md
  units:                   gdd/content/units.md
  encounters:              gdd/content/encounters.md   # Phase-2.5: resolves ambiguity #7
implementation_pointers:
  engine_a_xtreme: "impl/xtreme/src/**/*.rs"
  cargo_manifest:  "impl/xtreme/Cargo.toml"
---

# Lockstep

> A fixed-seed auto-battler: assemble a 5-unit squad, lock the formation, watch the tick.

## High Concept

A round of Lockstep is two squads, a hex grid, and ~120 ticks. The player makes every meaningful decision in the **setup** phase — what units to deploy, where to place them, which formation buffs to stack — and then watches the **ticking** phase resolve deterministically. The hook is *seed-shareable replays*: every encounter is byte-identical given the seed, so a player can hand-craft a challenge ("solve this with these units") and the solution travels.

## Pillars & Non-Goals

Three pillars (frontmatter) lock the design's character: deterministic replays, decisions front-loaded, sub-minute encounters. Three non-goals (frontmatter) name the failure modes adjacent games drift into.

## Player Experience Goals

**Challenge** and **expression** are primary — the puzzle of fitting a formation to a known enemy squad. **Discovery** is secondary (unit-combo synergies). **Submission** (zone-out auto-play) is explicitly out: the player must *finish* a setup before combat starts.

## Core Gameplay Loop

The core loop is `{loops.tick}` — a ~0.1-second moment loop driven by `{verbs.advance_tick}`. Three loops nest: `{loops.tick}` inside `{loops.encounter}` inside `{loops.campaign}`. See `gdd/loops.md`.

## Universal Surface

The full surface lives in the subfiles linked via the `files:` map above. Agent reading order from cold context:

1. `gdd/pillars.md`
2. `gdd/loops.md`
3. `gdd/mechanics.md`
4. `gdd/architecture-invariants.md` — note `{invariants.deterministic_given_seed}` is load-bearing.
5. `gdd/content/units.md` + one example from `content/units/*.yaml`.

## How to Use This Document (for the Agent)

- **YAML is normative.** Tokens compile-against; prose explains why.
- **Distributions are named.** `{distributions.action_order}` is `deterministic` on purpose — the rule of "highest speed first, tie-break by deployment order" *is* the distribution.
- **Tick-time integer.** Damage and HP resolve to integers (`{invariants.gameplay_state_is_integer}`); the gaussian damage roll rounds at apply.

## Glossary

- **Tick.** One discrete combat step (~100ms wall-clock). One unit acts per tick.
- **Formation.** The spatial arrangement of deployed units on the hex grid; affects flanking bonuses.
- **Lockstep.** The contract: given the seed, two players observing the same encounter see the same outcome at the same tick.
