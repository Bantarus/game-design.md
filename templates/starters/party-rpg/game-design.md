---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: "Untitled Party RPG"
short_pitch: "A short pitch for your party RPG — one sentence, ≤280 chars."
genre_tags: [rpg, party, turn-based, single-player]
status: draft
version: 0.1.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop, handheld]
pillars:
  - "Pillar 1 — the party-composition decision that shapes every encounter"
  - "Pillar 2 — the long-arc progression that rewards investment"
  - "Pillar 3 — the constraint that keeps encounters tactical, not formulaic"
non_goals:
  - "Real-time combat"
player_experience_goals:
  primary: [challenge, expression]
  secondary: [narrative]
core_loop_ref: "{loops.combat_round}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  economy_balance:         gdd/economy-balance.md
  content_index:           gdd/content/_index.md
  items:                   gdd/content/items.md
---

# Untitled Party RPG

> A short pitch for your party RPG — one sentence, ≤280 chars.

<!--
STARTER NOTE — delete this comment block once you've made the tree your own.

Descriptive scaffold extracted from the canonical party-rpg example
(examples/party-rpg/). Not a prescriptive contract — delete what doesn't fit,
rename what does, add what's missing. Lint-clean as-is.

Carries forward from the canonical party-rpg:
- A `party_members` instance_container — N owned hero instances each with
  per-instance hp/mp/equipment, drawn from a `heroes` template collection
  (F-008 v0.3 closure; the canonical case that drove the resolution).
- Turn-based round loop + encounter loop.
- Resources at the per-hero level (per_instance_state), not party-wide.
- Items as a content_collection of templates.

Does NOT carry:
- `clocks:` namespace — party RPGs are turn-driven; if your game uses real-time
  with pause (ATB / CTB systems), add a clock with `mode: continuous`.
-->

## High Concept

State the game's premise in 2-4 sentences. What's the party doing? What's the
decision space each round? What gives encounters their texture beyond optimal
play?

## Pillars & Non-Goals

The three pillars in the frontmatter are immutable for the life of the project.

## Player Experience Goals

`challenge` + `expression` with `narrative` secondary is a common party-RPG
pairing; adjust to fit your design intent.

## Core Gameplay Loop

`{loops.combat_round}` — see `gdd/loops.md`. The round loop is the moment loop;
`{loops.encounter}` is the session loop. Add a `campaign` meta loop when you
author the meta progression.

## How to Use This Document (for the Agent)

- YAML is normative; prose is rationale.
- Per-hero state lives in `entities.party_members.per_instance_state`
  (F-008 v0.3 binding). The hero TEMPLATE is read via `holds_template_from`.
- Distributions are named — every roll resolves through `{distributions.<id>}`.
