---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/driftwood/mechanics/**/*"]
entities:
  player:
    type: actor
    properties:
      position: { kind: world_coordinate }
      inventory: { from: "{entities.player_inventory}" }
      hp: { from: "{resources.hp}" }
      hunger: { from: "{resources.hunger}" }
      thirst: { from: "{resources.thirst}" }
    status: draft
    implemented_in: ["src/driftwood/mechanics/player.py"]
  player_inventory:
    type: instance_container
    capacity: 12
    holds_template_from: "{entities.recipes}"
    per_instance_state:
      remaining_durability: { type: integer, minimum: 0 }
      quantity:             { type: integer, minimum: 1, maximum: 8, default: 1 }
    status: draft
    implemented_in: ["src/driftwood/mechanics/inventory.py"]
  resource_node:
    type: terrain
    properties:
      kind: { enum: [tree, stone_outcrop, fiber_plant, berry_bush, tidepool, spring, flint_outcrop] }
      yield_per_harvest_baseline: { type: integer, minimum: 0 }
      yield_per_harvest_with_correct_tool: { type: integer, minimum: 0 }
      remaining_harvests: { type: integer, minimum: 0 }
      renewal: { enum: [none, per_day, infinite] }
    status: draft
    implemented_in: ["src/driftwood/mechanics/resource_node.py"]
  crafting_station:
    type: system_object
    properties:
      kind: { enum: [campfire, sawhorse, shelter, still] }
      position: { kind: world_coordinate }
      durability: { type: integer, minimum: 0 }
    status: draft
    implemented_in: ["src/driftwood/mechanics/crafting_station.py"]
  recipes:
    type: content_collection
    data_source: ../../content/recipes
    status: draft
    count_target: 12
  pyre:
    type: system_object
    properties:
      assembled_layers: { type: integer, minimum: 0, maximum: 4 }
      lit: { type: boolean }
      position_at: high_point
    status: draft
    implemented_in: ["src/driftwood/mechanics/pyre.py"]
verbs:
  gather:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 30, condition: tool_present, else_in_game_minutes: 60 }
    target_schema:
      type: "{entities.resource_node}"
      filter: "adjacent_to_actor_and_has_remaining_harvests"
    effects:
      - { resolve: "{rules.gather_resolution}" }
    feel: "{feel.gather}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/gather.py"]
  craft:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 60 }
      consumes: target_recipe_inputs
    target_schema:
      type: "{entities.recipes}"
      filter: "recipe_station_required_or_adjacent_to_station"
    effects:
      - { resolve: "{rules.craft_resolution}" }
    feel: "{feel.craft}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/craft.py"]
  eat:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 15 }
      consumes: target_food_item
    target_schema:
      type: "{entities.player_inventory}"
      filter: "tag_equals_food"
    effects:
      - { resolve: "{rules.eat_resolution}" }
    feel: "{feel.eat}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/eat.py"]
  drink:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 15 }
    target_schema:
      type: "{entities.resource_node}"
      filter: "node_kind_in_spring_or_still_and_adjacent_to_actor"
    effects:
      - { resolve: "{rules.drink_resolution}" }
    feel: "{feel.drink}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/drink.py"]
  place_station:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 60 }
      consumes: station_recipe_inputs
    target_schema:
      type: "{entities.crafting_station}"
      filter: "actor_in_camp_region_OR_station_kind_is_pyre_layer_at_high_point"
    effects:
      - { resolve: "{rules.place_station_resolution}" }
    feel: "{feel.place_station}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/place_station.py"]
  sleep_through_night:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_hours: hours_until_dawn }
    target_schema:
      type: world_coordinate
      filter: "adjacent_to_shelter_or_open_air_at_camp"
    effects:
      - { resolve: "{rules.sleep_resolution}" }
    feel: "{feel.sleep}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/sleep.py"]
  assemble_pyre:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 90 }
      consumes: pyre_layer_recipe_inputs
    target_schema:
      type: "{entities.pyre}"
      filter: "actor_at_high_point_AND_pyre_assembled_layers_lt_4"
    effects:
      - { resolve: "{rules.assemble_pyre_resolution}" }
    feel: "{feel.assemble_pyre}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/assemble_pyre.py"]
  light_pyre:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 5 }
      consumes: one_flint_shard
    target_schema:
      type: "{entities.pyre}"
      filter: "pyre_assembled_layers_eq_4_AND_day_eq_5_AND_part_eq_evening"
    effects:
      - { resolve: "{rules.light_pyre_resolution}" }
    feel: "{feel.light_pyre}"
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/light_pyre.py"]
  start_day:
    actor: "{entities.player}"
    cost:
      time_cost: { in_game_minutes: 0 }
    target_schema:
      type: world_clock
      filter: "world_clock_part_is_night_AND_dawn_due"
    effects:
      - { resolve: "{rules.start_day_resolution}" }
    status: draft
    implemented_in: ["src/driftwood/mechanics/verbs/start_day.py"]
resources:
  hp:
    scope: per_run
    min: 0
    max: 12
    velocity_target: "{balance_targets.hp_band_at_run_end}"
    visibility: hud
    status: draft
    implemented_in: ["src/driftwood/mechanics/resources/hp.py"]
  hunger:
    scope: per_run
    min: 0
    max: 12
    velocity_target: "{balance_targets.hunger_decay_rate}"
    visibility: hud
    status: draft
    implemented_in: ["src/driftwood/mechanics/resources/hunger.py"]
  thirst:
    scope: per_run
    min: 0
    max: 12
    velocity_target: "{balance_targets.thirst_decay_rate}"
    visibility: hud
    status: draft
    implemented_in: ["src/driftwood/mechanics/resources/thirst.py"]
states:
  world_clock:
    initial: morning_day_1
    nodes:
      - { id: morning_day_1 }
      - { id: afternoon }
      - { id: evening }
      - { id: night }
      - { id: morning_subsequent }
      - { id: rescued,        terminal: true }
      - { id: missed_rescue,  terminal: true }
      - { id: dead,           terminal: true }
    transitions:
      - { from: morning_day_1,      event: "{events.day_part_elapsed}", to: afternoon }
      - { from: afternoon,          event: "{events.day_part_elapsed}", to: evening }
      - { from: evening,            event: "{events.day_part_elapsed}", to: night }
      - { from: night,              event: "{events.dawn_after_sleep}", to: morning_subsequent }
      - { from: morning_subsequent, event: "{events.day_part_elapsed}", to: afternoon }
      - { from: night,              event: "{events.pyre_lit_at_dawn}", to: rescued }
      - { from: night,              event: "{events.day_5_passed}",     to: missed_rescue }
      - { from: morning_day_1,      event: "{events.hp_reached_zero}",  to: dead }
      - { from: afternoon,          event: "{events.hp_reached_zero}",  to: dead }
      - { from: evening,            event: "{events.hp_reached_zero}",  to: dead }
      - { from: night,              event: "{events.hp_reached_zero}",  to: dead }
      - { from: morning_subsequent, event: "{events.hp_reached_zero}",  to: dead }
  pyre_assembly:
    initial: not_started
    nodes:
      - { id: not_started }
      - { id: base_laid }
      - { id: middle_built }
      - { id: top_built }
      - { id: capstone_placed }
      - { id: lit, terminal: true }
    transitions:
      - { from: not_started,     event: "{events.pyre_layer_assembled}", to: base_laid }
      - { from: base_laid,       event: "{events.pyre_layer_assembled}", to: middle_built }
      - { from: middle_built,    event: "{events.pyre_layer_assembled}", to: top_built }
      - { from: top_built,       event: "{events.pyre_layer_assembled}", to: capstone_placed }
      - { from: capstone_placed, event: "{events.pyre_lit_at_dawn}",     to: lit }
events:
  day_part_elapsed:
    status: draft
    description: "World time has advanced through the end of a day-part (morning/afternoon/evening); emitted by {rules.advance_world_time} (driven by {clocks.world_time}) when the cumulative in-game minutes cross a day-part boundary."
    implemented_in: ["src/driftwood/mechanics/events/day_part_elapsed.py"]
  dawn_after_sleep:
    status: draft
    description: "The player slept through the night and dawn arrived; emitted by {verbs.sleep_through_night} on successful resolution."
    implemented_in: ["src/driftwood/mechanics/events/dawn_after_sleep.py"]
  pyre_layer_assembled:
    status: draft
    description: "A layer of the signal pyre was successfully placed at the high point; emitted by {verbs.assemble_pyre}."
    implemented_in: ["src/driftwood/mechanics/events/pyre_layer_assembled.py"]
  pyre_lit_at_dawn:
    status: draft
    description: "The pyre was lit at sunset on Day 5 and burned through the night; emitted by {verbs.light_pyre} on resolution at the world_clock's day-5 night transition."
    implemented_in: ["src/driftwood/mechanics/events/pyre_lit_at_dawn.py"]
  day_5_passed:
    status: draft
    description: "World time has reached the end of Day 5's night without the pyre being lit; emitted by {rules.advance_world_time} (driven by {clocks.world_time}) when the cumulative-day counter reaches 5 in the night day-part with pyre.lit == false."
    implemented_in: ["src/driftwood/mechanics/events/day_5_passed.py"]
  hp_reached_zero:
    status: draft
    description: "Player HP has decremented to zero from any cause (hunger/thirst depletion, night exposure without shelter); emitted by {rules.tick_meters}."
    implemented_in: ["src/driftwood/mechanics/events/hp_reached_zero.py"]
rules:
  gather_resolution:
    given:
      verb: "{verbs.gather}"
      state: "{states.world_clock}"
    target_selection: explicit
    do:
      - kind: check_tool_for_node
        actor_inventory: "{actor.inventory}"
        node_kind: "{target.kind}"
        into: tool_present
      - kind: sample
        from: "{distributions.gather_yield_deterministic}"
        into: gathered_qty
      - kind: add_to_inventory
        actor: "{actor.inventory}"
        item: "{target.kind}"
        quantity: gathered_qty
      - kind: decrement_node_remaining_harvests
        node: "{target}"
        by: 1
      - kind: decrement_tool_durability
        tool: "{actor.tool_for_node_kind}"
        by: 1
        if: tool_present
    outputs: [gather_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/gather.py"]
  craft_resolution:
    given:
      verb: "{verbs.craft}"
      state: "{states.world_clock}"
    target_selection: explicit
    do:
      - kind: check_recipe_inputs
        recipe: "{target}"
        actor_inventory: "{actor.inventory}"
      - kind: check_recipe_station
        recipe: "{target}"
        actor_adjacent_to: "{target.station_required}"
      - kind: consume_recipe_inputs
        recipe: "{target}"
        from: "{actor.inventory}"
      - kind: add_to_inventory
        actor: "{actor.inventory}"
        item: "{target.output_item}"
        quantity: "{target.output_quantity}"
    outputs: [craft_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/craft.py"]
  eat_resolution:
    given:
      verb: "{verbs.eat}"
    target_selection: explicit
    do:
      - kind: consume_from_inventory
        actor: "{actor.inventory}"
        item: "{target}"
        quantity: 1
      - kind: increase_resource
        resource: "{resources.hunger}"
        by: "{target.hunger_restore_value}"
        clamp: [0, 12]
    outputs: [eat_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/eat.py"]
  drink_resolution:
    given:
      verb: "{verbs.drink}"
    target_selection: explicit
    do:
      - kind: check_drink_source_kind
        source: "{target}"
        allowed_kinds_csv: spring,still
      - kind: decrement_source_capacity
        source: "{target}"
        by: 1
        if: target_kind_is_still
      - kind: increase_resource
        resource: "{resources.thirst}"
        by: 8
        clamp: [0, 12]
    outputs: [drink_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/drink.py"]
  place_station_resolution:
    given:
      verb: "{verbs.place_station}"
    target_selection: explicit
    do:
      - kind: consume_recipe_inputs
        recipe: "{target.station_recipe}"
        from: "{actor.inventory}"
      - kind: spawn_entity
        kind_name: "{target.kind}"
        position: "{target.coord}"
    outputs: [place_station_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/place_station.py"]
  sleep_resolution:
    given:
      verb: "{verbs.sleep_through_night}"
      state: "{states.world_clock}"
    target_selection: self
    do:
      - kind: check_shelter_present
        actor_position: "{actor.position}"
        into: shelter_present
      - kind: decrement_resource
        resource: "{resources.hp}"
        by: 3
        if_not: shelter_present
        clamp: [0, 12]
      - kind: advance_world_clock_to
        node: morning_subsequent
      - kind: emit_event
        event: "{events.dawn_after_sleep}"
    outputs: [dawn_after_sleep_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/sleep.py"]
  assemble_pyre_resolution:
    given:
      verb: "{verbs.assemble_pyre}"
      state: "{states.pyre_assembly}"
    target_selection: explicit
    do:
      - kind: check_actor_position
        actor_position: "{actor.position}"
        must_equal: high_point
      - kind: check_recipe_inputs
        recipe: current_pyre_layer_recipe
        actor_inventory: "{actor.inventory}"
      - kind: consume_recipe_inputs
        recipe: current_pyre_layer_recipe
        from: "{actor.inventory}"
      - kind: increment_pyre_assembled_layers
        pyre: "{target}"
        by: 1
      - kind: emit_event
        event: "{events.pyre_layer_assembled}"
    outputs: [pyre_layer_assembled_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/assemble_pyre.py"]
  light_pyre_resolution:
    given:
      verb: "{verbs.light_pyre}"
      state: "{states.pyre_assembly}"
    target_selection: explicit
    do:
      - kind: check_pyre_ready
        pyre: "{target}"
        required_layers: 4
        required_day: 5
        required_part: evening
      - kind: consume_from_inventory
        actor: "{actor.inventory}"
        item: flint_shard
        quantity: 1
      - kind: set_pyre_lit
        pyre: "{target}"
        value: true
      - kind: advance_world_clock_to
        node: night
      - kind: emit_event
        event: "{events.pyre_lit_at_dawn}"
    outputs: [pyre_lit_at_dawn_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/light_pyre.py"]
  start_day_resolution:
    given:
      verb: "{verbs.start_day}"
      state: "{states.world_clock}"
    target_selection: none
    do:
      - kind: advance_world_clock_to
        node: morning_subsequent
      - kind: emit_event
        event: "{events.dawn_after_sleep}"
    outputs: [dawn_after_sleep_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/start_day.py"]
  advance_world_time:
    given:
      driver: "{clocks.world_time}"
      state: "{states.world_clock}"
    target_selection: none
    do:
      - kind: increment_world_minutes
        by: "{actor.last_action_time_cost}"
      - kind: check_day_part_boundary
        emit_if_crossed: "{events.day_part_elapsed}"
      - kind: invoke_rule
        rule: "{rules.tick_meters}"
    outputs: [day_part_elapsed_event, hp_reached_zero_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/advance_world_time.py"]
  tick_meters:
    given:
      driver: "{clocks.world_time}"
    target_selection: self
    do:
      - kind: sample
        from: "{distributions.hunger_decay_per_in_game_hour}"
        into: hunger_decay
      - kind: sample
        from: "{distributions.thirst_decay_per_in_game_hour}"
        into: thirst_decay
      - kind: decrement_resource_proportional
        resource: "{resources.hunger}"
        rate: hunger_decay
        per_in_game_minutes: 60
        cost_in_game_minutes: "{actor.last_action_time_cost}"
        clamp: [0, 12]
      - kind: decrement_resource_proportional
        resource: "{resources.thirst}"
        rate: thirst_decay
        per_in_game_minutes: 60
        cost_in_game_minutes: "{actor.last_action_time_cost}"
        clamp: [0, 12]
      - kind: decrement_resource
        resource: "{resources.hp}"
        by: 1
        if_either_zero:
          - "{resources.hunger}"
          - "{resources.thirst}"
        clamp: [0, 12]
      - kind: emit_event_if
        event: "{events.hp_reached_zero}"
        condition_resource_at_zero: "{resources.hp}"
    outputs: [hp_reached_zero_event]
    status: draft
    implemented_in: ["src/driftwood/mechanics/rules/tick_meters.py"]
---

## Tokens

The complete mechanical surface: 5 entities (one of which is the `recipes` content_collection), 11 verbs, 3 resources, 2 state machines, 6 events, 11 rules. Reading order from the spec's universal-surface §4 ordering: entities → verbs → resources → states → events → rules.

## Rationale

### Entities

The five entities partition the world into the things-that-act, the things-that-yield, the things-that-craft, the player's win-condition object, and the data-only recipe collection.

- `player` is the sole actor. Its inventory is a first-class `instance_container` entity (`{entities.player_inventory}`, capacity 12, 8-per-slot stacking via `per_instance_state.quantity`) referenced by the player's `inventory:` property — see the per-instance-state note below.
- `resource_node` is hand-authored per-island; the brief enumerates the kinds (tree, stone outcrop, fiber plant, berry bush, tidepool, spring, flint outcrop). The `yield_per_harvest_with_correct_tool` field encodes the brief's "bare hands gives a small amount, the right tool gives a useful amount."
- `crafting_station` is the built-world-object class. The four kinds enumerated cover everything the brief lists (campfire, sawhorse, shelter, still). The `durability` field is non-zero because the brief implies stations are not infinite (a fire burns out).
- `recipes` is the content collection — see `gdd/content/recipes.md` for the schema and `content/recipes/*.yaml` for the per-recipe data. Twelve recipes total (under the §6 inline-content threshold of 20, but externalized to demonstrate the data-as-content pattern and to make the Easy benchmark task (author a new recipe) genuinely authorable from a schema + one YAML example).
- `pyre` is given its own entity (not just a `crafting_station` kind) because its layered assembly is its own state machine (`{states.pyre_assembly}`) and the win condition turns on its `assembled_layers == 4 AND lit == true`.

### Verbs

The four verbs the brief names — gather / craft / eat-drink-sleep / build-the-pyre — expand here into 10 verbs because eating and drinking decompose differently from each other (different cooldown, different resources), and the pyre's "assemble" and "light" are separate actions on separate days. The auxiliary verb `start_day` is infrastructure (system-actor, system-issued). Per-action world-time advancement is driven by `{clocks.world_time}` (spec §4.7, F-010 v0.3 resolution) — see `gdd/clocks.md`.

**Per-action time-passage is modeled as a first-class clock at v0.3.** Driftwood's in-game clock advances every time the player acts (each player verb declares its `time_cost.in_game_minutes`); the natural model is "world time ticks per action." In the original v0.1 / v0.2.0-alpha authoring this required a synthetic `verbs.advance_world_time` whose sole purpose was to satisfy the spec's verb-triggers-rule pattern; the friction was logged as a v0.3 candidate finding (F-010), and was the same pattern surfaced by Embergrave's `advance_tick` (the convergence across two genres was what motivated the resolution). F-010's resolution at v0.3 adds the first-class `clocks` namespace (spec §4.7), and Driftwood's per-action driver is now `{clocks.world_time}` (per_verb_delta mode, drives `{rules.advance_world_time}` then `{rules.tick_meters}`). See `gdd/clocks.md`.

### Resources

Only three resources: the vital meters `hp`, `hunger`, `thirst`. Inventory contents (how much wood, fiber, stone, flint, plus per-instance items like tools with their own durability) are NOT modeled as `resources` — they live inside `{entities.player_inventory}`, an `instance_container` (spec §4.1, F-008 v0.3 resolution) holding up to 12 instances drawn from `{entities.recipes}` templates, with `per_instance_state` carrying `remaining_durability` and `quantity` per instance. The spec's `resources:` namespace is for scalar vital quantities (HP-like, mana-like, meter-like); inventory is a structured container.

**Per-instance state on owned items is the F-008 v0.3 resolution.** A wooden axe has its own remaining-uses counter (durability); when the player has two wooden axes, each tracks its own. In the original v0.1 / v0.2.0-alpha authoring this required smuggling the state shape into prose because the three-layer entity vocabulary (`actor` + `content_collection` + `resources`) couldn't express "N owned instances each carrying per-instance runtime state." F-008's resolution at v0.3 adds `instance_container` as a peer entity type (spec §4.1) — Driftwood's `player_inventory` declares `capacity: 12`, `holds_template_from: "{entities.recipes}"`, and a `per_instance_state:` sub-schema for `remaining_durability` (countdown from each recipe's `output.starting_durability`) and `quantity` (stack count, 1-8 per slot).

### States

Two state machines:

- `world_clock` carries the day-part progression plus the three terminal nodes (rescued / missed_rescue / dead). The cycle morning → afternoon → evening → night → (sleep) → morning_subsequent → afternoon → ... is the day rhythm; the terminal transitions out are the three end-of-run conditions.
- `pyre_assembly` carries the layered build of the signal pyre — not_started → base_laid → middle_built → top_built → capstone_placed → lit. The transition into `lit` is gated on the world_clock state (Day 5 night), not on `pyre_assembly` state alone.

### Events

Six events, each emitted by exactly one verb or rule (see `description:` per event). The `day_part_elapsed` event fires multiple times per day (one per part boundary crossed); the other five are once-per-run-at-most.

### Rules

Eleven rules cover the ten verbs plus the world-time driver (most rules are 1:1 with verbs; `advance_world_time` and `tick_meters` are both driven by `{clocks.world_time}` rather than directly by a player verb; `start_day_resolution` shares its dawn-emission with `sleep_resolution`).

Every `do:` step is a typed object with a `kind:` field per D-011 (no bare-string steps). Context-local refs `{actor.<field>}` and `{target.<field>}` follow spec §3 — `{actor.inventory}`, `{actor.position}`, `{target.kind}`, `{target.station_required}`, `{target.output_item}`, etc. — resolved at rule-evaluation time against the live world. Internal step-to-step captures use bare variable names (`gathered_qty`, `tool_present`, `shelter_present`, `hunger_decay`, etc.); these are not curly-brace references in the spec's sense and are intentionally local to the rule. Distributions are referenced through `{distributions.<id>}` (deterministic-by-design for Driftwood; see `gdd/systems/distributions.md`).

The `gather_resolution` rule references `{distributions.gather_yield_deterministic}` — a deterministic-by-design distribution that returns the node's declared yield rather than sampling. The brief explicitly forbids RNG on gathering ("gathering yields are deterministic per node"); the spec's requirement that every random outcome resolve through a `distributions.<id>` means the deterministic path is also wrapped in a (constant) distribution.

## Open Questions

- Whether `crafting_station.durability` should be a per-instance integer (which would join the multi-instance-item friction noted above) or a permanent flag. Currently integer; brief implies a campfire burns out (limited duration) but is silent on whether shelters or sawhorses degrade. v0.1 simplification: only `campfire.durability` matters in practice; other stations are permanent until the run ends.
- Whether `verbs.gather` should be one verb with `target_schema` filtering by node kind, or one verb per node kind (`chop_tree`, `mine_stone`, `harvest_fiber`, `pick_berries`, `fish_tidepool`, `draw_spring_water`, `mine_flint`). Currently one verb; argument for: simpler. Argument against: the spec's `feel:` declaration per verb suggests differentiation. v0.1 keeps it one verb; per-kind feel is encoded in `gdd/feel.md`'s `gather` block as conditional prose.
- Whether `verbs.eat` and `verbs.drink` should collapse into one `consume_item` verb. Currently separate; argument for: separate verbs let `eat` and `drink` carry distinct `feel:` blocks (eating fish vs. drinking water are different sensations); argument against: more surface to author. v0.1 keeps them separate.
