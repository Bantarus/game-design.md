---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
entities:
  player:
    type: actor
    properties:
      x:              { from: "{resources.position_x}" }
      y:              { from: "{resources.position_y}" }
      vx:             { from: "{resources.velocity_x}" }
      vy:             { from: "{resources.velocity_y}" }
      lives:          { from: "{resources.lives}" }
    status: draft
    implemented_in: ["src/entities/player.py"]
  levels:
    type: content_collection
    data_source: ../../content/levels
    count_target: 10
    status: draft
verbs:
  move:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: directional }
    effects:
      - { resolve: "{rules.movement_intent}" }
    status: draft
    implemented_in: ["src/verbs/move.py"]
  jump:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: trigger }
    effects:
      - { resolve: "{rules.jump_intent}" }
    status: draft
    implemented_in: ["src/verbs/jump.py"]
  spawn:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.player_spawn}" }
    status: draft
    implemented_in: ["src/verbs/spawn.py"]
  resolve_level:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.level_resolution}" }
    status: draft
    implemented_in: ["src/verbs/resolve_level.py"]
resources:
  position_x:
    scope: permanent
    min: -99999
    max: 99999
    visibility: inferred
    status: draft
    implemented_in: ["src/resources/position.py"]
  position_y:
    scope: permanent
    min: -99999
    max: 99999
    visibility: inferred
    status: draft
    implemented_in: ["src/resources/position.py"]
  velocity_x:
    scope: permanent
    min: -999
    max: 999
    visibility: hidden
    status: draft
    implemented_in: ["src/resources/velocity.py"]
  velocity_y:
    scope: permanent
    min: -999
    max: 999
    visibility: hidden
    status: draft
    implemented_in: ["src/resources/velocity.py"]
  lives:
    scope: permanent
    min: 0
    max: 99
    visibility: hud
    status: draft
    implemented_in: ["src/resources/lives.py"]
states:
  player_state:
    initial: grounded
    nodes:
      - { id: grounded }
      - { id: airborne }
      - { id: dead, terminal: true }
    transitions:
      - { from: grounded, event: "{events.leave_ground}", to: airborne }
      - { from: airborne, event: "{events.land}",         to: grounded }
      - { from: grounded, event: "{events.hit_hazard}",   to: dead }
      - { from: airborne, event: "{events.hit_hazard}",   to: dead }
events:
  leave_ground:
    status: draft
    description: "Player leaves the ground (jumped or walked off a ledge)."
  land:
    status: draft
    description: "Player lands on a ground tile."
  hit_hazard:
    status: draft
    description: "Player collided with a hazard tile or enemy."
rules:
  movement_intent:
    given:
      verb: "{verbs.move}"
    do:
      - { kind: set_intent, axis: x }
    outputs: [movement_intent_set]
    status: draft
    implemented_in: ["src/rules/movement_intent.py"]
  jump_intent:
    given:
      verb: "{verbs.jump}"
    do:
      - { kind: set_intent, kind_of_intent: jump }
    outputs: [jump_intent_set]
    status: draft
    implemented_in: ["src/rules/jump_intent.py"]
  physics_tick:
    given:
      driver: "{clocks.physics}"
    do:
      - { kind: apply_gravity }
      - { kind: integrate_velocity }
      - { kind: resolve_collisions }
    outputs: [physics_state_updated]
    status: draft
    implemented_in: ["src/rules/physics_tick.py"]
  player_spawn:
    given:
      verb: "{verbs.spawn}"
    do:
      - { kind: reset_to_spawn_point }
    outputs: [player_spawned]
    status: draft
    implemented_in: ["src/rules/player_spawn.py"]
  level_resolution:
    given:
      verb: "{verbs.resolve_level}"
    do:
      - { kind: tally_level_stats }
    outputs: [level_resolved]
    status: draft
    implemented_in: ["src/rules/level_resolution.py"]
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `states`, `events`, `rules`.
The `physics_tick` rule is clock-driven; the input verbs (`move`, `jump`)
are player-driven and set per-frame intent, applied during the next tick.

## Rationale

**Position and velocity as resources.** Modeled as integer-valued resources
(per the spec's integer-domain discipline). For sub-pixel precision in your
implementation, store at higher precision (e.g., fixed-point at 1/64 pixel)
but expose the gameplay layer as integers.

**Intent-then-tick pattern.** Input verbs set INTENT (a flag/value); the
physics tick reads intent + state and produces new state. This decouples
input rate (variable) from physics rate (fixed 60Hz) and makes replays
deterministic.
