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
    rule: "All damage, hp, and mp quantities resolve to integers."
    applies_to: ["{resources}"]
    enforcement: lint
    severity: error
  per_instance_state_is_writable:
    kind: layer_boundary
    rule: "Runtime writes mutate `per_instance_state` fields ONLY. Templates (content_collection entries) and container properties are immutable per spec §3, §4.5 D-019."
    applies_to: ["{entities.party_members}", "{entities.items}", "{states.hero_lifecycle}"]
    enforcement: lint
    severity: error
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed, all distribution draws are reproducible."
    applies_to: ["{distributions}"]
    enforcement: verify
    severity: error
---

## Tokens

Three invariants. The per_instance_state_is_writable invariant is the F-008
v0.3 binding contract — it's what the `write-to-template-field` lint rule
(§9.1) catches statically.

## Rationale

A turn-based party RPG with item / equipment systems leans heavily on the
template / instance distinction; the invariant makes the contract explicit
so the engine doesn't accidentally mutate a hero TEMPLATE when it meant to
mutate a hero INSTANCE.
