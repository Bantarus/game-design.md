---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: ["src/ember_ascent/**/*.py"]
entities:
  player:
    type: actor
    properties:
      hp:        { from: "{resources.health}" }
      energy:    { from: "{resources.energy}" }
      block:     { from: "{resources.block}" }
      hand_size: 5
    status: draft
    implemented_in: ["src/ember_ascent/entities/player.py"]
  cards:
    type: content_collection
    data_source: ../../content/cards
    count_target: 220
    status: draft
  enemies:
    type: content_collection
    data_source: ../../content/enemies
    count_target: 30
    status: draft
verbs:
  draw_cards:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.draw_card}" }
    status: draft
    implemented_in: ["src/ember_ascent/verbs/draw_cards.py"]
  play_card:
    actor: "{entities.player}"
    cost: { resource: "{resources.energy}", amount: varies_by_card }
    target_schema:
      type:   "{entities.cards}"
      filter: in_hand
    effects:
      - { resolve: "{rules.damage_resolution}" }
    feel: "{feel.play_card}"
    status: draft
    implemented_in: ["src/ember_ascent/verbs/play_card.py"]
  end_turn:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.end_of_turn}" }
    status: draft
    implemented_in: ["src/ember_ascent/verbs/end_turn.py"]
  start_combat:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.encounter_setup}" }
    status: draft
    implemented_in: ["src/ember_ascent/verbs/start_combat.py"]
  resolve_encounter:
    actor: system
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.reward_resolution}" }
    status: draft
    implemented_in: ["src/ember_ascent/verbs/resolve_encounter.py"]
  choose_path:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: map_node }
    effects:
      - { kind: navigate_map }
    status: draft
    implemented_in: ["src/ember_ascent/verbs/choose_path.py"]
  claim_reward:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: reward_card }
    effects:
      - { kind: add_card_to_deck }
    status: draft
    implemented_in: ["src/ember_ascent/verbs/claim_reward.py"]
resources:
  energy:
    scope: per_turn
    min: 0
    max: 3
    velocity_target: "{balance_targets.energy_per_turn}"
    visibility: hud
    status: draft
    implemented_in: ["src/ember_ascent/resources/energy.py"]
  health:
    scope: permanent
    min: 0
    max: 80
    visibility: hud
    status: draft
    implemented_in: ["src/ember_ascent/resources/health.py"]
  block:
    scope: per_turn
    min: 0
    max: 999
    visibility: hud
    status: draft
    implemented_in: ["src/ember_ascent/resources/block.py"]
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
      - { from: in_deck,    event: "{events.draw}",                    to: in_hand }
      - { from: in_hand,    event: "{events.play_card}",               to: in_play,   side_effects: ["{resources.energy} -= cost"] }
      - { from: in_play,    event: "{events.resolve}",                 to: in_discard }
      - { from: in_hand,    event: "{events.exhaust}",                 to: exhausted }
      - { from: in_hand,    event: "{events.discard_at_end_of_turn}",  to: in_discard }
      - { from: in_discard, event: "{events.reshuffle}",               to: in_deck }
  enemy_lifecycle:
    initial: alive
    nodes:
      - { id: alive }
      - { id: burning }
      - { id: dead, terminal: true }
    transitions:
      - { from: alive,   event: "{events.catch_fire}",   to: burning, side_effects: ["apply burn stacks"] }
      - { from: burning, event: "{events.burn_expires}", to: alive }
      - { from: alive,   event: "{events.hp_zero}",      to: dead }
      - { from: burning, event: "{events.hp_zero}",      to: dead }
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
    description: "When draw is requested on an empty deck, the discard reshuffles back into in_deck."
  discard_at_end_of_turn:
    status: draft
    description: "Cards remaining in_hand at end of turn move to in_discard; emitted by {rules.end_of_turn}."
  catch_fire:
    status: draft
    description: "An enemy gains the burning state; usually emitted by fire-tagged card effects."
  burn_expires:
    status: draft
    description: "The burning state's duration counter reaches 0; the enemy returns to alive."
  hp_zero:
    status: draft
    description: "An enemy's hp reaches 0 from any damage source; the enemy enters dead."
---

## Tokens

This file owns the four flat namespaces of the moment-to-moment game: `entities`, `verbs`, `resources`, `states`. `rules` live in `gdd/systems/combat.md`; `distributions` live in `gdd/systems/distributions.md`.

## Rationale

**Entities.** Three top-level entities: the player (an `actor`), and two content collections — `cards` (220 designed) and `enemies` (~30 designed). Both collections live in `content/<kind>/*.yaml`; their schemas are in `gdd/content/<kind>.md`. See §6 of `docs/spec.md`.

**Verbs.** Seven verbs: three player turn verbs (`draw_cards`, `play_card`, `end_turn`), two system encounter verbs (`start_combat`, `resolve_encounter`), and two player map verbs (`choose_path`, `claim_reward`). Only `play_card` declares `feel:` — the other six are mechanical glue, not moments the player should "feel."

**Resources.** Three resources, sorted by scope: `energy` (per_turn — the binding constraint on play_card), `block` (per_turn — defensive, wiped on turn end), `health` (permanent — the run-level resource). `energy.velocity_target` ties to `balance_targets.energy_per_turn = 3` (no spend allowance).

**States.** Two named state machines. `card_lifecycle` is the canonical five-node card pipeline with `exhausted` as a terminal sink — needed for one-shot cards that should not return to the deck. `enemy_lifecycle` is a three-node simplification: `alive`, `burning`, `dead`. Burning is modeled as a state node rather than a counter because the *transition* to `alive` (when burn expires) is what `rules.end_of_turn` needs to fire on.

Both machines are total: every non-terminal node has at least one outgoing transition. The `state-machine-coverage` linter rule (§9.1 of the spec) will verify this.

## Open Questions

- Whether `block` should be a `state` rather than a `resource`. Argument for: it's wiped on turn end and is more like a temporary condition. Argument against: it's numeric, additive, and visible on the HUD — *resource* fits the spec definition better. Current call: resource.
- Whether `enemy_lifecycle.burning` should subdivide by burn intensity (1-stack vs 10-stack are different game feel). Currently flat; planned for v0.5.
