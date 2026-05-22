---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-22"
pillars:
  - "Four characters, one shared decision per turn"
  - "Pity floors prevent loot dry streaks; rewards always feel earned"
  - "A descent is one quest, ~25 minutes top to bottom"
non_goals:
  - "Open-world exploration"
  - "Crafting"
  - "Multiplayer"
---

## Tokens

See frontmatter.

## Rationale

**One decision per turn.** Four characters take individual actions, but the *interesting* choice is which character acts on this turn and what they do. We design turn pacing (~15s per character action) so the player never feels rushed but never zones out.

**Pity floors.** The `{distributions.loot_rarity}` is `pity_floor` with `rare_within: 6, epic_within: 20, legendary_within: 50`. The math: a player will see a rare within 6 encounters, an epic within 20, a legendary within 50 (the whole descent). Bad luck cannot ruin a run.

**25 minutes.** Top-to-bottom descent is 20 floors, ~75 seconds per floor on average. That's `{balance_targets.median_battle_turns} * 15s + setup/loot overhead`. Anything longer breaks the "one run per lunch break" promise.
