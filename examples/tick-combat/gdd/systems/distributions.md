---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: prototyped
last_verified: "2026-05-23"
implemented_in:
  - "impl/xtreme/src/distributions.rs"
  - "impl/xtreme/src/prng.rs"
  - "impl/godot/src/distributions.gd"
  - "impl/godot/src/prng.gd"
prng:
  # D-015 / Phase 4+ / spec §4.7. xoshiro256** + splitmix64 — the project-
  # neutral default. Both engines (xtreme/Rust and Godot/GDScript) implement
  # this from scratch; the reference_vector is the spec-side self-validation
  # vector that both engines must match before any trajectory comparison.
  algorithm: xoshiro256_starstar
  seeding:   splitmix64
  reference_vector:
    canonical_seed: 0
    outputs:
      - "0x860bfe4fec669882"
      - "0x829cde4321bdff18"
      - "0xd57ceaee872782c9"
      - "0xc47fc8ff58359611"
      - "0x71718b5da1661407"
  # D-018 / Phase 4++ / spec §4.7. Reduction-layer self-validation. Two
  # entries chosen so a misimplemented reduction fails at adapter startup,
  # not at trajectory tick N (which is how the F-007 GDScript-modulo bug
  # survived to tick 2 the first time). Draw #1 at canonical_seed=0 is
  # adversarial: first raw u64 = 0x860bfe4fec669882 (high bit set) → a
  # naive signed `raw % w` returns negative; the naive-corrected form
  # `((raw % w) + w) % w` matches the correct u64 modulo for the pow-of-
  # two entry (because 2^64 mod 8 = 0) but FAILS for the non-pow-of-two
  # entry (because 2^64 mod 7 = 2). The pair narrows diagnosis: a no-
  # correction impl fails both; a naive-corrected impl fails only the
  # non-pow-of-two; a correct 32-bit-halves-split impl passes both.
  uniform_int_reference_vector:
    - canonical_seed: 0
      range: [0, 7]           # power-of-two w=8 (bias-free)
      outputs: [2, 0, 1, 1, 7, 2, 5, 6]
    - canonical_seed: 0
      range: [0, 6]           # non-power-of-two w=7 (catches the naive-corrected form)
      outputs: [1, 1, 5, 6, 1, 5, 0, 3]
distributions:
  action_order:
    # D-011 / Phase-2.5 resolution of ambiguity #1: action_order is an
    # *ordering procedure* over the alive roster, not a literal sequence.
    # Pure deterministic sort — no PRNG involvement.
    type: ordering_rule
    over: "{entities.units}"
    filter: { lifecycle: alive }
    sort:
      - { by: speed,        direction: desc }   # primary
      - { by: deploy_order, direction: asc  }   # tie-break
    seed: deterministic_per_run
    status: prototyped
    implemented_in: ["impl/xtreme/src/distributions.rs"]
  damage_roll:
    # D-016 / Phase 4+ resolution of #13 + #15: integer-native gaussian-like.
    # sum 3 PRNG draws each uniform int in [-1, +1], then add params_from.mean
    # (the actor's attack stat), then clamp. Variance = 3 × ((1-(-1)+1)²−1)/12 = 2;
    # stddev ≈ √2 ≈ 1.41 (close to the previous continuous gaussian(stddev=1),
    # but bit-identical across engines that share the pinned xoshiro256**).
    # No transcendentals; no IEEE-754 ULP drift; no half_to_even boundary flips.
    type: discrete_sum
    samples: 3
    range: [-1, 1]
    params_from:
      mean: "{actor.attack}"
    clamp: [1, 99]
    output_domain: integer
    seed: deterministic_per_run
    status: prototyped
    implemented_in: ["impl/xtreme/src/distributions.rs"]
  critical_hit:
    # D-016 / D-017 / Phase 4+: integer uniform with explicit selection_rule.
    # range [0, 9] inclusive; sample < threshold (1) → crit. 1-in-10 = 10%
    # crit rate, semantically identical to the previous [0.0,1.0] threshold 0.10
    # but no floats involved.
    type: uniform
    range: [0, 9]
    threshold: 1
    output_domain: integer
    selection_rule: less_than
    seed: deterministic_per_run
    status: prototyped
    implemented_in: ["impl/xtreme/src/distributions.rs"]
  gold_drop:
    # D-014 (value-bearing) + D-016 (integer weights) + D-017 (declaration-
    # order_first_above selection rule with strict > on the running sum).
    # total_weight = 60 + 30 + 10 = 100; draw = rng.next_u64() mod 100;
    # walk cumulative in declaration order; first option whose c > draw wins.
    # Expected per drop: 0.60×1 + 0.30×3 + 0.10×10 = 2.5; combat_resolution
    # declares count: 6 → expected ~15 gold per encounter, inside the [10, 20]
    # band by design.
    type: weighted
    options:
      small:  { weight: 60, value: 1 }
      medium: { weight: 30, value: 3 }
      large:  { weight: 10, value: 10 }
    selection_rule: declaration_order_first_above
    seed: deterministic_per_run
    status: prototyped
    implemented_in: ["impl/xtreme/src/distributions.rs"]
---

## Tokens

Four distributions plus the tree-level `prng:` declaration that all stochastic distributions inherit. `{distributions.action_order}` is pure-deterministic (no PRNG); the other three are sampled from the pinned `xoshiro256_starstar + splitmix64` source.

## Rationale

**Why the integer-native rewrite (Phase 4+, D-015 + D-016 + D-017).** Phase 4's Godot adapter exposed three classes of cross-engine under-determination: the spec didn't pin the PRNG (#12), the gaussian sampling algorithm (#13), or the `weighted.options` iteration/selection rule (#14). Pinning a continuous-gaussian sampling method (#13) would still have left #15 latent — IEEE-754 doesn't mandate correctly-rounded `log`/`exp`/`sin`/`cos`, so even with the same PRNG and the same method, two engines' raw float gaussian samples differ in the last ULP and `round_mode: half_to_even` eventually flips near `.5` boundaries. The integer-native rewrite resolves #13 and #15 together by eliminating floats from the simulation path.

**Tree-level `prng:` declaration.** `xoshiro256_starstar + splitmix64` is the project-neutral default per spec §4.7. The reference vector is the spec-side hook that each engine self-validates against at adapter startup — divergence in the first 5 raw `u64` outputs at `canonical_seed: 0` means the engine has misimplemented the PRNG or seeding, surfacing the bug *before* any trajectory comparison runs. Both `impl/xtreme/src/distributions.rs` and `impl/godot/src/distributions.gd` carry a `reference_vector_self_check()` that asserts byte equality with the table above.

**Reduction-layer vector (Phase 4++, D-018).** The raw-stream vector stops one layer too early — Phase 4+ caught the F-007 reduction bug (GDScript's signed-int64 `int % w` differs from Rust's u64 modulo for high-bit-set raws) only at trajectory tick 2, after both engines had passed the raw vector cleanly. The `uniform_int_reference_vector:` block extends the contract to the integer-reduction step: two `(canonical_seed, range, outputs)` entries, one pow-of-two `w` (validates the reduction itself) and one non-pow-of-two `w` (catches the naive-corrected form, which silently equals the correct `u64 % w` only when `2^64 mod w = 0`). Draw #1 is adversarial — a wrong reduction fails at adapter startup, not at tick N. Both engines call `uniform_int_reference_vector_self_check()` alongside the raw-vector check in `Simulation::new()`.

**`action_order` is `ordering_rule`, not a literal sequence.** Unchanged from Phase 2.5 — the procedure is computable: sort the units in `{entities.units}` filtered to `lifecycle: alive`, primary key `speed desc`, tie-break by `deploy_order asc`. No PRNG involvement.

**Rotation semantics (resolves ambiguity #9).** `action_order` produces an ordered list every tick. `{rules.tick_resolution}` indexes that list by `tick_number mod len(list)` — one unit acts per tick. The `120 median ticks` balance target implies ~20 actions per unit across 6 alive units, which is the rotation form.

**`damage_roll` is integer-native discrete_sum (Phase 4+).** Three uniform-integer draws each in `{−1, 0, +1}` summed and added to the acting unit's `attack` stat (D-012 templating preserved). For an attacker with `attack = 5`, samples land in `[5−3, 5+3] = [2, 8]` (then clamped to `[1, 99]`) with variance 2. Pure integer arithmetic on the pinned PRNG's `u64` outputs; no math-library dependency; byte-identical across every engine that shares xoshiro256** + splitmix64. Replaces the Phase-2.5 `type: gaussian + round_mode: half_to_even` form, which Phase 4+ found vulnerable to the libm transcendental ULP drift (#15).

**`critical_hit` at 10%, integer form (Phase 4+).** Integer uniform on `[0, 9]` inclusive; `selection_rule: less_than` with `threshold: 1` → crit when `sample < 1`, i.e. `sample == 0`. Probability 1/10 = 10%, semantically identical to the previous float `[0.0, 1.0] threshold 0.10` but no floats involved. The integer reformulation predicted at Phase 2.5 is now normative.

**`gold_drop` is weighted with integer weights + declaration-order selection rule.** Per D-014 each option carries `{weight, value}`; per D-016 the weights are integers (the previous floats `0.6/0.3/0.1` are now `60/30/10`); per D-017 the selection rule is `declaration_order_first_above` — walk options in YAML declaration order, first option whose running cumulative sum strictly exceeds the draw wins. Expected gold per drop = `(60×1 + 30×3 + 10×10) / 100 = 250/100 = 2.5`; `{rules.combat_resolution}` declares `count: 6` → expected ~15 gold per encounter, inside the `gold_per_encounter: 14, tolerance: [10, 20]` band by design.

## Open Questions

- The closed PRNG vocabulary at v0.2.0-alpha is `xoshiro256_starstar | chacha20 | pcg32 | pcg64`. Other potential additions (xoshiro128++, mt19937, romu) are out of scope until a real example needs them; `pcg32`/`pcg64` are reserved-but-not-implemented until a concrete need arises.
- `gaussian` remains a legal distribution type for cosmetic/presentation-noise use (D-016), but tick-combat's `gdd/` declares no such use. If a future presentation-layer feature needs gaussian-shaped jitter, declare it under a separate distribution name (e.g. `screen_shake_jitter`) with `output_domain: real` and explicit "non-cross-engine, presentation-only" prose.
- The cumulative-sum sampling in `gold_drop` walks options in declaration order. PyYAML 5.1+ preserves YAML map order, and both Rust (`indexmap`/`BTreeMap` if used) and GDScript (`Dictionary` preserves insertion order in Godot 4) honor this — but a future engine using a hash-map would diverge. D-017's normative declaration_order rule blocks that engine's compliance; the linter does NOT yet enforce iteration discipline at the impl level (a Phase 5+ idea).
