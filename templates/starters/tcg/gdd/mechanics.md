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
      life:        { from: "{resources.life}" }
      mana:        { from: "{resources.mana}" }
      hand_size:   { from: "{resources.hand_size}" }
    status: draft
    implemented_in: ["src/entities/player.py"]
  cards:
    type: content_collection
    data_source: ../../content/cards
    count_target: 50
    status: draft
  battlefield:
    type: instance_container
    capacity: 14
    holds_template_from: "{entities.cards}"
    per_instance_state:
      tapped:             { type: boolean, default: false }
      plus_one_counters:  { type: integer, minimum: 0, default: 0 }
      minus_one_counters: { type: integer, minimum: 0, default: 0 }
      attached_items:     { type: array, default: [] }
    status: draft
    implemented_in: ["src/entities/battlefield.py"]
verbs:
  draw_card:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.card_draw}" }
    status: draft
    implemented_in: ["src/verbs/draw_card.py"]
  play_card:
    actor: "{entities.player}"
    cost: { resource: "{resources.mana}", amount: "varies_by_card" }
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
  start_match:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.match_setup}" }
    status: draft
    implemented_in: ["src/verbs/start_match.py"]
  resolve_match:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.match_resolution}" }
    status: draft
    implemented_in: ["src/verbs/resolve_match.py"]
resources:
  life:
    scope: permanent
    min: 0
    max: 30
    visibility: hud
    status: draft
    implemented_in: ["src/resources/life.py"]
  mana:
    scope: per_turn
    min: 0
    max: 10
    visibility: hud
    status: draft
    implemented_in: ["src/resources/mana.py"]
  hand_size:
    scope: permanent
    min: 0
    max: 7
    visibility: hud
    status: draft
    implemented_in: ["src/resources/hand_size.py"]
states:
  card_zone:
    initial: in_deck
    nodes:
      - { id: in_deck }
      - { id: in_hand }
      - { id: on_battlefield }
      - { id: in_graveyard }
      - { id: exiled, terminal: true }
    transitions:
      - { from: in_deck,        event: "{events.drawn}",     to: in_hand }
      - { from: in_hand,        event: "{events.cast}",      to: on_battlefield }
      - { from: on_battlefield, event: "{events.destroyed}", to: in_graveyard }
      - { from: on_battlefield, event: "{events.exiled}",    to: exiled }
      - { from: in_graveyard,   event: "{events.exiled}",    to: exiled }
events:
  drawn:
    status: draft
    description: "A card moves from in_deck to in_hand."
  cast:
    status: draft
    description: "A card moves from in_hand to on_battlefield (resolved)."
  destroyed:
    status: draft
    description: "A card on the battlefield moves to in_graveyard."
  exiled:
    status: draft
    description: "A card moves to exile (the terminal sink)."
rules:
  card_draw:
    given:
      verb: "{verbs.draw_card}"
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
      - { kind: transition_state, target: target, from: in_hand, to: on_battlefield }
    outputs: [card_resolved_event]
    status: draft
    implemented_in: ["src/rules/card_resolution.py"]
  end_of_turn:
    given:
      verb: "{verbs.end_turn}"
    do:
      - { kind: untap_all }
      - { kind: reset_resource, resource: "{resources.mana}" }
    outputs: [turn_ended_event]
    status: draft
    implemented_in: ["src/rules/end_of_turn.py"]
  match_setup:
    given:
      verb: "{verbs.start_match}"
    do:
      - { kind: shuffle_decks }
      - { kind: deal_opening_hands, distribution: "{distributions.opening_hand}" }
    outputs: [match_started_event]
    status: draft
    implemented_in: ["src/rules/match_setup.py"]
  match_resolution:
    given:
      verb: "{verbs.resolve_match}"
    do:
      - { kind: declare_winner }
    outputs: [match_resolved_event]
    status: draft
    implemented_in: ["src/rules/match_resolution.py"]
---

## Tokens

This file owns `entities`, `verbs`, `resources`, `states`, `events`, `rules`.
The `battlefield` is an instance_container (F-008 v0.3) — each card on the
board is a runtime instance carrying tap state + counters + attachments
that's distinct from the immutable card TEMPLATE.

## Rationale

**`battlefield` as instance_container.** A given card TEMPLATE (say
"Lightning Bolt") may appear on the battlefield as multiple distinct
INSTANCES, each with its own tap state, its own +1/+1 counters, and its own
attached items. F-008 v0.3's `instance_container` is the vocabulary that
expresses this naturally — `holds_template_from: "{entities.cards}"` ties
each instance to its template; `per_instance_state` declares the runtime-
mutable fields.

**`card_zone` state machine.** The five-node card-zone pipeline (deck → hand
→ battlefield → graveyard → exile) is the canonical TCG card lifecycle.
