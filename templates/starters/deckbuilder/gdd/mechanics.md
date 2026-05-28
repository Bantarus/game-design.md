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
      hp:        { from: "{resources.health}" }
      energy:    { from: "{resources.energy}" }
      block:     { from: "{resources.block}" }
      hand_size: 5
    status: draft
    implemented_in: ["src/entities/player.py"]
  cards:
    type: content_collection
    data_source: ../../content/cards
    count_target: 30
    status: draft
verbs:
  draw_cards:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.card_draw}" }
    status: draft
    implemented_in: ["src/verbs/draw_cards.py"]
  play_card:
    actor: "{entities.player}"
    cost: { resource: "{resources.energy}", amount: "varies_by_card" }
    target_schema:
      type:   "{entities.cards}"
      filter: in_hand
    effects:
      - { resolve: "{rules.card_resolution}" }
    status: draft
    implemented_in: ["src/verbs/play_card.py"]
  end_turn:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.end_of_turn}" }
    status: draft
    implemented_in: ["src/verbs/end_turn.py"]
  start_combat:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.encounter_setup}" }
    status: draft
    implemented_in: ["src/verbs/start_combat.py"]
  resolve_encounter:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.encounter_resolution}" }
    status: draft
    implemented_in: ["src/verbs/resolve_encounter.py"]
resources:
  energy:
    scope: per_turn
    min: 0
    max: 3
    velocity_target: "{balance_targets.energy_per_turn}"
    visibility: hud
    status: draft
    implemented_in: ["src/resources/energy.py"]
  health:
    scope: permanent
    min: 0
    max: 80
    visibility: hud
    status: draft
    implemented_in: ["src/resources/health.py"]
  block:
    scope: per_turn
    min: 0
    max: 999
    visibility: hud
    status: draft
    implemented_in: ["src/resources/block.py"]
states:
  card_lifecycle:
    initial: in_deck
    nodes:
      - { id: in_deck }
      - { id: in_hand }
      - { id: in_play }
      - { id: in_discard }
      - { id: exhausted, terminal: true }
    transitions:
      - { from: in_deck,    event: "{events.draw}",       to: in_hand }
      - { from: in_hand,    event: "{events.play_card}",  to: in_play, side_effects: ["{resources.energy} -= cost"] }
      - { from: in_play,    event: "{events.resolve}",    to: in_discard }
      - { from: in_hand,    event: "{events.exhaust}",    to: exhausted }
      - { from: in_discard, event: "{events.reshuffle}",  to: in_deck }
events:
  draw:
    status: draft
    description: "A card moves from in_deck to in_hand; emitted by {verbs.draw_cards}."
  play_card:
    status: draft
    description: "A card moves from in_hand to in_play; emitted by {verbs.play_card}."
  resolve:
    status: draft
    description: "A card finishes its in_play effects and moves to in_discard."
  exhaust:
    status: draft
    description: "A one-shot card moves from in_hand directly to the exhausted terminal node."
  reshuffle:
    status: draft
    description: "When draw is requested on an empty deck, discard reshuffles back into in_deck."
rules:
  card_draw:
    given:
      verb: "{verbs.draw_cards}"
    do:
      - { kind: sample, from: "{distributions.card_draw}", count: 1 }
      - { kind: transition_state, target: drawn_card, from: in_deck, to: in_hand }
    outputs: [card_drawn_event]
    status: draft
    implemented_in: ["src/rules/card_draw.py"]
  card_resolution:
    given:
      verb: "{verbs.play_card}"
    target_selection: explicit
    do:
      - { kind: apply_card_effects, target: target }
    outputs: [card_resolved_event]
    status: draft
    implemented_in: ["src/rules/card_resolution.py"]
  end_of_turn:
    given:
      verb: "{verbs.end_turn}"
    do:
      - { kind: reset_resource, resource: "{resources.energy}" }
      - { kind: reset_resource, resource: "{resources.block}" }
      - { kind: discard_hand }
    outputs: [turn_ended_event]
    status: draft
    implemented_in: ["src/rules/end_of_turn.py"]
  encounter_setup:
    given:
      verb: "{verbs.start_combat}"
    do:
      - { kind: spawn_enemies }
      - { kind: shuffle_deck }
    outputs: [encounter_started_event]
    status: draft
    implemented_in: ["src/rules/encounter_setup.py"]
  encounter_resolution:
    given:
      verb: "{verbs.resolve_encounter}"
    do:
      - { kind: award_rewards }
    outputs: [encounter_resolved_event]
    status: draft
    implemented_in: ["src/rules/encounter_resolution.py"]
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `states`, `events`, `rules`.
Distributions live in `gdd/systems/distributions.md`.

## Rationale

**Entities.** Three top-level: `player` (actor), `cards` (content_collection),
`enemies` (content_collection). The content collections externalize per spec §6
when `count_target >= 20`; tune `count_target` to your designed scope.

**Verbs.** Five: three player turn verbs + two system encounter verbs. Add
`feel:` references when you author `gdd/feel.md`.

**Resources.** The classic deckbuilder triad — `energy` (per_turn binding
constraint), `block` (per_turn defensive, wiped on turn end), `health`
(permanent run-level). Adjust scope and bounds to fit your design.

**States.** The `card_lifecycle` state machine is the canonical five-node
deckbuilder pipeline with `exhausted` as a terminal sink for one-shot cards.

**Rules.** Stubs only — the `kind:` values are illustrative; replace with the
actual operations your engine performs. Each rule's `do[]` step is currently
a structured object (per D-011), which is what the determinism gate expects
on rules reachable from a moment-timescale loop.
