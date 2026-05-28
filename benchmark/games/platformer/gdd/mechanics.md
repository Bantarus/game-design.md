---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/embergrave/**/*"]
entities:
  player_moth:
    type: actor
    properties:
      hp:             { from: "{resources.hp}" }
      ember:          { from: "{resources.ember}" }
      position_x:     { fixed_point: micro_units }
      position_y:     { fixed_point: micro_units }
      velocity_x:     { fixed_point: micro_units_per_tick }
      velocity_y:     { fixed_point: micro_units_per_tick }
      movement_state: "{states.moth_movement}"
    status: draft
    implemented_in: ["src/embergrave/entities/player_moth.py"]
  levels:
    type: content_collection
    data_source: ../../content/levels
    count_target: 40
    status: draft
  ember_pickup:
    type: terrain
    properties:
      position_x:    { fixed_point: micro_units }
      position_y:    { fixed_point: micro_units }
      ember_value:   { type: integer, default: 1 }
      collected:     { type: boolean, default: false }
    status: draft
    implemented_in: ["src/embergrave/entities/ember_pickup.py"]
  checkpoint:
    type: terrain
    properties:
      position_x:    { fixed_point: micro_units }
      position_y:    { fixed_point: micro_units }
      touched:       { type: boolean, default: false }
    status: draft
    implemented_in: ["src/embergrave/entities/checkpoint.py"]
verbs:
  jump:
    actor: "{entities.player_moth}"
    cost: { resource: "{resources.ember}", amount: 0 }
    target_schema: { type: input_event }
    effects:
      - { resolve: "{rules.jump_resolution}" }
    feel: "{feel.jump}"
    status: draft
    implemented_in: ["src/embergrave/verbs/jump.py"]
  dash:
    actor: "{entities.player_moth}"
    cost: { resource: "{resources.ember}", amount: 3 }
    target_schema: { type: input_event }
    effects:
      - { resolve: "{rules.dash_resolution}" }
    feel: "{feel.dash}"
    status: draft
    implemented_in: ["src/embergrave/verbs/dash.py"]
  glide:
    actor: "{entities.player_moth}"
    cost: { resource: "{resources.ember}", amount: 1 }
    target_schema: { type: input_event }
    effects:
      - { resolve: "{rules.glide_resolution}" }
    feel: "{feel.glide}"
    status: draft
    implemented_in: ["src/embergrave/verbs/glide.py"]
  refuel_ember:
    actor: system
    cost: 0
    target_schema:
      type:   "{entities.ember_pickup}"
      filter: "uncollected_and_overlapping_moth"
    effects:
      - { resolve: "{rules.ember_collection}" }
    status: draft
    implemented_in: ["src/embergrave/verbs/refuel_ember.py"]
  touch_checkpoint:
    actor: system
    cost: 0
    target_schema:
      type:   "{entities.checkpoint}"
      filter: "untouched_and_overlapping_moth"
    effects:
      - { resolve: "{rules.checkpoint_activation}" }
    status: draft
    implemented_in: ["src/embergrave/verbs/touch_checkpoint.py"]
  restart_at_checkpoint:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.respawn}" }
    status: draft
    implemented_in: ["src/embergrave/verbs/restart_at_checkpoint.py"]
  enter_level:
    actor: system
    cost: 0
    target_schema: { type: "{entities.levels}" }
    effects:
      - { resolve: "{rules.level_setup}" }
    status: draft
    implemented_in: ["src/embergrave/verbs/enter_level.py"]
  exit_level:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.level_completion}" }
    status: draft
    implemented_in: ["src/embergrave/verbs/exit_level.py"]
  reach_summit:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.expedition_completion}" }
    status: draft
    implemented_in: ["src/embergrave/verbs/reach_summit.py"]
resources:
  hp:
    scope: per_run
    min: 0
    max: 1
    visibility: hud
    status: draft
    implemented_in: ["src/embergrave/resources/hp.py"]
  ember:
    scope: per_run
    min: 0
    max: 12
    velocity_target: "{balance_targets.ember_velocity}"
    visibility: hud
    status: draft
    implemented_in: ["src/embergrave/resources/ember.py"]
states:
  moth_movement:
    initial: grounded
    nodes:
      - { id: grounded }
      - { id: airborne }
      - { id: dashing }
      - { id: gliding }
      - { id: dead, terminal: true }
    transitions:
      - { from: grounded,  event: "{events.jump_pressed}", to: airborne, side_effects: ["set vertical velocity from jump impulse"] }
      - { from: grounded,  event: "{events.walk_off_ledge}", to: airborne }
      - { from: airborne,  event: "{events.dash_pressed}", to: dashing, side_effects: ["{resources.ember} -= 3", "set horizontal velocity from dash impulse"] }
      - { from: airborne,  event: "{events.glide_pressed}", to: gliding, side_effects: ["{resources.ember} -= 1"] }
      - { from: airborne,  event: "{events.land}", to: grounded }
      - { from: dashing,   event: "{events.dash_duration_expired}", to: airborne }
      - { from: gliding,   event: "{events.glide_released}", to: airborne }
      - { from: gliding,   event: "{events.ember_depleted}", to: airborne }
      - { from: gliding,   event: "{events.land}", to: grounded }
      - { from: dashing,   event: "{events.land}", to: grounded }
      - { from: grounded,  event: "{events.death_zone_hit}", to: dead }
      - { from: airborne,  event: "{events.death_zone_hit}", to: dead }
      - { from: dashing,   event: "{events.death_zone_hit}", to: dead }
      - { from: gliding,   event: "{events.death_zone_hit}", to: dead }
  level_progress:
    initial: not_started
    nodes:
      - { id: not_started }
      - { id: active }
      - { id: completed, terminal: true }
    transitions:
      - { from: not_started, event: "{events.level_entered}",   to: active }
      - { from: active,      event: "{events.level_exit_reached}", to: completed }
events:
  jump_pressed:
    status: draft
    description: "Player presses the jump input button; emitted by {verbs.jump}."
  dash_pressed:
    status: draft
    description: "Player presses the dash input button; emitted by {verbs.dash}."
  glide_pressed:
    status: draft
    description: "Player presses-and-holds the glide input button; emitted by {verbs.glide}."
  glide_released:
    status: draft
    description: "Player releases the glide button (or duration expires); emitted by {verbs.glide} on release."
  dash_duration_expired:
    status: draft
    description: "The fixed-duration dash window ends; emitted by {rules.dash_resolution}."
  ember_depleted:
    status: draft
    description: "{resources.ember} reaches 0 during gliding; emitted by {rules.glide_resolution}."
  walk_off_ledge:
    status: draft
    description: "The moth's grounded check fails one tick after being grounded (no jump input); emitted by {rules.physics_tick}."
  land:
    status: draft
    description: "An airborne moth's grounded check succeeds; emitted by {rules.physics_tick}."
  death_zone_hit:
    status: draft
    description: "The moth's bounding box overlaps a lethal-tagged terrain region; emitted by {rules.physics_tick}."
  level_entered:
    status: draft
    description: "The level loop begins; emitted by {verbs.enter_level}."
  level_exit_reached:
    status: draft
    description: "The moth overlaps the level's exit position; emitted by {rules.physics_tick}."
---

## Tokens

This file owns the four flat namespaces of the moment-to-moment game: `entities`, `verbs`, `resources`, `states`. It also owns `events`, the named-event namespace that `states` transitions reference. The `rules` namespace lives in `gdd/systems/physics.md`.

## Rationale

**Entities — four kinds.** The player moth is the single actor; levels are a content_collection (~40 designed); ember pickups and checkpoints are `terrain` (per-level placed instances). No enemies exist as entities at all — combat is a non-goal (`{pillars}` rejection), and "obstacles" are pure level geometry rather than entity instances.

**Position is fixed-point integer.** All `position_x/y` and `velocity_x/y` fields use `fixed_point: micro_units` (one micro_unit = 1/1000 of a world unit). This is the architectural commitment that makes the simulation deterministic given input — float position breaks byte-identical replay (see `{invariants.fixed_point_simulation_state}`). The presentation layer renders by dividing back to floats for screen-space pixels; the simulation layer never sees those floats.

**Verbs — three input verbs declare feel, six are mechanical glue.** `jump`, `dash`, and `glide` are the three the player feels per-millisecond — each declares a `feel:` ref to `gdd/feel.md`. The six others (`refuel_ember`, `touch_checkpoint`, `restart_at_checkpoint`, `enter_level`, `exit_level`, `reach_summit`) are system-actor verbs that resolve game state without a haptic moment. `feel:` is reserved for verbs the player consciously *commits* to. The per-tick physics simulation is fired by `{clocks.physics}` (spec §4.7, F-010 v0.3 resolution) rather than by a synthetic verb — see `gdd/clocks.md`.

**Time-passage is modeled as a first-class clock at v0.3.** Embergrave's per-tick physics simulation has no natural player-verb to attach to — the simulation advances every tick (60 Hz) regardless of input. In the original v0.1 / v0.2.0-alpha authoring this required a synthetic `verbs.advance_tick` whose sole purpose was to satisfy the spec's verb-triggers-rule pattern; the friction was logged as a v0.3 candidate finding (F-010). F-010's resolution at v0.3 adds the first-class `clocks` namespace (spec §4.7), and Embergrave's per-tick driver is now `{clocks.physics}` (continuous mode, 60 Hz, drives `{rules.physics_tick}`). See `gdd/clocks.md`.

**Resources — hp and ember.** `hp` is per_run with max 1 — every hit is lethal; this is the "one-hit-kill platformer" design call. `ember` is per_run with max 12 (12 dashes' worth if hoarded; ~4 dashes plus 12 short glides in practice). `ember.velocity_target` ties to `{balance_targets.ember_velocity}` — the design call is that a skilled player on a tier-3 level burns and refuels ember at a rate that keeps the meter visible-but-tense (median 4-6 ember mid-level).

**States — two named machines.** `moth_movement` is the moment-to-moment FSM with five nodes; `dead` is terminal and triggers `{verbs.restart_at_checkpoint}` from outside the machine. `level_progress` is the per-session FSM with three nodes; `completed` is terminal. Both are total: every non-terminal node has at least one outgoing transition. State-machine-coverage lint passes.

**Events — first-class tokens (D-005).** Every transition's `event:` value is a `{events.<id>}` ref, owned by this file's `events:` namespace. The deckbuilder's pattern is mirrored: events declare `status` and `description`, and `implemented_in` for status >= prototyped (not required at draft).

**`rules.*` are declared at status: draft in `gdd/systems/physics.md`.** Ten rules govern the simulation: `physics_tick` (per-tick collision + emission), three input-resolution rules (`jump_resolution`, `dash_resolution`, `glide_resolution`), and six system-resolution rules (`ember_collection`, `checkpoint_activation`, `respawn`, `level_setup`, `level_completion`, `expedition_completion`). All ten are at `status: draft` with `implemented_in:` pointing at planned paths; the benchmark's medium and hard tasks involve adding new rules (or new verb/rule pairs) that interact with this rule set.

## Open Questions

- Whether `moth_movement.gliding` should be a *sub-state* of `airborne` rather than a peer (the moth is airborne while gliding — strictly the FSM has them parallel). Argument for refactor: matches mental model. Argument against: flat machines are easier to lint. Currently flat.
- Whether `walk_off_ledge` should be a distinct event from `jump_pressed` or whether both should resolve through a unified `become_airborne` event. Currently distinct because the *side effects* differ (jump applies impulse; walk-off does not).
- Whether to allow `dash → gliding` direct transition (currently must pass through `airborne`). Argument for: better aerial combos. Argument against: gives the player too many in-air options, contradicts the "every jump is a commitment" pillar. Currently no.
