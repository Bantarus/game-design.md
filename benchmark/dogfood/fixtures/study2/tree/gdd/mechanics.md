---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-04-18"
implemented_in: ["impl/lanternfall/core/**/*.py"]
entities:
  lamplighter:
    type: actor
    properties:
      vigor: { from: "{resources.vigor}" }
      ward_focus: { from: "{resources.ward_focus}" }
      lantern_oil: { from: "{resources.lantern_oil}" }
      grave_coin: { from: "{resources.grave_coin}" }
      load: { from: "{resources.satchel_load}" }
      satchel: { from: "{entities.satchel}" }
      might: 3
    status: draft
    implemented_in: ["impl/lanternfall/core/lamplighter.py"]
  items:
    type: content_collection
    data_source: ../../content/items
    count_target: 140
    status: draft
  skills:
    type: content_collection
    data_source: ../../content/skills
    count_target: 90
    status: draft
  monsters:
    type: content_collection
    data_source: ../../content/monsters
    count_target: 60
    status: draft
  encounters:
    type: content_collection
    data_source: ../../content/encounters
    count_target: 30
    status: draft
  satchel:
    type: instance_container
    capacity: 16
    holds_template_from: "{entities.items}"
    per_instance_state:
      charges: { type: integer, minimum: 0 }
      wear: { type: integer, minimum: 0, maximum: 5 }
      quantity: { type: integer, minimum: 1, default: 1 }
    status: draft
    implemented_in: ["impl/lanternfall/core/satchel.py"]
verbs:
  descend_stair:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: "{entities.encounters}", filter: unexplored_stair }
    effects:
      - { resolve: "{rules.spawn_encounter}" }
    feel: "{feel.descend_stair}"
    oil_cost: 4
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/descend_stair.py"]
  strike_foe:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: "{entities.monsters}", filter: adjacent_and_revealed }
    effects:
      - { resolve: "{rules.resolve_strike}" }
    feel: "{feel.strike_foe}"
    oil_cost: 1
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/strike_foe.py"]
  invoke_skill:
    actor: "{entities.lamplighter}"
    cost: { resource: "{resources.ward_focus}", amount: varies_by_skill }
    target_schema: { type: "{entities.skills}", filter: known_and_affordable }
    effects:
      - { resolve: "{rules.resolve_skill}" }
    oil_cost: 1
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/invoke_skill.py"]
  use_relic:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: "{entities.satchel}", filter: has_charges }
    effects:
      - { resolve: "{rules.apply_relic}" }
    oil_cost: 1
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/use_relic.py"]
  loot_remains:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: "{entities.monsters}", filter: defeated_this_floor }
    effects:
      - { resolve: "{rules.roll_drops}" }
    oil_cost: 2
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/loot_remains.py"]
  salvage_gear:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: "{entities.satchel}", filter: worn_quality }
    effects:
      - { resolve: "{rules.resolve_salvage}" }
    oil_cost: 2
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/salvage_gear.py"]
  trim_wick:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.refill_lantern}" }
    oil_cost: 0
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/trim_wick.py"]
  ring_the_knell:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: "{entities.monsters.knell_mother}", filter: at_the_bell }
    effects:
      - { resolve: "{rules.boss_awakening}" }
    feel: "{feel.ring_the_knell}"
    oil_cost: 3
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/ring_the_knell.py"]
  breach_sanctum:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: "{entities.encounters.soot_sanctum}", filter: all_knells_rung }
    effects:
      - { resolve: "{rules.sanctum_trial}" }
    oil_cost: 6
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/breach_sanctum.py"]
  flee_upward:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.resolve_flight}" }
    oil_cost: 8
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/flee_upward.py"]
  make_camp:
    actor: "{entities.lamplighter}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { kind: restore, resource: "{resources.vigor}" }
    oil_cost: 0
    status: draft
    implemented_in: ["impl/lanternfall/core/verbs/make_camp.py"]
resources:
  lantern_oil:
    scope: per_run
    min: 0
    max: 120
    velocity_target: "{balance_targets.oil_per_floor}"
    visibility: hud
    status: draft
    implemented_in: ["impl/lanternfall/core/lantern_oil.py"]
  vigor:
    scope: per_run
    min: 0
    max: 40
    visibility: hud
    status: draft
    implemented_in: ["impl/lanternfall/core/vigor.py"]
  ward_focus:
    scope: per_turn
    min: 0
    max: 12
    visibility: hud
    status: draft
    implemented_in: ["impl/lanternfall/core/ward_focus.py"]
  grave_coin:
    scope: permanent
    min: 0
    max: 9999
    velocity_target: "{balance_targets.coin_per_expedition}"
    visibility: hud
    status: draft
    implemented_in: ["impl/lanternfall/core/grave_coin.py"]
  satchel_load:
    scope: per_run
    min: 0
    max: 30
    visibility: inferred
    status: draft
    implemented_in: ["impl/lanternfall/core/satchel_load.py"]
states:
  affliction:
    initial: clear
    nodes:
      - { id: clear }
      - { id: chilled }
      - { id: hexed }
      - { id: bleeding }
      - { id: dazed }
    transitions:
      - { from: clear, event: "{events.chill_applied}", to: chilled }
      - { from: clear, event: "{events.hex_applied}", to: hexed }
      - { from: clear, event: "{events.wound_opened}", to: bleeding }
      - { from: clear, event: "{events.daze_applied}", to: dazed }
      - { from: chilled, event: "{events.affliction_faded}", to: clear }
      - { from: hexed, event: "{events.affliction_faded}", to: clear }
      - { from: bleeding, event: "{events.affliction_faded}", to: clear }
      - { from: dazed, event: "{events.affliction_faded}", to: clear }
  lantern_state:
    initial: lit
    nodes:
      - { id: lit }
      - { id: dim }
      - { id: guttered, terminal: true }
    transitions:
      - { from: lit, event: "{events.oil_low}", to: dim }
      - { from: dim, event: "{events.oil_refilled}", to: lit }
      - { from: dim, event: "{events.flame_out}", to: guttered }
events:
  chill_applied:
    status: draft
    description: The lamplighter or a monster becomes chilled.
  hex_applied:
    status: draft
    description: A hex takes hold.
  wound_opened:
    status: draft
    description: A wound opens and starts to bleed.
  daze_applied:
    status: draft
    description: A blow or a knell leaves its target dazed.
  affliction_faded:
    status: draft
    description: Any affliction wears off at the end of its span.
  oil_low:
    status: draft
    description: Lantern oil falls below the dim threshold.
  oil_refilled:
    status: draft
    description: The wick is trimmed and the lantern refilled.
  flame_out:
    status: draft
    description: The lantern runs dry and gutters out.
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `states` and `events`. Rules live in `gdd/systems/*.md`, distributions in `gdd/systems/distributions.md`. The four content collections keep their entries in `content/<kind>/*.yaml`; their schemas are in `gdd/content/<kind>.md`.

## Rationale

**One actor.** The lamplighter is the only actor; monsters are content, instantiated per encounter. The satchel is an `instance_container`: relics carry charges and wear per copy, while the item template stays immutable.

**Verbs burn oil.** Every verb declares `oil_cost:`, which the lantern clock reads after the verb fires. Most verbs cost nothing else; only skills spend ward focus. Descending is the expensive choice by design.

**Two state machines.** `affliction` is the status a skill can inflict, and every affliction fades back to `clear`. `lantern_state` is the lantern itself: `guttered` is terminal for the expedition.

## Open Questions

- Whether satchel wear should be a resource rather than per-instance state. Current call: per-instance, because two copies of the same relic wear independently.
