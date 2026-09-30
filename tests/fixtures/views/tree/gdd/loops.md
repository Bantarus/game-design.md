---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-09-30"
loops:
  day:
    timescale: moment
    duration: "~1m"
    sequence:
      - study: "{verbs.study}"
      - rest: "{verbs.rest}"
    intended_dynamics: ["pacing focus"]
    intended_aesthetics: [discovery]
    balance_targets: ["{balance_targets.focus_per_day}"]
    status: draft
    implemented_in: ["src/sim/day.py"]
---

## Rationale

`{loops.day}` alternates `{verbs.study}` and `{verbs.rest}`.
