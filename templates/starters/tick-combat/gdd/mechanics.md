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
      gold: { from: "{resources.gold}" }
    status: draft
    implemented_in: ["src/entities/player.py"]
  units:
    type: content_collection
    data_source: ../../content/units
    count_target: 20
    status: draft
  deployed_units:
    type: instance_container
    capacity: 12
    holds_template_from: "{entities.units}"
    per_instance_state:
      hp:           { type: integer, minimum: 0 }
      lifecycle:    { type: string }
      deploy_order: { type: integer, minimum: 0 }
      side:         { type: string }
    status: draft
    implemented_in: ["src/entities/deployed_units.py"]
verbs:
  deploy_units:
    actor: "{entities.player}"
    cost: { resource: "{resources.gold}", amount: "varies_by_unit" }
    target_schema:
      type: "{entities.units}"
    effects:
      - { resolve: "{rules.unit_deployed}" }
    status: draft
    implemented_in: ["src/verbs/deploy_units.py"]
  resolve_match:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.match_resolution}" }
    status: draft
    implemented_in: ["src/verbs/resolve_match.py"]
resources:
  gold:
    scope: per_run
    min: 0
    max: 999
    visibility: hud
    status: draft
    implemented_in: ["src/resources/gold.py"]
states:
  unit_lifecycle:
    initial: alive
    nodes:
      - { id: alive }
      - { id: stunned }
      - { id: dead, terminal: true }
    transitions:
      - { from: alive,   event: "{events.stun_applied}", to: stunned }
      - { from: stunned, event: "{events.stun_expires}", to: alive }
      - { from: alive,   event: "{events.hp_zero}",      to: dead }
      - { from: stunned, event: "{events.hp_zero}",      to: dead }
events:
  stun_applied:
    status: draft
    description: "A deployed unit gains the stunned state."
  stun_expires:
    status: draft
    description: "A unit's stun counter reaches 0 and they return to alive."
  hp_zero:
    status: draft
    description: "A unit's hp reaches 0; they enter the dead terminal node."
rules:
  unit_deployed:
    given:
      verb: "{verbs.deploy_units}"
    target_selection: explicit
    do:
      - { kind: instantiate_unit_in_container, container: "{entities.deployed_units}" }
    outputs: [unit_deployed_event]
    status: draft
    implemented_in: ["src/rules/unit_deployed.py"]
  tick_resolution:
    given:
      driver: "{clocks.tick}"
    target_selection: first_alive_opposite
    do:
      - { kind: select_actor, from_container: "{entities.deployed_units}", using: "{distributions.action_order}", index_by: tick_number }
      - { kind: sample, from: "{distributions.damage_roll}", params_from: { mean: "{actor.attack}" }, into: damage }
      - { kind: apply_damage, target: target, amount: damage, field: hp }
    outputs: [tick_resolved_event]
    status: draft
    implemented_in: ["src/rules/tick_resolution.py"]
  match_resolution:
    given:
      verb: "{verbs.resolve_match}"
    do:
      - { kind: declare_winner }
    outputs: [match_resolved_event]
    status: draft
    implemented_in: ["src/rules/match_resolution.py"]
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `states`, `events`, `rules`.
The `tick_resolution` rule is clock-driven (`given.driver: "{clocks.tick}"`)
— it fires on each clock tick, not in response to a player verb.

## Rationale

**Clock-driven rule pattern.** The `tick_resolution` rule's `do:` block
demonstrates the F-010 + F-008 + D-019 composition: `select_actor` from a
container using a distribution, sample damage with `params_from:` reading
from the actor's template field, apply damage to a `per_instance_state`
field. Writes to `hp` are legal (declared in per_instance_state); a write
to `attack` would be lint-errored because `attack` is a template field.

**`unit_lifecycle` state machine.** The state lives on `deployed_units.
per_instance_state.lifecycle` per the D-019 binding. State transitions on
an instance fire via the same per_instance_state binding.
