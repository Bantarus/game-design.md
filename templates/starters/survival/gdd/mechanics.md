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
      hunger:  { from: "{resources.hunger}" }
      thirst:  { from: "{resources.thirst}" }
      fatigue: { from: "{resources.fatigue}" }
    status: draft
    implemented_in: ["src/entities/player.py"]
  items:
    type: content_collection
    data_source: ../../content/items
    count_target: 20
    status: draft
  recipes:
    type: content_collection
    data_source: ../../content/recipes
    count_target: 15
    status: draft
  inventory:
    type: instance_container
    capacity: 12
    holds_template_from: "{entities.items}"
    per_instance_state:
      durability: { type: integer, minimum: 0 }
      quantity:   { type: integer, minimum: 1, maximum: 8, default: 1 }
      charges:    { type: integer, minimum: 0 }
    status: draft
    implemented_in: ["src/entities/inventory.py"]
verbs:
  gather:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: gatherable }
    effects:
      - { resolve: "{rules.gather_resolution}" }
    time_cost:
      in_game_minutes: 15
    status: draft
    implemented_in: ["src/verbs/gather.py"]
  craft:
    actor: "{entities.player}"
    cost: 0
    target_schema:
      type: "{entities.recipes}"
    effects:
      - { resolve: "{rules.craft_resolution}" }
    time_cost:
      in_game_minutes: 30
    status: draft
    implemented_in: ["src/verbs/craft.py"]
  eat:
    actor: "{entities.player}"
    cost: 0
    target_schema:
      type:   "{entities.inventory}"
      filter: edible
    effects:
      - { resolve: "{rules.eat_resolution}" }
    time_cost:
      in_game_minutes: 5
    status: draft
    implemented_in: ["src/verbs/eat.py"]
  rest:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.rest_resolution}" }
    time_cost:
      in_game_minutes: 240
    status: draft
    implemented_in: ["src/verbs/rest.py"]
resources:
  hunger:
    scope: permanent
    min: 0
    max: 100
    visibility: hud
    status: draft
    implemented_in: ["src/resources/hunger.py"]
  thirst:
    scope: permanent
    min: 0
    max: 100
    visibility: hud
    status: draft
    implemented_in: ["src/resources/thirst.py"]
  fatigue:
    scope: permanent
    min: 0
    max: 100
    visibility: hud
    status: draft
    implemented_in: ["src/resources/fatigue.py"]
rules:
  gather_resolution:
    given:
      verb: "{verbs.gather}"
    do:
      - { kind: sample, from: "{distributions.gather_yield}" }
      - { kind: add_to_inventory, container: "{entities.inventory}" }
    outputs: [item_gathered]
    status: draft
    implemented_in: ["src/rules/gather_resolution.py"]
  craft_resolution:
    given:
      verb: "{verbs.craft}"
    do:
      - { kind: consume_from_inventory, container: "{entities.inventory}" }
      - { kind: add_to_inventory, container: "{entities.inventory}" }
    outputs: [item_crafted]
    status: draft
    implemented_in: ["src/rules/craft_resolution.py"]
  eat_resolution:
    given:
      verb: "{verbs.eat}"
    target_selection: explicit
    do:
      - { kind: consume_from_inventory, container: "{entities.inventory}" }
      - { kind: reduce_resource, resource: "{resources.hunger}", amount: 30 }
    outputs: [food_consumed]
    status: draft
    implemented_in: ["src/rules/eat_resolution.py"]
  rest_resolution:
    given:
      verb: "{verbs.rest}"
    do:
      - { kind: reduce_resource, resource: "{resources.fatigue}", amount: 80 }
    outputs: [player_rested]
    status: draft
    implemented_in: ["src/rules/rest_resolution.py"]
  tick_meters:
    given:
      driver: "{clocks.world_time}"
    do:
      - { kind: increase_resource, resource: "{resources.hunger}",  amount_per_hour: 4 }
      - { kind: increase_resource, resource: "{resources.thirst}",  amount_per_hour: 6 }
      - { kind: increase_resource, resource: "{resources.fatigue}", amount_per_hour: 3 }
    outputs: [meters_ticked]
    status: draft
    implemented_in: ["src/rules/tick_meters.py"]
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `rules`. Each player verb
declares `time_cost.in_game_minutes`; the `world_time` clock reads this and
advances by that delta on each verb firing.

## Rationale

**Per-verb time costs.** Gather 15 min, craft 30 min, eat 5 min, rest 4 hours.
These are the load-bearing numbers — every survival pressure target is
calibrated against the cumulative time-cost of optimal play.

**`tick_meters` is clock-driven.** Hunger/thirst/fatigue tick UP per in-game
hour of world_time advancement. This is the F-010 / D-019 composition: a
clock-driven rule that mutates per-actor state at a rate proportional to
elapsed time.
