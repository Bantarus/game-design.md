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
      life:      { from: "{resources.life}" }
      mana:      { from: "{resources.mana}" }
      hand_size: { from: "{resources.hand_size}" }
    status: draft
    implemented_in: []
  cards:
    type: content_collection
    data_source: ../../content/cards
    count_target: 220
    status: draft
verbs:
  play_card:
    actor: "{entities.player}"
    cost: { resource: "{resources.mana}", amount: varies_by_card }
    target_schema:
      type:   "{entities.cards}"
      filter: in_hand
    effects:
      - { resolve: "{rules.card_play_resolution}" }
    status: draft
    implemented_in: []
  attack:
    actor: "{entities.player}"
    cost: 0
    target_schema:
      type: "{entities.player}"
      filter: opponent
    effects:
      - { resolve: "{rules.attack_resolution}" }
    status: draft
    implemented_in: []
  end_turn:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { kind: pass_priority }
    status: draft
    implemented_in: []
  mulligan:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { kind: reshuffle_and_redraw, draw_count: "previous - 1" }
    status: draft
    implemented_in: []
  draw_card:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.draw_step}" }
    status: draft
    implemented_in: []
  start_game:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { sample: "{distributions.first_player}" }
      - { kind: deal_opening_hands, count: 7 }
    status: draft
    implemented_in: []
resources:
  life:
    scope: per_run
    min: 0
    max: 30
    visibility: hud
    status: draft
    implemented_in: []
  mana:
    scope: per_turn
    min: 0
    max: 10
    velocity_target: "{balance_targets.mana_per_turn}"
    visibility: hud
    status: draft
    implemented_in: []
  hand_size:
    scope: per_turn
    min: 0
    max: 7
    visibility: hud
    status: draft
    implemented_in: []
states:
  card_state:
    initial: in_deck
    nodes:
      - { id: in_deck }
      - { id: in_hand }
      - { id: on_board }
      - { id: graveyard }
      - { id: exiled, terminal: true }
    transitions:
      - { from: in_deck,    event: draw,        to: in_hand }
      - { from: in_hand,    event: cast,        to: on_board }
      - { from: on_board,   event: destroyed,   to: graveyard }
      - { from: graveyard,  event: reanimate,   to: on_board }
      - { from: in_hand,    event: discard,     to: graveyard }
      - { from: graveyard,  event: exile,       to: exiled }
      - { from: on_board,   event: exile_direct, to: exiled }
  phase_state:
    initial: untap
    nodes:
      - { id: untap }
      - { id: upkeep }
      - { id: main }
      - { id: combat }
      - { id: endphase }
    transitions:
      - { from: untap,    event: proceed, to: upkeep }
      - { from: upkeep,   event: proceed, to: main }
      - { from: main,     event: proceed, to: combat }
      - { from: combat,   event: proceed, to: endphase }
      - { from: endphase, event: pass,    to: untap }
rules:
  card_play_resolution:
    given:
      verb: "{verbs.play_card}"
    do:
      - pay_mana_cost
      - apply_card_effects
    outputs: [card_played_event]
    status: draft
    implemented_in: []
  attack_resolution:
    given:
      verb: "{verbs.attack}"
    do:
      - deal_damage_to_opponent: integer_only
    outputs: [attack_resolved_event, life_changed_event]
    status: draft
    implemented_in: []
  draw_step:
    given:
      verb: "{verbs.draw_card}"
    do:
      - sample: "{distributions.card_draw}"
        count: 1
        transition: "in_deck -> in_hand"
    outputs: [card_drawn_event]
    status: draft
    implemented_in: []
---

## Tokens

Owns entities, verbs, resources, states, and rules for Lattice. The `phase_state` machine is **cyclic** — no terminal node — which is fine: spec §4.4 only requires non-terminal nodes to have outgoing transitions, which they all do.

## Rationale

**Two state machines, two shapes.** `{states.card_state}` is the deckbuilder-style lifecycle with `exiled` as a terminal sink. `{states.phase_state}` is a *cyclic* machine — each turn goes `untap → upkeep → main → combat → endphase → untap (opponent)`. Cyclic machines satisfy `state-machine-coverage` as long as every node has at least one outgoing transition.

**Six verbs.** Four player-issued (`play_card`, `attack`, `end_turn`, `mulligan`), two system-issued (`draw_card`, `start_game`). The system verbs handle the game's invariants (initial draw, first-player coin flip, turn-start draw).

**Three resources, three scopes.** `life` is `per_run` (per game; reset between games), `mana` is `per_turn` (resets every turn), `hand_size` is `per_turn` (a soft cap — drawing past 7 forces a discard).
