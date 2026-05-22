---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/ember_ascent/rules/**/*.py"]
rules:
  draw_card:
    given:
      verb: "{verbs.draw_cards}"
    do:
      - sample: "{distributions.card_draw}"
        count: 1
        transition: "in_deck -> in_hand"
      - if_pile_empty: reshuffle_discard_into_deck
    outputs: [card_drawn_event]
    status: draft
    implemented_in: ["src/ember_ascent/rules/draw_card.py"]
  damage_resolution:
    given:
      verb: "{verbs.play_card}"
    do:
      - sample: "{distributions.damage_roll}"
        round: half_to_even
      - sample: "{distributions.critical_hit}"
        on_hit_multiply_by: 2
      - apply_damage_to_target: integer_only
    outputs: [damage_event, hp_changed_event]
    status: draft
    implemented_in: ["src/ember_ascent/rules/damage_resolution.py"]
  end_of_turn:
    given:
      verb: "{verbs.end_turn}"
    do:
      - tick_burning_on_each_enemy
      - discard_remaining_hand
      - reset_resource: "{resources.energy}"
      - reset_resource: "{resources.block}"
      - resolve: "{rules.draw_card}"
        count: 5
    outputs: [turn_ended_event]
    status: draft
    implemented_in: ["src/ember_ascent/rules/end_of_turn.py"]
  encounter_setup:
    given:
      verb: "{verbs.start_combat}"
    do:
      - sample: "{distributions.enemy_pack_size}"
      - spawn_enemies_from_pack
      - reveal_intent
    outputs: [encounter_started_event]
    status: draft
    implemented_in: ["src/ember_ascent/rules/encounter_setup.py"]
  reward_resolution:
    given:
      verb: "{verbs.resolve_encounter}"
    do:
      - sample: "{distributions.reward_choice}"
        count: 3
      - present_reward_choices
    outputs: [rewards_offered_event]
    status: draft
    implemented_in: ["src/ember_ascent/rules/reward_resolution.py"]
---

## Tokens

Five rules. Each is keyed by the verb it resolves and lists its `do:` steps in execution order.

## Rationale

The rules are deliberately thin. Heavy logic — e.g. *how* damage scales with burn stacks — lives in card-effect handlers (`content/cards/*.yaml`), not here. This subfile is the *control flow*; the cards are the *data*.

Three of the five rules sample distributions; the other two (`end_of_turn`, `encounter_setup` step 2/3) do not. Note that `encounter_setup` is the only rule that produces stochasticity *outside* the player's verb — pack size is rolled at combat start, not at play_card time.

`reward_resolution.do.sample` has `count: 3` because the player is always offered three reward choices (with one removable to redraw, in v0.5). This is a deliberate design constant tied to `{loops.run.intended_dynamics}`.

## Open Questions

- Whether `damage_resolution` should `sample {distributions.critical_hit}` *before* or *after* applying burn multipliers. Order matters for high-roll variance. Current call: crit first, burn second.
- Whether `end_of_turn.tick_burning_on_each_enemy` should itself reference a distribution (variable burn damage). Currently deterministic at burn-stack × 1.
