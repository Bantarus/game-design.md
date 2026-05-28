---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
loops:
  action:
    timescale: moment
    duration: "varies (per-verb time_cost)"
    sequence:
      - gather: "{verbs.gather}"
      - craft:  "{verbs.craft}"
      - eat:    "{verbs.eat}"
      - rest:   "{verbs.rest}"
    intended_dynamics:
      - "each action spends real time AND advances the world clock"
    intended_aesthetics: [challenge, discovery]
    feel_priority: high
    balance_targets:
      - "{balance_targets.average_actions_per_day}"
    status: draft
    implemented_in: ["src/loops/action.py"]
  day_cycle:
    timescale: session
    duration: "~30 in-game minutes wall-clock per in-game day"
    clock: "{clocks.world_time}"
    sequence: []
    intended_dynamics:
      - "day-night cycle drives weather, hazard frequency, visibility"
    intended_aesthetics: [challenge]
    balance_targets:
      - "{balance_targets.days_survived_target}"
    status: draft
    implemented_in: ["src/loops/day_cycle.py"]
---

## Tokens

Two loops. The `action` loop is the per-action moment loop (verb-driven, with
each verb advancing world time by its declared cost). The `day_cycle` loop is
clock-driven — world_time advances through it as actions accumulate.

## Rationale

**Two-tier time semantics.** The action loop is the player's decision unit;
the day_cycle is the consequence horizon. Both reference world_time but at
different granularities — the action loop reads "did time advance this
action?", the day_cycle reads "what game-day are we on?"
