---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: prototyped
last_verified: "2026-05-22"
implemented_in:
  - "impl/xtreme/src/distributions.rs"
distributions:
  action_order:
    # D-011 / Phase-2.5 resolution of ambiguity #1: action_order is an
    # *ordering procedure* over the alive roster, not a literal sequence.
    # New type `ordering_rule` (added v0.2.0-alpha) replaces the prose-string
    # `deterministic.sequence: [...]` form.
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
    type: gaussian
    # D-012: distribution parameter sourced from rule-evaluation context.
    # The acting unit's `attack` field becomes the gaussian mean; stddev
    # remains a small fixed variance. This is the resolution of ambiguity
    # #8 (unit.attack was decorative; now it actually scales damage).
    params_from:
      mean: "{actor.attack}"
    stddev: 1
    clamp: [1, 99]
    output_domain: integer        # D-010
    round_mode: half_to_even      # D-010
    seed: deterministic_per_run
    status: prototyped
    implemented_in: ["impl/xtreme/src/distributions.rs"]
  critical_hit:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.10
    seed: deterministic_per_run
    status: prototyped
    implemented_in: ["impl/xtreme/src/distributions.rs"]
  gold_drop:
    type: weighted
    # D-014 / ambiguity #4 resolution: weighted options carry per-category
    # value, not just probability. The expected gold per drop is
    # 0.6*1 + 0.3*3 + 0.1*10 = 2.5; combat_resolution declares count: 6,
    # producing expected ~15 gold per encounter (inside the [10, 20] band).
    options:
      small:  { weight: 0.6, value: 1 }
      medium: { weight: 0.3, value: 3 }
      large:  { weight: 0.1, value: 10 }
    seed: deterministic_per_run
    status: prototyped
    implemented_in: ["impl/xtreme/src/distributions.rs"]
---

## Tokens

Four distributions. `{distributions.action_order}` is the load-bearing `deterministic` distribution — given a seed plus the deployed units, the tick-by-tick order is fully reproducible.

## Rationale

**`action_order` is `ordering_rule`, not a literal sequence.** The new type was added at v0.2.0-alpha specifically to fix the Phase-2 ambiguity (#1) where `deterministic.sequence: ["highest_speed_first", "tie_break_by_deployment_order"]` left two engines to interpret prose. Now the procedure is computable: sort the units in `{entities.units}` (filtered to lifecycle alive), primary key speed descending, tie-break by deployment order ascending. Identical inputs → identical ordering, byte-for-byte across engines.

**Rotation semantics (resolves ambiguity #9).** `action_order` produces an ordered list every tick. `{rules.tick_resolution}` indexes that list by `tick_number mod len(list)` — one unit acts per tick, the next unit acts on the next tick, and the rotation skips dead/stunned units (because the `filter: { lifecycle: alive }` excludes them). The `120 median ticks` balance target implies ~20 actions per unit across 6 alive units, which is exactly the rotation form, not the dominate form.

**`damage_roll` is gaussian with declared integer rounding and templated mean.** Mean is sourced from the acting unit's `attack` field via `params_from: { mean: "{actor.attack}" }` (D-012). Stddev is fixed at 1 — small variance around each unit's intrinsic damage. Clamp `[1, 99]`, `round_mode: half_to_even`. Per D-010, rounding happens *at the point of application* by `{rules.tick_resolution}`, after `clamp`, in canonical order (sample → clamp continuous → round half-to-even → integer-clamp belt-and-suspenders). Half-to-even is supported by both Rust's `f64::round_ties_even()` (since 1.77) and Unreal's `FMath::RoundHalfToEven`.

**`critical_hit` at 10%.** Uniform threshold roll. Spec §4.7 canonicalizes the comparison: `sample <= threshold` returns true (D-010 boundary clarification, Phase-2 ambiguity #3). The integer reformulation (`range: [0, 99], threshold: 9`) remains a candidate for v0.3 if Phase 4 surfaces float-comparison drift between Rust and the Blueprint VM; for now the float form holds because xtreme's seed-determinism check passes and the canonical `<=` direction is normative.

**`gold_drop` is weighted with per-category value.** Per D-014 (resolves ambiguity #4), each option carries `{ weight, value }`. Expected gold per drop = `0.6×1 + 0.3×3 + 0.1×10 = 2.5`. `{rules.combat_resolution}` declares `count: 6` on the gold_drop step (resolves ambiguity #6), producing expected ~15 gold per encounter — inside the `gold_per_encounter: 14, tolerance: [10, 20]` band by design, not by coincidence.
