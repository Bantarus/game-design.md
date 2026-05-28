---
spec: game-design.md
spec_version: 0.2.0-alpha
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
  battlefield:
    type: instance_container
    capacity: 200
    holds_template_from: "{entities.cards}"
    per_instance_state:
      controller:         { enum: [local, opponent] }
      tapped:             { type: boolean, default: false }
      summoning_sickness: { type: boolean, default: true }
      counters_plus_one:  { type: integer, minimum: 0, default: 0 }
      counters_minus_one: { type: integer, minimum: 0, default: 0 }
      damage_taken:       { type: integer, minimum: 0, default: 0 }
    status: draft
    implemented_in: []
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
      - { from: in_deck,    event: "{events.draw}",         to: in_hand }
      - { from: in_hand,    event: "{events.cast}",         to: on_board }
      - { from: on_board,   event: "{events.destroyed}",    to: graveyard }
      - { from: graveyard,  event: "{events.reanimate}",    to: on_board }
      - { from: in_hand,    event: "{events.discard}",      to: graveyard }
      - { from: graveyard,  event: "{events.exile}",        to: exiled }
      - { from: on_board,   event: "{events.exile_direct}", to: exiled }
  phase_state:
    initial: untap
    nodes:
      - { id: untap }
      - { id: upkeep }
      - { id: main }
      - { id: combat }
      - { id: endphase }
    transitions:
      - { from: untap,    event: "{events.proceed}", to: upkeep }
      - { from: upkeep,   event: "{events.proceed}", to: main }
      - { from: main,     event: "{events.proceed}", to: combat }
      - { from: combat,   event: "{events.proceed}", to: endphase }
      - { from: endphase, event: "{events.pass_turn}", to: untap }
events:
  draw:
    status: draft
    description: "A card moves from in_deck to in_hand; usually emitted in {states.phase_state.untap}."
  cast:
    status: draft
    description: "A card moves from in_hand to on_board; emitted by {verbs.play_card} after mana is paid."
  destroyed:
    status: draft
    description: "An on_board card is destroyed and moves to graveyard."
  reanimate:
    status: draft
    description: "A graveyard card returns to on_board via a reanimation effect."
  discard:
    status: draft
    description: "An in_hand card moves directly to graveyard (forced or voluntary discard)."
  exile:
    status: draft
    description: "A graveyard card moves to the exiled terminal node."
  exile_direct:
    status: draft
    description: "An on_board card moves straight to exiled, bypassing graveyard."
  proceed:
    status: draft
    description: "Phase advances within a turn (untap → upkeep → main → combat → endphase)."
  pass_turn:
    status: draft
    description: "End of one player's turn; phase_state returns to untap for the next player."

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

**Cards on the battlefield carry per-instance state via `instance_container`.** `{entities.battlefield}` (spec §4.1, F-008 v0.3 resolution) holds up to 200 instances drawn from `{entities.cards}` templates, with `per_instance_state` carrying `controller` (which player owns the instance), `tapped` (tap state), `summoning_sickness` (the turn-of-arrival lock), `counters_plus_one` / `counters_minus_one` (stat modifiers), and `damage_taken` (cumulative damage on creatures). Before F-008's v0.3 resolution, this state was invisible to the token surface — the `card_state` machine tracked zone but couldn't express per-instance runtime data. Cards in `in_deck`, `in_hand`, `graveyard`, or `exiled` are addressed by template id alone (no per-instance state matters in those zones); on-board cards live in this container.

**Six verbs.** Four player-issued (`play_card`, `attack`, `end_turn`, `mulligan`), two system-issued (`draw_card`, `start_game`). The system verbs handle the game's invariants (initial draw, first-player coin flip, turn-start draw).

**Three resources, three scopes.** `life` is `per_run` (per game; reset between games), `mana` is `per_turn` (resets every turn), `hand_size` is `per_turn` (a soft cap — drawing past 7 forces a discard).
