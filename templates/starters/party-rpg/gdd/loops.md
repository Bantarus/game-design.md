---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
loops:
  combat_round:
    timescale: moment
    duration: "~60s"
    sequence:
      - hero_actions:  "{verbs.take_hero_action}"
      - enemy_actions: "{verbs.resolve_enemy_actions}"
      - end_round:     "{verbs.end_round}"
    intended_dynamics:
      - "turn order is determined by speed; party composition affects who acts first"
      - "resource (mp/items) scarcity forces tactical investment decisions"
    intended_aesthetics: [challenge, expression]
    feel_priority: high
    balance_targets:
      - "{balance_targets.average_rounds_per_encounter}"
    status: draft
    implemented_in: ["src/loops/combat_round.py"]
  encounter:
    timescale: session
    duration: "~5-10 min"
    sequence:
      - start:  "{verbs.start_encounter}"
      - rounds: "{loops.combat_round}"
      - end:    "{verbs.resolve_encounter}"
    intended_dynamics:
      - "an encounter is a series of rounds with rewards on victory"
    intended_aesthetics: [challenge]
    balance_targets:
      - "{balance_targets.win_rate_normal}"
    status: draft
    implemented_in: ["src/loops/encounter.py"]
---

## Tokens

Two nested loops. The `combat_round` is the per-round moment loop; `encounter`
is the session loop bracketing one combat from start to resolution. Add a
`campaign` meta loop when you author the meta progression.

## Rationale

A party RPG's moment loop is the round — the small decision per hero that
sums to a tactical sequence. The encounter is the unit of pacing and reward.
