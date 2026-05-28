---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: "Untitled Deckbuilder"
short_pitch: "A short pitch for your deckbuilder — one sentence, ≤280 chars."
genre_tags: [deckbuilder, single-player]
status: draft
version: 0.1.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop]
pillars:
  - "Pillar 1 — the core decision the game asks every minute"
  - "Pillar 2 — the synergy or system that rewards investment"
  - "Pillar 3 — the constraint that keeps runs short and replayable"
non_goals:
  - "Multiplayer (or any other thing this game explicitly refuses)"
player_experience_goals:
  primary: [challenge, expression]
  secondary: [discovery]
core_loop_ref: "{loops.combat_turn}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  economy_balance:         gdd/economy-balance.md
  content_index:           gdd/content/_index.md
  cards:                   gdd/content/cards.md
---

# Untitled Deckbuilder

> A short pitch for your deckbuilder — one sentence, ≤280 chars.

<!--
STARTER NOTE — delete this comment block once you've made the tree your own.

This is a **descriptive scaffold extracted from the canonical deckbuilder
example** (examples/deckbuilder/, "Ember Ascent"). It is NOT a prescriptive
contract for what a deckbuilder must contain — it's a starting point. Delete
what doesn't fit, rename what does, add what's missing. Lint-clean as-is.

What this starter carries forward from the canonical deckbuilder:
- Three nested loops at three timescales (combat_turn → encounter → run).
- A `player` actor + `cards` content_collection + `enemies` content_collection.
- Three resources (energy / health / block) — the classic deckbuilder triad.
- A `card_lifecycle` state machine on the card namespace.
- Named distributions for card_draw + damage_roll.
- `pity_floor` reserved as a comment; uncomment if your loot/reward needs it.

What this starter does NOT carry (because the canonical example didn't need it):
- `clocks:` namespace — deckbuilders are typically turn-driven (player verb
  advances the loop), not time-driven. If your game is real-time, add it; if
  not, the absence is correct.
- `instance_container:` entity type — the canonical deckbuilder's cards are
  immutable templates; if YOUR design needs per-card state (cards with charges,
  modifiable HP, etc.), add an instance_container for that.

When in doubt, see `examples/deckbuilder/` for the populated reference.
-->

## High Concept

State your game's premise in 2-4 sentences. What's the player doing? Why does
each decision feel meaningful? What makes this game different from other
deckbuilders?

## Pillars & Non-Goals

The three pillars in the frontmatter are immutable for the life of the project
(spec §8.2 stability guarantee). Non-goals say what the game explicitly refuses
to be — every comparable game is tempted toward these; this one refuses.

## Player Experience Goals

`challenge` + `expression` is the canonical deckbuilder pairing (think
hand-shape decisions + run-shape investment); adjust `primary` to fit your
design intent.

## Core Gameplay Loop

`{loops.combat_turn}` — see `gdd/loops.md`. Three loops nest at three
timescales: `{loops.combat_turn}` (moment, ~45s) inside `{loops.encounter}`
(session, ~2-4 min) inside `{loops.run}` (meta, ~30 min). Replace the
placeholder loops with the actual structure of your game.

## How to Use This Document (for the Agent)

- **YAML is normative.** Compile against tokens; prose is rationale.
- **Tokens win on conflict.** If numbers in `gdd/economy-balance.md` disagree
  with prose anywhere, the numbers are correct.
- **Distributions are named.** Every roll resolves through `{distributions.<id>}`.
- **Invariants are contracts.** Before writing code that touches damage, state,
  or RNG, read `gdd/architecture-invariants.md`.
