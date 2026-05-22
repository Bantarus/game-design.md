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
    type: deterministic
    sequence:
      - "highest_speed_first"
      - "tie_break_by_deployment_order"
    seed: deterministic_per_run
    status: draft
    implemented_in: []
  damage_roll:
    type: gaussian
    mean: 5
    stddev: 1
    clamp: [1, 99]
    output_domain: integer        # D-010: simulation state is integer-domain
    round_mode: half_to_even      # D-010: canonical unbiased rounding
    seed: deterministic_per_run
    status: draft
    implemented_in: []
  critical_hit:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.10
    seed: deterministic_per_run
    status: draft
    implemented_in: []
  gold_drop:
    type: weighted
    options:
      small:  0.6
      medium: 0.3
      large:  0.1
    seed: deterministic_per_run
    status: draft
    implemented_in: []
---

## Tokens

Four distributions. `{distributions.action_order}` is the load-bearing `deterministic` distribution — given a seed plus the deployed units, the tick-by-tick order is fully reproducible.

## Rationale

**`action_order` is `deterministic` on purpose.** The "sequence" here is a *rule* expressed as a pair of ordered tie-break clauses, not a literal list of unit ids — at runtime the resolver sorts the alive roster by speed and breaks ties by deployment order. Two runs with the same seed and same deployment produce the same sequence.

**`damage_roll` is gaussian with declared integer rounding.** Mean 5, stddev 1, clamp `[1, 99]`. Per D-010, `output_domain: integer` + `round_mode: half_to_even` are declared inline so cross-engine implementations (Phase 4: xtreme + Unreal) round identically. Half-to-even (banker's rounding) is the unbiased choice and is supported by both Rust's `f64::round_ties_even()` (since 1.77) and Unreal's `FMath::RoundHalfToEven`. Rounding happens at the point of application by `{rules.tick_resolution}`, never at sample time — sampling produces the canonical real-valued sample, the consuming rule rounds.

**`critical_hit` at 10%.** Uniform threshold roll, lower than the deckbuilder's 15% because Lockstep's tick count is higher — a 15% crit rate over 120 ticks would be too swingy. **Note (D-010 follow-up):** the current float form (`range: [0.0, 1.0]`, `threshold: 0.10`) produces a boolean via float comparison; that comparison is the cross-engine divergence risk. Phase 2's xtreme implementation will test whether the float form holds under fixed seeds; if it doesn't, the reformulation is `range: [0, 99], threshold: 9` (integer-domain Bernoulli, same crit rate). Held in the soft form for v0.2.0-alpha so the migration is driven by evidence rather than preemption.

**`gold_drop` is weighted.** Small/medium/large drops at 60/30/10. Composite payouts (multiple drops per encounter) are resolved by multiple independent rolls, not by a composite distribution — keeps the static-checkability promise from `{invariants.deterministic_given_seed}`.
