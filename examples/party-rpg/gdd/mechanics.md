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
      hp:    { from: "{resources.hp}" }
      mp:    { from: "{resources.mp}" }
      gold:  { from: "{resources.gold}" }
      party_size: 4
    status: draft
    implemented_in: []
  items:
    type: content_collection
    data_source: ../../content/items
    count_target: 50
    status: draft
verbs:
  act:
    actor: "{entities.player}"
    cost: { resource: "{resources.mp}", amount: varies_by_action }
    target_schema:
      type: action_choice
      filter: "attack | cast_spell | use_item"
    effects:
      - { resolve: "{rules.action_resolution}" }
    status: draft
    implemented_in: []
  end_turn:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.end_of_turn}" }
    status: draft
    implemented_in: []
  start_battle:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { kind: spawn_encounter }
    status: draft
    implemented_in: []
  claim_loot:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: "{entities.items}" }
    effects:
      - { resolve: "{rules.loot_resolution}" }
    status: draft
    implemented_in: []
resources:
  hp:
    scope: permanent
    min: 0
    max: 100
    visibility: hud
    status: draft
    implemented_in: []
  mp:
    scope: permanent
    min: 0
    max: 40
    visibility: hud
    status: draft
    implemented_in: []
  gold:
    scope: permanent
    min: 0
    max: 99999
    velocity_target: "{balance_targets.gold_per_quest}"
    visibility: hud
    status: draft
    implemented_in: []
states:
  character_lifecycle:
    initial: alive
    nodes:
      - { id: alive }
      - { id: wounded }
      - { id: unconscious }
      - { id: dead, terminal: true }
    transitions:
      - { from: alive,       event: hp_below_half, to: wounded }
      - { from: wounded,     event: hp_zero,       to: unconscious }
      - { from: unconscious, event: revive,        to: alive,       side_effects: ["restore hp to 1"] }
      - { from: unconscious, event: counted_out,   to: dead }
      - { from: alive,       event: instant_kill,  to: dead }
      - { from: wounded,     event: heal_above_half, to: alive }
rules:
  action_resolution:
    given:
      verb: "{verbs.act}"
    do:
      - sample: "{distributions.damage_roll}"
        round: half_to_even
      - sample: "{distributions.critical_hit}"
        on_hit_multiply_by: 2
      - apply_damage_to_target: integer_only
    outputs: [action_resolved_event, damage_event]
    status: draft
    implemented_in: []
  end_of_turn:
    given:
      verb: "{verbs.end_turn}"
    do:
      - tick_status_effects
      - regenerate_mp
    outputs: [turn_ended_event]
    status: draft
    implemented_in: []
  loot_resolution:
    given:
      verb: "{verbs.claim_loot}"
    do:
      - sample: "{distributions.loot_rarity}"
      - present_loot_choice
    outputs: [loot_offered_event]
    status: draft
    implemented_in: []
---

## Tokens

Owns entities, verbs, resources, states, and rules for Hollow Hold. Distributions, balance targets, and invariants live in their own subfiles.

## Rationale

**Four verbs.** `{verbs.act}` (one player verb that resolves into attack/spell/item internally), `{verbs.end_turn}` (system, after 4 acts), `{verbs.start_battle}` (system), `{verbs.claim_loot}` (player). Keeping the verb count low keeps the doc legible; the *types* of action live inside `target_schema.filter`.

**The character lifecycle has revival.** `{states.character_lifecycle.unconscious}` can transition back to `alive` via the `revive` event (a held item, a healer spell, or the post-battle medic mechanic). Only `dead` is terminal. This makes Hollow Hold less punishing than a roguelike — encounters that wipe one character don't end the quest if the remaining party can clutch a revive.

**Three resources, shared across the party.** `hp` and `mp` are tracked per-character at runtime, but for the design doc they're the *shape* of every character's pool (max 100 hp, max 40 mp). `gold` is the party's shared currency.
