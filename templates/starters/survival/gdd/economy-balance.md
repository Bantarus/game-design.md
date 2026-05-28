---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/balance/**/*.py"]
balance_targets:
  average_actions_per_day:
    target_kind: range
    target: { near: 30, tolerance: 10 }
    measure: "median number of actions a player takes per in-game day"
    status: draft
  days_survived_target:
    target_kind: range
    target: { near: 20, tolerance: 10 }
    measure: "median days survived in a successful playthrough"
    status: draft
---

## Tokens

Two balance targets — action density per day (pacing) and total run length
in days (replayability target).
