---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: core
name: "Lattice"
short_pitch: "A 20-minute asymmetric two-player TCG. Pick an archetype, play three best-of-three games, win on cards not luck."
genre_tags: [tcg, two-player, head-to-head]
status: draft
version: 0.2.0
last_updated: "2026-05-28"
target_platforms_neutral: [desktop, web]
pillars:
  - "Cards decide games, not lucky draws"
  - "Each of the four archetypes plays differently and is winnable"
  - "A match is best-of-three, ~20 minutes total"
non_goals:
  - "Booster packs / free-to-play monetization"
  - "Single-player campaign"
  - "Real-time mechanics"
player_experience_goals:
  primary: [challenge, fellowship]
  secondary: [expression]
  explicit_non_goals: [submission]
core_loop_ref: "{loops.turn}"
files:
  pillars:                 gdd/pillars.md
  loops:                   gdd/loops.md
  mechanics:               gdd/mechanics.md
  architecture_invariants: gdd/architecture-invariants.md
  distributions:           gdd/systems/distributions.md
  economy_balance:         gdd/economy-balance.md
  verification:            gdd/verification.md
  content_index:           gdd/content/_index.md
  cards:                   gdd/content/cards.md
---

# Lattice

> A 20-minute asymmetric two-player TCG. Pick an archetype, play three best-of-three games, win on cards not luck.

## High Concept

Two players pick one of four archetypes (Spark, Bulwark, Veil, Forge). Each archetype has 50 unique cards plus access to a shared neutral pool of 20. A match is best-of-three games; a game ends when one player's life reaches 0 or their deck is empty. The hook is **balanced asymmetry** — each archetype plays differently, and `{balance_targets.win_rate_archetype_neutral}` keeps the matchup matrix flat (every archetype's overall win rate stays between 0.45 and 0.55).

## Pillars & Non-Goals

Three pillars: cards over luck, all archetypes viable, a match fits a coffee break. Three non-goals (frontmatter) name what Lattice is not.

## Player Experience Goals

**Challenge** and **fellowship** are primary — the fellowship aesthetic is the head-to-head social loop, not co-op. **Expression** (deck construction within an archetype) is secondary. **Submission** is explicitly out: there's no auto-play.

## Core Gameplay Loop

`{loops.turn}` is the moment loop. Three loops nest: `{loops.turn}` inside `{loops.game}` inside `{loops.match}`.

## Universal Surface

The full surface lives in subfiles linked via the `files:` map. Agent reading order from cold:

1. `gdd/pillars.md`
2. `gdd/loops.md`
3. `gdd/mechanics.md`
4. `gdd/architecture-invariants.md`
5. `gdd/content/cards.md` + one example from `content/cards/*.yaml`.

## How to Use This Document (for the Agent)

- `{distributions.card_draw}` is `shuffle_bag` per spec §4.8 — every card appears exactly its deck-quantity times before reshuffling.
- Damage and life are integers per `{invariants.damage_is_integer}`.
- `{states.phase_state}` is **cyclic** — there is no terminal phase, the cycle runs until the game ends via the separate `{states.card_state}` `exiled` terminal or via life reaching zero.

## Glossary

- **Archetype.** One of the four card pools (Spark/Bulwark/Veil/Forge). Each player picks one before the match.
- **Match.** Best-of-three games. The series ends when one player wins two games.
- **Phase.** One of `untap`, `upkeep`, `main`, `combat`, `end`. Cyclic; see `{states.phase_state}`.
