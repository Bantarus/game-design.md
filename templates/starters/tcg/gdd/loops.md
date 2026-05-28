---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
loops:
  player_turn:
    timescale: moment
    duration: "~60s"
    sequence:
      - draw_phase: "{verbs.draw_card}"
      - main_phase: "{verbs.play_card}"
      - end_phase:  "{verbs.end_turn}"
    intended_dynamics:
      - "resource curve (mana / energy) forces play-pacing decisions"
      - "board state reading rewards interactive play over solitaire"
    intended_aesthetics: [challenge, fellowship]
    feel_priority: high
    balance_targets:
      - "{balance_targets.average_turns_per_match}"
    status: draft
    implemented_in: ["src/loops/player_turn.py"]
  match:
    timescale: session
    duration: "~15-30 min"
    sequence:
      - start: "{verbs.start_match}"
      - turns: "{loops.player_turn}"
      - end:   "{verbs.resolve_match}"
    intended_dynamics:
      - "matches end on life-total or deck-out"
    intended_aesthetics: [challenge]
    balance_targets:
      - "{balance_targets.win_rate_mirror_match}"
    status: draft
    implemented_in: ["src/loops/match.py"]
---

## Tokens

Two nested loops: `player_turn` (moment) and `match` (session). Add a `season`
meta loop if your game has ranking / progression across matches.

## Rationale

The TCG moment loop is the player turn — a phased sequence (draw / main / end)
where mana, hand, and board are the load-bearing decision spaces.
