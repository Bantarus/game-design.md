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
distributions:
  hazard_variation:
    type: weighted
    options:
      slow:   { weight: 50, value: slow }
      medium: { weight: 35, value: medium }
      fast:   { weight: 15, value: fast }
    selection_rule: declaration_order_first_above
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/rng/hazard.py"]
---

## Tokens

One named distribution: `hazard_variation` (the per-level random hazard
behavior).

## Rationale

A precision platformer typically has LITTLE randomness — most variance is
in player skill, not RNG. Where randomness exists (hazard timing variations,
particle effects), it MUST be named and deterministic-per-run so replays
reproduce.
