---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-22"
pillars:
  - "Cards decide games, not lucky draws"
  - "Each of the four archetypes plays differently and is winnable"
  - "A match is best-of-three, ~20 minutes total"
non_goals:
  - "Booster packs / free-to-play monetization"
  - "Single-player campaign"
  - "Real-time mechanics"
---

## Tokens

See frontmatter.

## Rationale

**Cards over luck.** Lattice's randomness is bounded: `{distributions.card_draw}` is `shuffle_bag` (every card sees play before any repeats), and there is no in-game damage roll — printed damage is what hits. Variance comes from *which* cards a player drew, not *whether* the dice favor them.

**All archetypes viable.** `{balance_targets.win_rate_archetype_neutral}` keeps the matchup matrix flat — every archetype wins between 45% and 55% of mirrored matches. The verify adapter (when it ships) runs 1000 matches per archetype-pair and asserts the rate.

**20-minute match.** Three games × ~7 minutes per game = ~21 minutes total. Anchored to `{balance_targets.average_match_duration}`.
