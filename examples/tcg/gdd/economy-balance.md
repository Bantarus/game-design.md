---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
balance_targets:
  win_rate_archetype_neutral:
    target: 0.5
    tolerance: [0.45, 0.55]
    measure: "win rate of each of the four archetypes over 1000 matches against every other archetype"
    status: draft
  average_match_duration:
    target: "20 min"
    tolerance: ["14 min", "28 min"]
    measure: "median wall-clock of a best-of-three match"
    status: draft
  average_game_turns:
    target: 8
    tolerance: [5, 12]
    measure: "median number of turns per game"
    status: draft
  mana_per_turn:
    target: 4
    tolerance: [3, 5]
    measure: "average mana available per turn after the curve ramps from 1 to 10"
    status: draft
---

## Tokens

Four balance targets. `win_rate_archetype_neutral` is the keystone — the matchup matrix asymmetry.

## Rationale

**`win_rate_archetype_neutral` at 0.5.** Each archetype, averaged across all opposing archetypes, must win roughly half its matches. The tolerance `[0.45, 0.55]` is the design's promise on archetype balance. A regression here triggers immediate rebalance.

**`average_match_duration` at 20 min.** Anchors `{pillars}[2]`. Tolerance is wide because best-of-three variance is high — a 2-0 sweep is ~15 minutes, a 2-1 with mulligans can stretch to 28.

**`average_game_turns` at 8.** A game shorter than 5 turns means the meta is too aggressive ("burn deck wins by turn 4"); longer than 12 means control is too dominant. Tolerance band `[5, 12]` keeps both extremes flagged.

**`mana_per_turn` at 4** — the mana curve goes 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 across turns. Average across an 8-turn game is ~4.5; we target 4 as the *active-cards-per-turn* anchor.
