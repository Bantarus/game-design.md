---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: "Untitled TCG"
short_pitch: "A short pitch for your trading card game — one sentence, ≤280 chars."
genre_tags: [tcg, multiplayer, head-to-head]
status: draft
version: 0.1.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop, mobile]
pillars:
  - "Pillar 1 — the deckbuilding decision that defines a player's identity"
  - "Pillar 2 — the in-game decision that rewards reading the board"
  - "Pillar 3 — the constraint that keeps matches reasonable in length"
non_goals:
  - "Single-player campaign as the primary mode"
player_experience_goals:
  primary: [challenge, fellowship]
  secondary: [expression]
core_loop_ref: "{loops.player_turn}"
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

# Untitled TCG

> A short pitch for your trading card game — one sentence, ≤280 chars.

<!--
STARTER NOTE — delete this comment block once you've made the tree your own.

Descriptive scaffold extracted from the canonical TCG example (examples/tcg/).
Not a prescriptive contract — delete what doesn't fit. Lint-clean as-is.

Carries forward from the canonical TCG:
- A `battlefield` instance_container (F-008 v0.3) — N owned card instances on
  the board, each with per-instance counters (+1/+1, charges, taps, etc.).
- Two-player asymmetric structure with a `player_turn` core loop.
- `cards` as the content_collection of immutable card templates.
- Phased turn structure (draw → main → end).

Does NOT carry:
- `clocks:` namespace — TCG turns advance on player verb, not wall clock.
  Add a clock if your game has a per-turn timer.
-->

## High Concept

State the premise in 2-4 sentences. What makes the deckbuilding decisions
matter? Why are matches interactive rather than solitaire?

## Pillars & Non-Goals

The three pillars in the frontmatter are immutable for the life of the project.

## Player Experience Goals

`challenge` + `fellowship` is the canonical TCG pairing — competitive play
against another mind.

## Core Gameplay Loop

`{loops.player_turn}` — the per-turn moment loop. The `{loops.match}` session
loop brackets one match from start to victory/concession.

## How to Use This Document (for the Agent)

- YAML is normative; prose is rationale.
- Per-card-on-board state lives in `entities.battlefield.per_instance_state`.
- Distributions are named — every shuffle, every coin flip, every random card
  selection resolves through `{distributions.<id>}`.
