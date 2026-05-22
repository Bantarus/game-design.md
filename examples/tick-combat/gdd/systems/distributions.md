---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
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

**`damage_roll` is gaussian with rounding.** Mean 5, stddev 1, clamp `[1, 99]`. `{invariants.damage_is_integer}` requires half-to-even rounding at the point of application, not at sampling, so the order of operations between rolls and rounds is fixed.

**`critical_hit` at 10%.** Uniform threshold roll, lower than the deckbuilder's 15% because Lockstep's tick count is higher — a 15% crit rate over 120 ticks would be too swingy.

**`gold_drop` is weighted.** Small/medium/large drops at 60/30/10. Composite payouts (multiple drops per encounter) are resolved by multiple independent rolls, not by a composite distribution — keeps the static-checkability promise from `{invariants.deterministic_given_seed}`.
