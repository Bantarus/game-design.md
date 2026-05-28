---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/balance/**/*.py"]
balance_targets:
  average_ticks_per_match:
    target_kind: range
    target: { near: 40, tolerance: 15 }
    measure: "median ticks per match (one tick = 250ms)"
    status: draft
  win_rate_neutral_formation:
    target_kind: scalar
    target: 0.50
    tolerance: [0.40, 0.60]
    measure: "win rate when both sides field identical rosters; deviation flags asymmetry bugs"
    status: draft
---

## Tokens

Two balance targets. The neutral-formation win rate at 0.50 is the structural
fairness check; any deviation signals tick-order bias or roster-asymmetry bugs.
