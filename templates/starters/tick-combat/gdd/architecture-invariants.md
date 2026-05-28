---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/invariants/**/*.py"]
invariants:
  gameplay_state_is_integer:
    kind: numeric_domain
    rule: "All hp, damage, gold, and gameplay-state quantities resolve to integers. Floats are forbidden in trajectory-affecting state."
    applies_to: ["{resources}"]
    enforcement: lint
    severity: error
  per_instance_state_is_writable:
    kind: layer_boundary
    rule: "Runtime writes mutate `per_instance_state` fields ONLY. Unit TEMPLATES are immutable."
    applies_to: ["{entities.deployed_units}", "{states.unit_lifecycle}"]
    enforcement: lint
    severity: error
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed and identical deployment, the per-tick trajectory is byte-identical across engines. Tick-combat's verify-adapter (§9.5) is the cross-engine gate."
    applies_to: ["{distributions}", "{clocks.tick}"]
    enforcement: verify
    severity: error
---

## Tokens

Three load-bearing invariants. The deterministic_given_seed invariant is
extra load-bearing here because tick-combat is the canonical cross-engine
case for the spec — the verify-adapter PASS on F-008 + F-010 closure is
what validates that v0.3's vocabulary preserves byte-identical trajectories.
