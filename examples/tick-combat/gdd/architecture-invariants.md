---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
invariants:
  damage_is_integer:
    kind: numeric_domain
    rule: "All damage, hp, and gold quantities resolve to integers. The gaussian damage roll rounds at apply (half-to-even)."
    applies_to:
      - "{resources.gold}"
      - "{rules.tick_resolution}"
    enforcement: lint
    severity: error
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed and identical setup, every encounter produces byte-identical state at every tick. The deterministic action order is the load-bearing piece."
    applies_to:
      - "{distributions.action_order}"
      - "{distributions.damage_roll}"
      - "{distributions.critical_hit}"
      - "{distributions.gold_drop}"
    enforcement: verify
    severity: error
  units_act_only_when_alive:
    kind: architectural_pattern
    rule: "A unit in state {states.unit_lifecycle.dead} or {states.unit_lifecycle.stunned} produces no actions on its tick."
    applies_to:
      - "{states.unit_lifecycle}"
      - "{rules.tick_resolution}"
    enforcement: advisory
    severity: warning
---

## Tokens

Three invariants. The two load-bearing ones (`damage_is_integer`, `deterministic_given_seed`) are the contract that makes Lockstep's replay-share feature actually work.

## Rationale

### damage_is_integer

Damage shows as integers on the HUD; the gaussian distribution `{distributions.damage_roll}` is clamped to `[1, 99]` and rounded half-to-even at apply. Lint statically verifies all `effects[].amount` in `content/units/*.yaml` are integers.

**Why:** if damage were floating-point, two replays of the same seed could diverge after a few hundred ticks due to floating-point order-of-operations. Integer-domain damage closes that source of non-determinism.

### deterministic_given_seed

The contract is binding. Two clients on the same seed must produce byte-identical state at every tick. The verify adapter (when one ships) runs the same encounter twice and diffs.

**Why:** the entire replay-share feature lives or dies on this. A regression here is a launch blocker.

### units_act_only_when_alive

Advisory — there's no clean static check. The reminder is for code review: when a unit's turn comes up in the deterministic order, the tick resolver must consult `{states.unit_lifecycle}` before invoking its action.

**Why:** v0.0.3 internal had a regression where stunned units still attacked. The state check fixes it; the invariant prevents regression.
