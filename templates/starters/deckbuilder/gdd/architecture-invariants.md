---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/invariants/**/*.py"]
invariants:
  damage_is_integer:
    kind: numeric_domain
    rule: "All damage, health, and resource quantities resolve to integers."
    applies_to: ["{resources}"]
    enforcement: lint
    severity: error
  data_behavior_separation:
    kind: architectural_pattern
    rule: "Entities are data-only; logic lives in stateless rules that operate on them. No gameplay logic inside presentation/render code."
    applies_to: ["{entities}", "{rules}", "{states.card_lifecycle}"]
    enforcement: advisory
    severity: warning
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed, all distribution draws are reproducible. Card draws, damage rolls, and reward selection all use named distributions only."
    applies_to: ["{distributions}"]
    enforcement: verify
    severity: error
---

## Tokens

Three invariants the codebase must satisfy. The damage-is-integer invariant
catches float drift in the resolution pipeline; the data-behavior-separation
invariant catches gameplay logic creeping into UI; the deterministic-given-seed
invariant catches any rollback-breaking unnamed randomness.

## Rationale

These three are the load-bearing properties for a single-player deckbuilder.
A multiplayer deckbuilder would add `state_authoritative_on_server` or similar;
a roguelike-lite would add `seed_uniquely_identifies_run`. Add invariants when
the codebase needs a contract that's load-bearing across the implementation,
not for every property that seems "nice to have."
