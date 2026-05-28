---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/clocks/**/*.py"]
clocks:
  world_time:
    mode: per_verb_delta
    delta_source: "verb.time_cost.in_game_minutes"
    drives: ["{rules.tick_meters}"]
    status: draft
    implemented_in: ["src/clocks/world_time.py"]
---

## Tokens

One clock: `world_time`, in `per_verb_delta` mode. Each player verb declares
a `time_cost: { in_game_minutes: <int> }` field; when the verb fires, the
clock advances by that delta, then drives `{rules.tick_meters}` to apply
the survival-pressure consequences (hunger, thirst, fatigue ticking up).

## Rationale

**`per_verb_delta` mode (F-010 v0.3).** In an action-economy survival game,
time is what the player SPENDS, not what passes around them. Each action
declares its time cost; the clock advances by that amount. This is the
F-010 mode Driftwood drove into the v0.3 vocabulary — before F-010, this
pattern was modeled with a synthetic "advance_world_time" verb that existed
only to trigger the meter-tick rule.

**`delta_source: "verb.time_cost.in_game_minutes"`.** A dotted string path
read at apply-time per spec §3. Each verb MUST declare this field if it's
to drive the world_time clock. Verbs that don't advance time (UI verbs,
inspection verbs) omit `time_cost:` and the clock doesn't advance on them.
