---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/driftwood/clocks/**/*"]
clocks:
  world_time:
    mode: per_verb_delta
    delta_source: "actor.last_action_time_cost"
    drives:
      - "{rules.advance_world_time}"
      - "{rules.tick_meters}"
    status: draft
    implemented_in: ["src/driftwood/clocks/world_time.py"]
---

## Tokens

This file owns the `clocks` namespace for Driftwood. The single clock `{clocks.world_time}` drives both `{rules.advance_world_time}` (the world-clock increment + day-part boundary check) and `{rules.tick_meters}` (hp/hunger/thirst decay) on each advancement.

## Rationale

**`{clocks.world_time}` lifts the world-clock advancement out of the verb namespace.** Driftwood's in-game clock advances every time the player acts (each player verb declares its `time_cost.in_game_minutes`); the natural model is "world time ticks per action." Earlier modeling used a synthetic `verbs.advance_world_time` whose sole purpose was to satisfy the spec's verb-triggers-rule pattern. F-010's v0.3 resolution (spec §4.7) makes time-passage a first-class primitive with two modes; Driftwood's `world_time` is the `per_verb_delta` case (paired with Embergrave's and tick-combat's `continuous` case, the two modes that closed F-010's empirical surface).

**`delta_source: "actor.last_action_time_cost"`** — context-local ref bound at apply-time per spec §3. The delta is the most-recently-fired player verb's `time_cost.in_game_minutes` value, captured on the actor (player) at verb-fire time. The clock advances by that amount and then fires its driven rules.

**`drives:` lists two rules.** Each clock advancement fires both `{rules.advance_world_time}` (which increments the world minutes/hours and checks day-part boundaries) and `{rules.tick_meters}` (which decays hp/hunger/thirst per the elapsed in-game time). The ordering between these two is the same as before F-010 — `advance_world_time` first (so day-part boundary events are emitted before meter decay), then `tick_meters`. Engines MUST fire the rules in the declared `drives:` order.

**Cross-engine determinism.** The `world_time` clock's contract is engine-neutral: given the same sequence of player verbs (each with its declared `time_cost.in_game_minutes`), the clock advances identically across engines and the two driven rules fire identically. Time-passage doesn't introduce any cross-engine ambiguity (no PRNG, no transcendental math); the determinism contract is purely structural.
