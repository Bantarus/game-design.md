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
  action_order:
    type: ordering_rule
    over: "{entities.deployed_units}"
    filter: { lifecycle: alive }
    sort:
      - { by: deploy_order, direction: asc }
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/rng/action_order.py"]
  damage_roll:
    type: discrete_sum
    samples: 3
    range: [-1, 1]
    params_from:
      mean: "{actor.attack}"
    clamp: [1, 99]
    status: draft
    implemented_in: ["src/rng/damage.py"]
---

## Tokens

Two named distributions: `action_order` (an ordering_rule — deterministic
computation, not a sample), and `damage_roll` (integer-native discrete_sum).

## Rationale

**`ordering_rule` (D-014 / spec §4.8).** Action order in an auto-battler is
typically deterministic-from-state — sorted by deploy_order (or speed, or
some tiebreaker). The `ordering_rule` distribution type expresses this without
inventing a "deterministic sort" primitive.

**`discrete_sum` over `gaussian` for damage** — required for cross-engine
determinism (D-016). Pure integer arithmetic, bit-identical across engines
that share the pinned PRNG.

**PRNG reference vectors.** Pre-filled with the canonical xoshiro256** values
at canonical_seed=0; any engine implementing this game MUST self-validate
against these at adapter startup. Mismatch = misimplemented PRNG = drift at
the very first sample.
