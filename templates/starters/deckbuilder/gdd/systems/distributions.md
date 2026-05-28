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
  card_draw:
    type: shuffle_bag
    of: "{entities.cards}"
    refill_when: empty
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/rng/card_draw.py"]
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

Two named distributions: `card_draw` (shuffle_bag over the cards collection)
and `damage_roll` (integer-native discrete_sum, suitable for cross-engine
determinism per D-016).

The `prng:` block pins the random number generator at the tree level — every
distribution defaults to xoshiro256** unless it overrides. The
`reference_vector:` + `uniform_int_reference_vector:` let any engine self-
validate against the spec at adapter startup (D-015, D-018).

## Rationale

**`card_draw` as shuffle_bag.** Bagged draws (no replacement until empty) are
the canonical deckbuilder card-flow distribution. The bag refills when empty,
which matches the typical "discard reshuffles into deck" behavior.

**`damage_roll` as discrete_sum.** Integer-native gaussian-like; bit-identical
across engines that share the pinned PRNG (D-016). For continuous gaussian
randomness use the `gaussian` type — but ONLY for non-state-affecting cosmetic
noise; state-affecting integer draws use `discrete_sum`.

**When you add a new randomness source**, name it here. Inline `random.choice()`
in source code is forbidden — the linter's `undefined-distribution` rule fires
on any `do[].sample` that doesn't reference `{distributions.<id>}`.
