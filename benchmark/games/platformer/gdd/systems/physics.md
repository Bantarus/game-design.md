---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/embergrave/rules/**/*"]
rules:
  physics_tick:
    given:
      verb: "{verbs.advance_tick}"
    do:
      - { kind: advance_positions, by: "velocity * dt", dt_ticks: 1 }
      - { kind: apply_gravity, magnitude: "gravity_constant", to: "{entities.player_moth}" }
      - { kind: collision_check, target: "level_terrain", on_solid_floor: { emit: "{events.land}" }, on_solid_lateral: { reflect_velocity: 0 } }
      - { kind: collision_check, target: "lethal_regions", on_hit: { emit: "{events.death_zone_hit}" } }
      - { kind: overlap_check, target: "{entities.ember_pickup}", on_overlap: { emit_verb: "{verbs.refuel_ember}" } }
      - { kind: overlap_check, target: "{entities.checkpoint}", on_overlap: { emit_verb: "{verbs.touch_checkpoint}" } }
      - { kind: overlap_check, target: "level_exit", on_overlap: { emit: "{events.level_exit_reached}" } }
      - { kind: grounded_check, on_walk_off: { emit: "{events.walk_off_ledge}" } }
      - { kind: ember_drain_if_gliding, amount_per_tick: "1/60" }
      - { kind: state_check, when: "{states.moth_movement}", on_dead: { emit_verb: "{verbs.restart_at_checkpoint}" } }
    outputs: [position_updated, state_transitions_emitted, verb_emissions_queued]
    status: draft
    implemented_in: ["src/embergrave/rules/physics_tick.py"]
  jump_resolution:
    given:
      verb: "{verbs.jump}"
      state: "{states.moth_movement}"
    do:
      - { kind: check_state, must_be_in: grounded }
      - { kind: set_velocity_y, value: "jump_impulse" }
      - { kind: emit_event, value: "{events.jump_pressed}" }
    outputs: [velocity_set, event_emitted]
    status: draft
    implemented_in: ["src/embergrave/rules/jump_resolution.py"]
  dash_resolution:
    given:
      verb: "{verbs.dash}"
      state: "{states.moth_movement}"
    do:
      - { kind: check_state, must_be_in: airborne }
      - { kind: check_resource, resource: "{resources.ember}", min: 3, on_insufficient: { reject: true } }
      - { kind: spend_resource, resource: "{resources.ember}", amount: 3 }
      - { kind: set_velocity_x, value: "dash_impulse * direction" }
      - { kind: set_dash_duration_remaining, ticks: 12 }
      - { kind: emit_event, value: "{events.dash_pressed}" }
    outputs: [velocity_set, ember_spent, event_emitted]
    status: draft
    implemented_in: ["src/embergrave/rules/dash_resolution.py"]
  glide_resolution:
    given:
      verb: "{verbs.glide}"
      state: "{states.moth_movement}"
    do:
      - { kind: check_state, must_be_in: airborne }
      - { kind: check_resource, resource: "{resources.ember}", min: 1, on_insufficient: { reject: true } }
      - { kind: apply_velocity_damping, multiplier_y: 0.3, multiplier_x: 1.0 }
      - { kind: emit_event, value: "{events.glide_pressed}" }
      - { kind: continuous_ember_drain, while_held: true, on_depleted: { emit: "{events.ember_depleted}" } }
    outputs: [velocity_damped, event_emitted]
    status: draft
    implemented_in: ["src/embergrave/rules/glide_resolution.py"]
  ember_collection:
    given:
      verb: "{verbs.refuel_ember}"
    do:
      - { kind: read_property, source: "ember_pickup.ember_value", into: "delta" }
      - { kind: refund_resource, resource: "{resources.ember}", amount: "delta" }
      - { kind: mark_collected, target: "ember_pickup" }
    outputs: [ember_increased, pickup_consumed]
    status: draft
    implemented_in: ["src/embergrave/rules/ember_collection.py"]
  checkpoint_activation:
    given:
      verb: "{verbs.touch_checkpoint}"
    do:
      - { kind: mark_touched, target: "checkpoint" }
      - { kind: set_respawn_position, value: "checkpoint.position" }
    outputs: [checkpoint_touched, respawn_position_set]
    status: draft
    implemented_in: ["src/embergrave/rules/checkpoint_activation.py"]
  respawn:
    given:
      verb: "{verbs.restart_at_checkpoint}"
    do:
      - { kind: read_property, source: "respawn_position", into: "spawn" }
      - { kind: set_position, target: "{entities.player_moth}", value: "spawn" }
      - { kind: zero_velocity, target: "{entities.player_moth}" }
      - { kind: reset_state, state: "{states.moth_movement}", to: grounded }
      - { kind: refund_resource, resource: "{resources.hp}", to: max }
      - { kind: refund_resource, resource: "{resources.ember}", to: max }
    outputs: [moth_respawned, state_reset]
    status: draft
    implemented_in: ["src/embergrave/rules/respawn.py"]
  level_setup:
    given:
      verb: "{verbs.enter_level}"
    do:
      - { kind: load_level_data, source: "target_level" }
      - { kind: instantiate_ember_pickups, from: "level.ember_pickups" }
      - { kind: instantiate_checkpoints, from: "level.checkpoints" }
      - { kind: instantiate_lethal_regions, from: "level.lethal_regions" }
      - { kind: set_position, target: "{entities.player_moth}", value: "level.entry" }
      - { kind: reset_state, state: "{states.level_progress}", to: not_started }
      - { kind: transition_state, state: "{states.level_progress}", via: "{events.level_entered}" }
    outputs: [level_loaded, state_transitioned]
    status: draft
    implemented_in: ["src/embergrave/rules/level_setup.py"]
  level_completion:
    given:
      verb: "{verbs.exit_level}"
    do:
      - { kind: transition_state, state: "{states.level_progress}", via: "{events.level_exit_reached}" }
      - { kind: record_completion_stats, fields: [deaths_this_level, time_elapsed_ms, ember_collected_pct] }
      - { kind: persist_level_completed, target: "level.id" }
    outputs: [level_completed, stats_recorded]
    status: draft
    implemented_in: ["src/embergrave/rules/level_completion.py"]
  expedition_completion:
    given:
      verb: "{verbs.reach_summit}"
    do:
      - { kind: assert_all_summit_levels_completed }
      - { kind: record_expedition_stats, fields: [total_deaths, total_time_ms, ember_collected_overall_pct] }
      - { kind: present_summit_screen }
    outputs: [expedition_completed, stats_recorded]
    status: draft
    implemented_in: ["src/embergrave/rules/expedition_completion.py"]
---

## Tokens

This file owns the `rules` namespace for Embergrave. Ten rules total: `physics_tick` is the per-tick driver; three are input-resolution rules (one per declaring-feel verb); six are system-resolution rules (each invoked by exactly one system-actor verb). Every rule's `given.verb` references a verb declared in `gdd/mechanics.md`; every `do:` step is a structured object (no bare strings, per D-011's determinism-undetermined-rule advisory).

## Rationale

**`physics_tick` is the simulation heart.** It runs once per simulation tick (60Hz, fixed timestep per `{invariants.fixed_timestep_simulation}`), advances positions by velocity, applies gravity, checks collisions against terrain and lethal regions, and emits events or system verbs in response. The `do:` steps are an ordered sequence — positions advance before collision is checked; collision against lethal terrain emits `death_zone_hit` *before* checkpoint overlap is checked (so a moth that lands in lava at the same frame it touches a checkpoint dies cleanly, no half-state).

**Input-resolution rules are short and structured.** `jump_resolution`, `dash_resolution`, `glide_resolution` each: check the current state, check (where relevant) the ember resource, apply the velocity/state change, and emit the event that drives the state-machine transition. The `dash_resolution` pattern is the canonical example: ember check is at the *start* (rejection before any side effect), then atomic spend + velocity-set + emit. A future implementer must preserve this order — applying velocity before checking ember would leave a no-op-dash visible to the player.

**System-resolution rules manipulate world state but don't move the moth directly.** `ember_collection`, `checkpoint_activation`, `respawn`, `level_setup`, `level_completion`, `expedition_completion` each handle a specific system-state transition. `respawn` is the cheapest-feeling but most important: it must complete in <200ms wall-clock to honor the "death is cheap" pillar — implementations should pre-warm the respawn target position and avoid level reloading.

**No rule references a distribution.** Embergrave has no gameplay RNG (see `gdd/systems/distributions.md`); the only declared distribution is `ember_flicker_jitter` which is cosmetic-only and lives in the presentation layer. Rules here therefore declare no `sample:` steps. This is the deliberate "low-RNG is a design choice" structure of the platformer — see the spec's `undefined-distribution` linter rule, which fires when stochastic ops omit a distribution reference; we have no stochastic ops to omit.

**Structured `do:` steps are required.** Every step is a YAML map with a `kind:` discriminator. Bare-string steps (e.g. `"resolve_unit_action"`) would fire the `determinism-undetermined-rule` advisory because the platformer's loops are `timescale: moment`. The discipline lives here at the rules layer: every step a future implementer reads is a parseable structure, not a prose label.

## Open Questions

- Whether `physics_tick.do[2]`'s `on_solid_lateral: reflect_velocity: 0` is the right behavior (current call: lateral collision zeroes horizontal velocity, mimicking a wall). Alternative: `clamp_to_wall` (the moth slides along the wall). Currently 0-reflect; precision-platformer tradition favors clean stops over wall-sliding.
- Whether `respawn` should be split into `respawn_state_reset` and `respawn_position_set` rules (two-phase respawn for animation). Currently one atomic rule. Re-evaluate if the cheap-death feel needs splitting at implementation.
- Whether `level_completion.do`'s `record_completion_stats` should include `ember_collected_pct` as `delta_from_total_ember` or as the absolute count. Currently the schema says `pct` (proportion); pct is robust to per-level ember-pickup-count variance.
- Whether to consolidate the four `collision_check`/`overlap_check` steps in `physics_tick` into a single `spatial_query` step. Argument for: cleaner. Argument against: order-of-resolution matters (lethal first, pickup second, checkpoint third, exit fourth — the conceptual priority of "dying always wins, then collecting"). Currently separate.
