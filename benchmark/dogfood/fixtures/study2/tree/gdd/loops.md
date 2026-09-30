---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-04-18"
implemented_in: ["impl/lanternfall/core/loops/**/*.py"]
loops:
  delve_turn:
    timescale: moment
    duration: "~20s"
    sequence:
      - { strike: "{verbs.strike_foe}" }
      - { skill: "{verbs.invoke_skill}" }
      - { relic: "{verbs.use_relic}" }
    clock: "{clocks.lantern_burn}"
    intended_dynamics:
      - every action is weighed against the oil it burns
      - afflictions reward finishing fights quickly
    intended_aesthetics: [challenge]
    feel_priority: high
    balance_targets:
      - "{balance_targets.turns_per_fight}"
    status: draft
    implemented_in: ["impl/lanternfall/core/loops/delve_turn.py"]
  floor_sweep:
    timescale: session
    duration: "~4 min"
    sequence:
      - { descend: "{verbs.descend_stair}" }
      - { fight: "{loops.delve_turn}" }
      - { loot: "{verbs.loot_remains}" }
      - { salvage: "{verbs.salvage_gear}" }
      - { trim: "{verbs.trim_wick}" }
    intended_dynamics:
      - depth choice trades oil for better drops
      - salvage turns worn gear back into light
    intended_aesthetics: [challenge, discovery]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.oil_per_floor}"
    status: draft
    implemented_in: ["impl/lanternfall/core/loops/floor_sweep.py"]
  expedition:
    timescale: meta
    duration: "~45 min"
    sequence:
      - { camp: "{verbs.make_camp}" }
      - { floors: "{loops.floor_sweep}" }
      - { knell: "{verbs.ring_the_knell}" }
      - { sanctum: "{verbs.breach_sanctum}" }
      - { flee: "{verbs.flee_upward}" }
    intended_dynamics:
      - the decision to flee is as important as the decision to fight
      - bosses are optional until the sanctum
    intended_aesthetics: [challenge, discovery, fantasy]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.expedition_length}"
      - "{balance_targets.clear_rate}"
    status: draft
    implemented_in: ["impl/lanternfall/core/loops/expedition.py"]
---

## Tokens

Three nested loops: `{loops.delve_turn}` (a moment loop, driven by the lantern clock) inside `{loops.floor_sweep}` (one floor) inside `{loops.expedition}` (one descent and return).

## Rationale

**The clock is the lantern.** `delve_turn` declares `clock:`; every verb in it burns oil through `{clocks.lantern_burn}`. There is no turn timer.

**Floors are the unit of risk.** A floor sweep is where the player decides whether to go deeper. Salvage and trimming the wick close the floor; both are optional, both cost oil.

**Expeditions end by choice.** Fleeing upward is a verb, not a failure state: `{loops.expedition}` ends when the lamplighter flees, clears the sanctum, or the lantern gutters.
