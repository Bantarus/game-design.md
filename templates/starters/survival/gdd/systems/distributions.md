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
  gather_yield:
    type: weighted
    options:
      nothing:  { weight: 30, value: 0 }
      small:    { weight: 50, value: 1 }
      large:    { weight: 20, value: 3 }
    selection_rule: declaration_order_first_above
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/rng/gather.py"]
---

## Tokens

One named distribution: `gather_yield` (the number of items returned per
gather action).

## Rationale

The weighted-with-values shape demonstrates D-014's value-bearing weighted
options. `selection_rule: declaration_order_first_above` is D-017's normative
selection rule.
