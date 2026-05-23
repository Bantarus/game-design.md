---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/driftwood/balance/**/*"]
balance_targets:
  hunger_decay_rate:
    target_kind: scalar
    target: 1
    tolerance: [1, 1]
    measure: "hunger units lost per in-game hour; the brief commits to '1 per hour'"
    status: draft
  thirst_decay_rate:
    target_kind: scalar
    target: 1
    tolerance: [1, 1]
    measure: "thirst units lost per in-game hour; the brief commits to '1 per hour' (with faster decay implicit via fewer-hours-between-drinks in play)"
    status: draft
  hp_band_at_run_end:
    target_kind: range
    target: { between: [6, 12] }
    measure: "HP a skilled player should finish a clean run with; the brief implies 'comfortably alive at rescue,' not 'on the brink'"
    status: draft
  in_game_hours_per_run:
    target_kind: scalar
    target: 120
    tolerance: [120, 120]
    measure: "in-game hours in a full five-day run; structurally fixed (5 days × 24 hours)"
    status: draft
  skilled_player_pyre_completion_pct:
    target_kind: scalar
    target: 80
    tolerance: [70, 95]
    measure: "percent of clean-routed runs where a skilled player lights the pyre on Day 5; brief implies the route is reliably executable"
    status: draft
  first_time_player_pyre_completion_pct:
    target_kind: scalar
    target: 20
    tolerance: [10, 30]
    measure: "percent of first-time-player runs where the pyre is lit; brief says '80% of first runs miss the rescue' which is 20% complete"
    status: draft
  run_length_wall_clock_minutes:
    target_kind: range
    target: { near: 30, tolerance: 10 }
    measure: "wall-clock minutes per run for a decisive player; brief commits to '~30 minutes'"
    status: draft
  pyre_input_total:
    target_kind: distribution_over_categories
    target:    { wood: 20, fiber: 18, stone: 7, flint: 1 }
    tolerance: { wood: 4,  fiber: 4,  stone: 2, flint: 0 }
    measure: "total raw materials to assemble the pyre (sum of all recipe-chain inputs); brief lists ~20/18/7/1 as the targets"
    status: draft
---

## Tokens

Eight balance targets. The first four (`hunger_decay_rate`, `thirst_decay_rate`, `hp_band_at_run_end`, `in_game_hours_per_run`) are per-tick / per-run scalar invariants the brief commits to. The next two (`skilled_player_pyre_completion_pct`, `first_time_player_pyre_completion_pct`) are the headline completion rates — the brief commits to the *skilled* number as "reliable" and the *first-time* number as "~20% complete on first run." The `run_length_wall_clock_minutes` target is the deadline framing. The `pyre_input_total` target is the resource-budget anchor — it constrains the recipe tree's total material cost.

Targets are split into structural (cannot change without redefining the game), prescriptive (the design's intended numbers, tunable at playtest within their tolerance), and outcome (what we should observe at the end of N runs). Each target's `measure:` field names the brief sentence the target is anchored in.

## Rationale

### Why the deadline is the only difficulty knob

The brief commits to "time pressure, not difficulty pressure." Tightening the deadline (fewer in-game hours per day, or fewer days) makes the game harder; loosening it makes it easier. There is no other knob — no enemy difficulty, no skill gate, no rng. So balance work post-launch is a single-dimension tuning: are the rates and budgets right such that the skilled-player band lands at 70–95% completion and the first-timer band lands at 10–30%?

### Why the pyre's input total is a hard target, not soft

The recipe tree is the game; the pyre is the apex. If `pyre_input_total` is wrong (too high → first-timers can't even theoretically make it; too low → skilled players finish on Day 3 and the deadline framing collapses), the entire economy is wrong. The 20/18/7/1 tolerance bands are tight (±4 for the bulk materials, 0 for flint which is structurally unique) because the recipe-tree math doesn't tolerate much drift.

### Why HP band is wide

The brief is silent on what HP a skilled player should end with — it says "comfortably alive at rescue" via the absence of "barely surviving" language. Target HP 6–12 is wide because the brief doesn't anchor a number; we infer "not on the brink" but won't be more precise without playtest data.

## Open Questions

- Whether `hunger_decay_rate` and `thirst_decay_rate` should be `target_kind: scalar` with `[1, 1]` tolerance (current — pinning the rate as a fixed design constant) or `range` with `near: 1, tolerance: 0.5` (loosening to a band). Currently pinned to 1; the brief commits to "1 per hour" as a number, so the band would be playtest-loosening, not design-loosening. Leaving pinned.
- Whether `pyre_input_total.flint` should be `1` (structurally — there's one flint outcrop and you need one flint shard) or could be `2` (a "backup" flint per run for replay smoothness if the player accidentally drops or loses it). Currently 1; brief is consistent with 1; revisit if playtest shows accidental-loss-of-flint is a real failure mode.
