---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/rng/**/*.py"]
prng:
  algorithm: xoshiro256_starstar
  seeding: splitmix64
  reference_vector:
    canonical_seed: 0
    outputs:
      - "0x860bfe4fec669882"
      - "0x829cde4321bdff18"
      - "0xd57ceaee872782c9"
      - "0xc47fc8ff58359611"
      - "0x71718b5da1661407"
  uniform_int_reference_vector:
    - canonical_seed: 0
      range: [0, 7]
      outputs: [2, 0, 1, 1, 7, 2, 5, 6]
    - canonical_seed: 0
      range: [0, 6]
      outputs: [1, 1, 5, 6, 1, 5, 0, 3]
distributions:
  initiative_roll:
    type: discrete_sum
    samples: 1
    range: [1, 20]
    params_from:
      mean: "{actor.speed}"
    clamp: [1, 99]
    status: draft
    implemented_in: ["src/rng/initiative.py"]
  damage_roll:
    type: discrete_sum
    samples: 3
    range: [-1, 1]
    params_from:
      mean: "{actor.attack}"
    clamp: [1, 99]
    status: draft
    implemented_in: ["src/rng/damage.py"]
  enemy_action_choice:
    type: weighted
    options:
      attack: { weight: 70, value: attack }
      defend: { weight: 20, value: defend }
      flee:   { weight: 10, value: flee }
    selection_rule: declaration_order_first_above
    status: draft
    implemented_in: ["src/rng/enemy_action.py"]
---

## Tokens

Three named distributions: initiative_roll (turn order), damage_roll (per-
attack damage), enemy_action_choice (AI selection).

## Rationale

`enemy_action_choice` demonstrates the D-014 value-bearing options shape —
each option carries both a weight and a value. `selection_rule:
declaration_order_first_above` is the D-017 normative selection rule for
cross-engine determinism.
