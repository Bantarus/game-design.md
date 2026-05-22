---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
balance_targets:
  median_ticks_per_combat:
    target: 120
    tolerance: [80, 200]
    measure: "median tick count from start_combat to resolved, over 1000 monte-carlo encounters"
    status: draft
  average_team_dps:
    target: 8.0
    tolerance: [6.0, 10.0]
    measure: "average damage per tick across a balanced 5-unit roster"
    status: draft
  gold_per_encounter:
    target: 14
    tolerance: [10, 20]
    measure: "expected gold reward from one encounter, weighted across difficulty"
    status: draft
  win_rate_neutral_formation:
    target: 0.5
    tolerance: [0.45, 0.55]
    measure: "win rate of the canonical neutral formation against the canonical neutral opponent over 1000 runs"
    status: draft
---

## Tokens

Four balance targets. Each is referenced from at least one loop, resource, or verify target — otherwise `orphaned-entity` would fire.

## Rationale

`{balance_targets.median_ticks_per_combat}` is the *headline pacing metric*. 120 ticks at 100ms is ~12 seconds wall-clock; the tolerance band `[80, 200]` is wide enough to accommodate stalemates and quick decisives without flagging design intent.

`{balance_targets.average_team_dps}` cross-checks the damage curve. If `{distributions.damage_roll}` shifts (mean or stddev), this target catches it.

`{balance_targets.gold_per_encounter}` ties to `{resources.gold}.velocity_target` — the economy spec.

`{balance_targets.win_rate_neutral_formation}` is the asymmetry test. A neutral formation against a neutral opponent should be a coin flip; deviation means the formation system has hidden tilts.
