---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
entities:
  player:
    type: actor
    properties:
      gold:           { from: "{resources.gold}" }
      roster_size:    5
    status: draft
    implemented_in: []
  units:
    type: content_collection
    data_source: ../../content/units
    count_target: 24
    status: draft
verbs:
  deploy_unit:
    actor: "{entities.player}"
    cost: { resource: "{resources.gold}", amount: varies_by_unit }
    target_schema:
      type:   "{entities.units}"
      filter: roster
    effects:
      - { kind: spawn_on_grid }
    status: draft
    implemented_in: []
  set_formation:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: grid_tile }
    effects:
      - { kind: arrange_deployed_units }
    status: draft
    implemented_in: []
  start_combat:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { kind: transition_combat_phase, to: ticking }
    status: draft
    implemented_in: []
  advance_tick:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.tick_resolution}" }
    status: draft
    implemented_in: []
  resolve_combat:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.combat_resolution}" }
    status: draft
    implemented_in: []
  collect_reward:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: gold }
    effects:
      - { kind: gain, resource: "{resources.gold}" }
    status: draft
    implemented_in: []
resources:
  gold:
    scope: permanent
    min: 0
    max: 9999
    velocity_target: "{balance_targets.gold_per_encounter}"
    visibility: hud
    status: draft
    implemented_in: []
states:
  unit_lifecycle:
    initial: alive
    nodes:
      - { id: alive }
      - { id: stunned }
      - { id: dead, terminal: true }
    transitions:
      - { from: alive,   event: stun,    to: stunned }
      - { from: stunned, event: recover, to: alive }
      - { from: alive,   event: hp_zero, to: dead }
      - { from: stunned, event: hp_zero, to: dead }
  combat_phase:
    initial: setup
    nodes:
      - { id: setup }
      - { id: ticking }
      - { id: resolved, terminal: true }
    transitions:
      - { from: setup,   event: start_combat,    to: ticking }
      - { from: ticking, event: one_side_cleared, to: resolved }
rules:
  tick_resolution:
    given:
      verb: "{verbs.advance_tick}"
    do:
      - sample: "{distributions.action_order}"
      - resolve_unit_action
      - sample: "{distributions.damage_roll}"
        round: half_to_even
      - sample: "{distributions.critical_hit}"
        on_hit_multiply_by: 2
      - apply_damage_to_target: integer_only
    outputs: [tick_resolved_event, damage_event]
    status: draft
    implemented_in: []
  combat_resolution:
    given:
      verb: "{verbs.resolve_combat}"
    do:
      - sample: "{distributions.gold_drop}"
      - award_gold_to_winner
    outputs: [combat_resolved_event]
    status: draft
    implemented_in: []
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `states`, and `rules` for Lockstep. Distributions live in `gdd/systems/distributions.md`.

## Rationale

**Verbs are roles, not buttons.** Three verbs are player-issued (`deploy_unit`, `set_formation`, `start_combat`); three are system-issued (`advance_tick`, `resolve_combat`, `collect_reward`). The `actor:` field distinguishes them — `actor: "{entities.player}"` vs. `actor: system`.

**The tick is one rule.** `{rules.tick_resolution}` walks the deterministic action order and applies a single unit's action. Repeating it ~120 times *is* an encounter. The simplicity is deliberate: replay determinism depends on the rule being a single function, not a tangle of sub-rules.

**State machines.** `{states.unit_lifecycle}` has a recoverable `stunned` node — units can return to `alive` via the `recover` event before `hp_zero` kills them. `{states.combat_phase}` is a strict three-step machine ending at the absorbing `resolved` node.
