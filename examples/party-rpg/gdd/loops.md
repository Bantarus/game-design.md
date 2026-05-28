---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
loops:
  turn:
    timescale: moment
    duration: "~15s"
    sequence:
      - act:      "{verbs.act}"
      - finalize: "{verbs.end_turn}"
    intended_dynamics:
      - "one of four characters acts per turn; player chooses which"
      - "tactical commitment — there is no undo"
    intended_aesthetics: [challenge, expression]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.median_battle_turns}"
    status: draft
    implemented_in: []
  battle:
    timescale: session
    duration: "~3 min"
    sequence:
      - start:  "{verbs.start_battle}"
      - turns:  "{loops.turn}"
      - claim:  "{verbs.claim_loot}"
    intended_dynamics:
      - "loot decisions create a meta tension with inventory limits"
    intended_aesthetics: [challenge, discovery]
    feel_priority: low
    balance_targets:
      - "{balance_targets.win_rate_neutral_party}"
    status: draft
    implemented_in: []
  quest:
    timescale: meta
    duration: "~25 min"
    sequence:
      - battles: "{loops.battle}"
    intended_dynamics:
      - "pity floors guarantee at least one legendary per quest"
    intended_aesthetics: [challenge, discovery]
    feel_priority: low
    balance_targets:
      - "{balance_targets.legendary_drops_per_quest}"
      - "{balance_targets.average_quest_length}"
    status: draft
    implemented_in: []
---

## Tokens

Three loops at three timescales: `{loops.turn}` (moment) inside `{loops.battle}` (session) inside `{loops.quest}` (meta).

## Rationale

`{loops.turn}` is the moment-to-moment unit — one character commits one action via `{verbs.act}`, then end-of-turn cleanup. Four characters means four turns per round; the loop fires once per character action.

`{loops.battle}` is one floor of the dungeon. Setup is automatic (random enemy spawn from the encounter table); the player just watches and acts.

`{loops.quest}` is the whole descent — 20 floors. The legendary pity floor at 50 drops means a player who goes 50 encounters without a legendary on rarer runs will *always* see one by the end of the quest.
