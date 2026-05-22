---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/ember_ascent/loops/**/*.py"]
loops:
  combat_turn:
    timescale: moment
    duration: "~45s"
    sequence:
      - draw:     "{verbs.draw_cards}"
      - play:     "{verbs.play_card}"
      - end_turn: "{verbs.end_turn}"
    intended_dynamics:
      - "energy scarcity forces hand-shape decisions"
      - "burn × bellow synergy rewards holding cards across turns"
    intended_aesthetics: [challenge, expression]
    feel_priority: high
    balance_targets:
      - "{balance_targets.energy_per_turn}"
      - "{balance_targets.average_combo_length}"
    status: draft
    implemented_in: ["src/ember_ascent/loops/combat_turn.py"]
  encounter:
    timescale: session
    duration: "~2-4 min"
    sequence:
      - start:   "{verbs.start_combat}"
      - turns:   "{loops.combat_turn}"
      - resolve: "{verbs.resolve_encounter}"
    intended_dynamics:
      - "deck composition decisions outweigh single-turn decisions"
      - "intent telegraphing lets the player plan two turns ahead"
    intended_aesthetics: [challenge]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.median_turns_per_combat}"
    status: draft
    implemented_in: ["src/ember_ascent/loops/encounter.py"]
  run:
    timescale: meta
    duration: "~32 min"
    sequence:
      - choose_path: "{verbs.choose_path}"
      - encounters:  "{loops.encounter}"
      - claim:       "{verbs.claim_reward}"
    intended_dynamics:
      - "path choice matters; the visible map shapes risk appetite"
      - "reward economy creates a meta-decision between card-add and card-removal"
    intended_aesthetics: [challenge, expression, discovery]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.average_run_length}"
      - "{balance_targets.win_rate_ascension_0}"
    status: draft
    implemented_in: ["src/ember_ascent/loops/run.py"]
---

## Tokens

Three loops at three nested timescales. Reading order when reasoning about the game: `combat_turn → encounter → run`.

## Rationale

A turn is the unit of *decision*. An encounter is the unit of *commitment* — once entered the player cannot rewind. A run is the unit of *narrative*: the salamander dies, the cycle resets.

The boss fight is intentionally not a separate loop. Bosses are encounters with different content; treating them as a separate timescale would teach the player that "boss mode" is different, which we don't want. Re-evaluate after balance pass.

## Open Questions

- Whether elite encounters should declare their own intended_dynamics or inherit from `encounter`. Current call: inherit.
- Whether the rare alt-win path (event that stops the collapse) belongs in `loops.run.sequence` or as a `rules.*` branch. Currently in rules.
