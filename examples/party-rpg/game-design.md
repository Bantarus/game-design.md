---
spec: game-design.md
spec_version: 0.1.1
file_type: core
name: "Hollow Hold"
short_pitch: "A 30-minute four-party dungeon descent where loot pity floors keep every run honest."
genre_tags: [party-rpg, dungeon-crawler, single-player]
status: draft
version: 0.1.0
last_updated: "2026-05-22"
target_platforms_neutral: [desktop, handheld]
pillars:
  - "Four characters, one shared decision per turn"
  - "Pity floors prevent loot dry streaks; rewards always feel earned"
  - "A descent is one quest, ~25 minutes top to bottom"
non_goals:
  - "Open-world exploration"
  - "Crafting"
  - "Multiplayer"
player_experience_goals:
  primary: [challenge, expression]
  secondary: [discovery]
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
  items:                   gdd/content/items.md
---

# Hollow Hold

> A 30-minute four-party dungeon descent where loot pity floors keep every run honest.

## High Concept

Four adventurers descend a vertical dungeon, one floor per encounter, twenty floors to the bottom. The party shares one decision per turn: *which character acts, and how*. Loot drops at the end of each encounter through a `pity_floor` distribution — no rare item by the 6th drop guarantees one; no epic by the 20th guarantees one; no legendary by the 50th guarantees one. The hook is that *every run feels earned* because the math refuses to leave you dry.

## Pillars & Non-Goals

See frontmatter. The three pillars and three non-goals are locked.

## Player Experience Goals

**Challenge** + **expression** primary (build a four-character composition; commit per turn). **Discovery** secondary (item synergies). **Submission** is explicitly out — the player must choose actively, even with one viable option.

## Core Gameplay Loop

`{loops.turn}` is the moment loop — one character commits one action, then the next character, then the next, then end-of-round. Three loops nest: `{loops.turn}` inside `{loops.battle}` inside `{loops.quest}`.

## Universal Surface

The full surface lives in the subfiles linked via the `files:` map. Agent reading order from cold:

1. `gdd/pillars.md`
2. `gdd/loops.md`
3. `gdd/mechanics.md`
4. `gdd/architecture-invariants.md`
5. `gdd/content/items.md` + one example from `content/items/*.yaml`.

## How to Use This Document (for the Agent)

- `{distributions.loot_rarity}` is `pity_floor` — pity floors are the design's promise to the player; do not weaken them to "weighted" without an explicit decision.
- Damage and HP are integers per `{invariants.damage_is_integer}`.
- The character lifecycle has a revive transition (`unconscious → alive`) — `dead` is the only terminal node.

## Glossary

- **Hollow.** The dungeon's setting; also the in-fiction term for unconscious party members.
- **Pity floor.** The guaranteed-by-N-drops mechanic on `{distributions.loot_rarity}`.
- **Floor.** One vertical level of the dungeon = one encounter.
