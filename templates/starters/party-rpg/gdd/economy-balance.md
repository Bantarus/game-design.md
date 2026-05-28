---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/balance/**/*.py"]
balance_targets:
  average_rounds_per_encounter:
    target_kind: range
    target: { near: 4, tolerance: 2 }
    measure: "median rounds to clear a typical encounter, Normal difficulty"
    status: draft
  win_rate_normal:
    target_kind: scalar
    target: 0.65
    tolerance: [0.55, 0.75]
    measure: "win rate over 200 monte-carlo encounters at Normal difficulty"
    status: draft
---

## Tokens

Two balance targets — encounter pacing and difficulty curve. Add more as your
balance considerations stack up.
