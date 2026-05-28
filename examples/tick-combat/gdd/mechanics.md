---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: prototyped
last_verified: "2026-05-22"
implemented_in:
  - "impl/xtreme/src/components.rs"
  - "impl/xtreme/src/resources.rs"
  - "impl/xtreme/src/state.rs"
  - "impl/xtreme/src/rules.rs"
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
  deployed_units:
    type: instance_container
    capacity: 10
    holds_template_from: "{entities.units}"
    per_instance_state:
      side:           { enum: [player, enemy] }
      deploy_order:   { type: integer, minimum: 0, maximum: 4 }
      hp:             { type: integer, minimum: 0 }
      lifecycle:      { enum: [alive, stunned, dead], default: alive }
      stun_remaining: { type: integer, minimum: 0, default: 0 }
    status: draft
    implemented_in: ["impl/xtreme/src/components.rs"]
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
      - { from: alive,   event: "{events.stun}",    to: stunned }
      - { from: stunned, event: "{events.recover}", to: alive }
      - { from: alive,   event: "{events.hp_zero}", to: dead }
      - { from: stunned, event: "{events.hp_zero}", to: dead }
  combat_phase:
    initial: setup
    nodes:
      - { id: setup }
      - { id: ticking }
      - { id: resolved, terminal: true }
    transitions:
      - { from: setup,   event: "{events.start_combat}",     to: ticking }
      - { from: ticking, event: "{events.one_side_cleared}", to: resolved }
events:
  stun:
    status: draft
    description: "A status effect is applied that prevents the unit from acting on its tick."
  recover:
    status: draft
    description: "A stunned unit's stun duration expires at the start of its tick."
  hp_zero:
    status: draft
    description: "A unit's hp reaches 0 from any damage source; emitted by {rules.tick_resolution}."
  start_combat:
    status: draft
    description: "The player commits the formation and combat begins; emitted by {verbs.start_combat}."
  one_side_cleared:
    status: draft
    description: "All units on one side enter the {states.unit_lifecycle.dead} terminal node."
rules:
  tick_resolution:
    given:
      driver: "{clocks.tick}"
    # D-013: target is the first alive unit on the opposite side, in
    # deployment order. target_selection iterates the actor's container
    # ({entities.deployed_units}) by default per spec §4.5.
    target_selection: first_alive_opposite
    do:
      # D-011: every step is a structured object (no bare prose strings).
      # D-019: actor is selected from the deployed_units instance_container
      # via the canonical clock-driven pattern (spec §4.5).
      - kind: select_actor
        from_container: "{entities.deployed_units}"
        using: "{distributions.action_order}"
        index_by: tick_number     # rotation: actor = order[tick mod len(order)]
      - kind: sample
        from: "{distributions.damage_roll}"
        into: damage
      - kind: sample
        from: "{distributions.critical_hit}"
        into: crit
      # D-019: `field: hp` declares the per_instance_state write; the lint
      # rule `write-to-template-field` validates hp lives in the target
      # container's per_instance_state schema.
      - kind: apply_damage
        target: target            # resolved via target_selection
        field: hp
        amount:
          base: damage
          multiplier_if: { crit: 2 }
        domain: integer           # belt-and-suspenders post-rounding clamp
    outputs: [tick_resolved_event, damage_event]
    status: prototyped
    implemented_in: ["impl/xtreme/src/rules.rs"]
  combat_resolution:
    given:
      verb: "{verbs.resolve_combat}"
    target_selection: none        # no target; awards gold globally
    do:
      - kind: sample
        from: "{distributions.gold_drop}"
        count: 6                   # D-014 / D-013-resolution of ambiguity #6
        accumulate: value          # sum the per-drop value fields
        into: total_gold
      - kind: gain_resource
        resource: "{resources.gold}"
        amount: total_gold
    outputs: [combat_resolved_event]
    status: prototyped
    implemented_in: ["impl/xtreme/src/rules.rs"]
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `states`, and `rules` for Lockstep. Distributions live in `gdd/systems/distributions.md`.

## Rationale

**Verbs are roles, not buttons.** Three verbs are player-issued (`deploy_unit`, `set_formation`, `start_combat`); two are system-issued (`resolve_combat`, `collect_reward`). The `actor:` field distinguishes them — `actor: "{entities.player}"` vs. `actor: system`. The per-tick simulation is fired by `{clocks.tick}` (spec §4.7, F-010 v0.3 resolution) rather than by a synthetic verb — see `gdd/clocks.md`.

**The tick is one rule.** `{rules.tick_resolution}` walks the deterministic action order and applies a single unit's action. Repeating it ~120 times *is* an encounter. The simplicity is deliberate: replay determinism depends on the rule being a single function, not a tangle of sub-rules.

**State machines.** `{states.unit_lifecycle}` has a recoverable `stunned` node — units can return to `alive` via the `recover` event before `hp_zero` kills them. `{states.combat_phase}` is a strict three-step machine ending at the absorbing `resolved` node.

**Deployed units carry per-instance state via `instance_container` (F-008 v0.3 resolution).** `{entities.units}` is the content_collection of unit templates (24 designed units, each in `content/units/*.yaml` carrying immutable template fields like `attack`, `max_hp`, `abilities`). `{entities.deployed_units}` is the `instance_container` (spec §4.1) that holds the up-to-10 deployed runtime instances (5 per side) with per_instance_state for `side`, `deploy_order`, `hp` (current, distinct from template `max_hp`), `lifecycle` (alive / stunned / dead, the state machine's runtime node), and `stun_remaining` (ticks of stun left). Tick resolution writes to `hp` (per D-019 spec §3 + §4.5; the `field: hp` declaration on the apply_damage step is validated by the `write-to-template-field` lint rule, which would catch a typo like `field: attack` since attack lives on the template, not per_instance_state). State-machine transitions on `lifecycle` fire through the same per_instance_state binding: a unit hitting `hp == 0` emits `{events.hp_zero}` which the `unit_lifecycle` machine consumes to transition the instance to the `dead` node.
