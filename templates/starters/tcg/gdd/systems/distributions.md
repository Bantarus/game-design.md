---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/rng/**/*.py"]
prng:
  algorithm: chacha20
  seeding: splitmix64
  reference_vector:
    canonical_seed: 0
    outputs:
      - "0x0000000000000000"
      - "0x0000000000000000"
      - "0x0000000000000000"
      - "0x0000000000000000"
      - "0x0000000000000000"
  uniform_int_reference_vector:
    - canonical_seed: 0
      range: [0, 7]
      outputs: [0, 0, 0, 0, 0, 0, 0, 0]
distributions:
  card_draw:
    type: shuffle_bag
    of: "{entities.cards}"
    refill_when: empty
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/rng/card_draw.py"]
  opening_hand:
    type: shuffle_bag
    of: "{entities.cards}"
    refill_when: per_run
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/rng/opening_hand.py"]
---

## Tokens

Two named distributions: card_draw (per-turn shuffle bag) and opening_hand
(per-match shuffle bag, refilled at match start).

## Rationale

**`chacha20` over `xoshiro256_starstar`.** For TWO-player TCGs where seed
predictability could become an exploit, the cryptographic-quality
unpredictability of ChaCha20 is the right tradeoff against its slightly
heavier implementation cost (D-015). For single-player TCGs (puzzle modes,
solo campaigns), `xoshiro256_starstar` is the cheaper-and-equivalent default.

**Reference vectors must be filled in.** The above vectors are placeholders
(all-zeros). Generate real reference vectors by running your ChaCha20
implementation with `canonical_seed: 0` and recording the first 5 raw u64
outputs + the first 8 uniform-int outputs at `range: [0, 7]`. Two engines
that disagree on these vectors have misimplemented the PRNG.
