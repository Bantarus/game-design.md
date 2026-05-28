---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/driftwood/time/**/*"]
balance_targets:
  in_game_hours_per_day:
    target_kind: scalar
    target: 24
    tolerance: [24, 24]
    measure: "in-game hours per day; structurally fixed"
    status: draft
  day_part_hour_boundaries:
    target_kind: distribution_over_categories
    target:    { morning: 6, afternoon: 6, evening: 4, night: 8 }
    tolerance: { morning: 0, afternoon: 0, evening: 0, night: 0 }
    measure: "in-game hours per day-part; structurally fixed (day-part durations are part of the game's identity)"
    status: draft
  wall_clock_seconds_per_in_game_hour:
    target_kind: scalar
    target: 15
    tolerance: [12, 18]
    measure: "wall-clock seconds per in-game hour at a decisive player's pace (target 15s; tolerance 12-18s)"
    status: draft
---

## Tokens

The in-game day's structure: 24 hours per day, partitioned into morning (6h) / afternoon (6h) / evening (4h) / night (8h), at ~15 wall-clock seconds per in-game hour for a decisive player. These three constants live here (not in `gdd/economy-balance.md`) because they are the *structural definition* of the day, not balance levers — changing them would change what the game *is*, not just how hard it is.

## Rationale

The day's structure is fixed by design. The brief commits to "a real-time day is about six minutes wall-clock" (6 minutes × 60 s = 360 s; 360 s / 24 in-game hours = 15 s per hour), and to the morning/afternoon/evening/night vocabulary. Day-part durations are not equal — morning and afternoon are the long, gathering-friendly parts; evening is short (the brief calls evening "good for crafting" — fewer in-game hours of it); night is the longest part but is gated by sleep (the player skips through it via `verbs.sleep_through_night` instead of acting through it).

**Why this is a system, not in `gdd/economy-balance.md`.** The economy-balance file holds the *tunable* targets — meter decay rates, win-condition thresholds, expected pyre completion percentages. Day length and day-part boundaries are *structural* — they define the day's shape. Putting them under a `systems/world_time.md` subsystem signals that they are part of the world model, not numbers to playtest. A future v2 of the game could tune the meter decay rate without changing the day's shape; this separation supports that.

**Action-driven advancement, not real-time tick.** As noted in `gdd/mechanics.md`, the in-game clock advances per-action (each verb's `time_cost.in_game_minutes`). A decisive player issues roughly 24 actions per in-game day; at ~15 s per action (deliberation + animation + result-observation) the wall-clock day is ~6 minutes. A first-time player takes longer per action; the wall-clock day stretches accordingly, but the in-game day-budget of 24 hours stays fixed. This is the property that makes the game a planning game rather than a real-time-clock game.

## Open Questions

- Whether to allow a "real-time mode" toggle where the in-game clock advances on a continuous wall-clock tick rather than per-action. Argument for: matches the genre's real-time-survival default. Argument against: punishes deliberation in a game where deliberation is the gameplay. v1: no, action-driven only.
- Whether the `wall_clock_seconds_per_in_game_hour` band's upper bound (18s) is too tight — a deliberating first-time player might be at 30s/hour, which would put a wall-clock day at 12 minutes. Currently the 18s upper bound describes a *decisive* player's pace; first-time players exceeding 18s is expected and is not a balance failure. Possibly add a `first_time_player_wall_clock_seconds_per_in_game_hour` target if playtest data warrants.
