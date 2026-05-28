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
      party_size: 4
    status: draft
    implemented_in: ["src/entities/player.py"]
  heroes:
    type: content_collection
    data_source: ../../content/heroes
    count_target: 8
    status: draft
  items:
    type: content_collection
    data_source: ../../content/items
    count_target: 30
    status: draft
  party_members:
    type: instance_container
    capacity: 4
    holds_template_from: "{entities.heroes}"
    per_instance_state:
      hp:               { type: integer, minimum: 0 }
      mp:               { type: integer, minimum: 0 }
      equipped_item_id: { type: string }
      status_effects:   { type: array }
    status: draft
    implemented_in: ["src/entities/party_members.py"]
verbs:
  take_hero_action:
    actor: "{entities.player}"
    cost: 0
    target_schema:
      type:   "{entities.party_members}"
      filter: alive_this_round
    effects:
      - { resolve: "{rules.hero_action_resolution}" }
    status: draft
    implemented_in: ["src/verbs/take_hero_action.py"]
  resolve_enemy_actions:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.enemy_action_resolution}" }
    status: draft
    implemented_in: ["src/verbs/resolve_enemy_actions.py"]
  end_round:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.end_round_resolution}" }
    status: draft
    implemented_in: ["src/verbs/end_round.py"]
  start_encounter:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.encounter_setup}" }
    status: draft
    implemented_in: ["src/verbs/start_encounter.py"]
  resolve_encounter:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.encounter_resolution}" }
    status: draft
    implemented_in: ["src/verbs/resolve_encounter.py"]
states:
  hero_lifecycle:
    initial: alive
    nodes:
      - { id: alive }
      - { id: stunned }
      - { id: ko, terminal: true }
    transitions:
      - { from: alive,   event: "{events.stun_applied}", to: stunned }
      - { from: stunned, event: "{events.stun_expires}", to: alive }
      - { from: alive,   event: "{events.hp_zero}",      to: ko }
      - { from: stunned, event: "{events.hp_zero}",      to: ko }
events:
  stun_applied:
    status: draft
    description: "A hero gains the stunned state."
  stun_expires:
    status: draft
    description: "A hero's stunned counter reaches 0 and they return to alive."
  hp_zero:
    status: draft
    description: "A hero's hp reaches 0 from any damage source; they enter ko."
rules:
  hero_action_resolution:
    given:
      verb: "{verbs.take_hero_action}"
    target_selection: explicit
    do:
      - { kind: sample, from: "{distributions.damage_roll}", into: damage_value }
      - { kind: apply_hero_action, target: target }
    outputs: [hero_action_resolved_event]
    status: draft
    implemented_in: ["src/rules/hero_action_resolution.py"]
  enemy_action_resolution:
    given:
      verb: "{verbs.resolve_enemy_actions}"
    do:
      - { kind: sample, from: "{distributions.enemy_action_choice}" }
      - { kind: apply_enemy_action }
    outputs: [enemy_action_resolved_event]
    status: draft
    implemented_in: ["src/rules/enemy_action_resolution.py"]
  end_round_resolution:
    given:
      verb: "{verbs.end_round}"
    do:
      - { kind: tick_status_effects }
    outputs: [round_ended_event]
    status: draft
    implemented_in: ["src/rules/end_round_resolution.py"]
  encounter_setup:
    given:
      verb: "{verbs.start_encounter}"
    do:
      - { kind: spawn_enemies }
      - { kind: roll_initiative, distribution: "{distributions.initiative_roll}" }
    outputs: [encounter_started_event]
    status: draft
    implemented_in: ["src/rules/encounter_setup.py"]
  encounter_resolution:
    given:
      verb: "{verbs.resolve_encounter}"
    do:
      - { kind: award_xp_and_loot }
    outputs: [encounter_resolved_event]
    status: draft
    implemented_in: ["src/rules/encounter_resolution.py"]
---

## Tokens

This file owns `entities`, `verbs`, `states`, `events`, `rules`. The party
itself is modeled as an `instance_container` (F-008 v0.3) — each party slot is
an owned hero instance with per-instance hp / mp / equipped_item.

## Rationale

**`party_members` as instance_container.** This is the canonical F-008 v0.3
case: N owned hero instances each carrying runtime state (hp / mp /
status_effects) that's distinct from the immutable hero TEMPLATE. The template
data (max_hp, attack, etc.) lives in `content/heroes/<id>.yaml`; the per-
instance runtime data lives in `per_instance_state`.

Reads via `{target.hp}` resolve through the binding order in spec §3:
per_instance_state → template → container. Writes to `hp` are legal because
`hp` is declared in per_instance_state; writes to `max_hp` would be lint-
errored (`write-to-template-field`) because templates are immutable.

**Rules.** Five stubs cover the round loop. Replace the `kind:` values with
your engine's actual operations.
