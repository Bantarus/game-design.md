---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
loops:
  physics_step:
    timescale: moment
    duration: "~16.67ms"
    clock: "{clocks.physics}"
    sequence:
      - sample_input: "{verbs.move}"
      - sample_input: "{verbs.jump}"
    intended_dynamics:
      - "input intent is captured per-frame and applied during the physics tick"
    intended_aesthetics: [sensation]
    feel_priority: high
    balance_targets:
      - "{balance_targets.target_jump_height_pixels}"
    status: draft
    implemented_in: ["src/loops/physics_step.py"]
  level_attempt:
    timescale: session
    duration: "~30s-5min"
    sequence:
      - spawn: "{verbs.spawn}"
      - play:  "{loops.physics_step}"
      - end:   "{verbs.resolve_level}"
    intended_dynamics:
      - "an attempt runs until death or clear"
    intended_aesthetics: [challenge]
    balance_targets:
      - "{balance_targets.average_attempts_per_level}"
    status: draft
    implemented_in: ["src/loops/level_attempt.py"]
---

## Tokens

Two nested loops. The `physics_step` loop is clock-driven (the
`{clocks.physics}` 60Hz clock IS the iteration); it lists the input-sampling
verbs in `sequence:` because input intent IS gathered per-frame and applied
during the physics tick.

The `level_attempt` is the session loop bracketing one attempt at a level.

## Rationale

**Mixed `clock:` + `sequence:`.** Per F-010 v0.3, a clock-driven loop may
also list verbs in `sequence:` for input-driven additional behavior. The
physics tick is clock-driven; player intent verbs (move, jump) are
sequence-driven on the same loop iteration.
