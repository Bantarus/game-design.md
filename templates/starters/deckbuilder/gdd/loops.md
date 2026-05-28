---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
loops:
  combat_turn:
    timescale: moment
    duration: "~45s"
    sequence:
      - draw:     "{verbs.draw_cards}"
      - play:     "{verbs.play_card}"
      - end_turn: "{verbs.end_turn}"
    intended_dynamics:
      - "energy scarcity forces hand-shape decisions each turn"
    intended_aesthetics: [challenge, expression]
    feel_priority: high
    balance_targets:
      - "{balance_targets.energy_per_turn}"
    status: draft
    implemented_in: ["src/loops/combat_turn.py"]
  encounter:
    timescale: session
    duration: "~2-4 min"
    sequence:
      - start: "{verbs.start_combat}"
      - turns: "{loops.combat_turn}"
      - end:   "{verbs.resolve_encounter}"
    intended_dynamics:
      - "an encounter is a series of combat turns with a clear win/lose end"
    intended_aesthetics: [challenge]
    balance_targets:
      - "{balance_targets.win_rate_normal}"
    status: draft
    implemented_in: ["src/loops/encounter.py"]
  run:
    timescale: meta
    duration: "~30 min"
    sequence:
      - encounters: "{loops.encounter}"
    intended_dynamics:
      - "a run is a sequence of encounters with cumulative deck shaping"
    intended_aesthetics: [challenge, discovery]
    balance_targets:
      - "{balance_targets.average_run_length}"
    status: draft
    implemented_in: ["src/loops/run.py"]
---

## Tokens

Three nested loops at three timescales. The `combat_turn` is the moment loop
(the per-turn decision); `encounter` is the session loop (one combat from
start to end); `run` is the meta loop (one full playthrough).

## Rationale

The `core_loop_ref` in the root file points at `combat_turn` — that's where
the second-by-second decision-making lives. The other two loops give context
for how meaning accumulates across longer time horizons.
