---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/invariants/**/*.py"]
invariants:
  game_state_is_integer:
    kind: numeric_domain
    rule: "All life, mana, counters, and damage quantities resolve to integers."
    applies_to: ["{resources}"]
    enforcement: lint
    severity: error
  per_instance_state_is_writable:
    kind: layer_boundary
    rule: "Runtime writes mutate `per_instance_state` fields ONLY. Card TEMPLATES (content_collection entries) and container properties are immutable per spec §3, §4.5 D-019."
    applies_to: ["{entities.battlefield}", "{states.card_zone}"]
    enforcement: lint
    severity: error
  deterministic_given_seed:
    kind: determinism
    rule: "Shuffles, opening hands, and any card-selection randomness use named distributions only. Given identical decks and identical seed, two clients produce identical game state."
    applies_to: ["{distributions}"]
    enforcement: verify
    severity: error
---

## Tokens

Three load-bearing invariants. Determinism is especially load-bearing for
networked multiplayer — both clients must produce identical game state from
identical inputs.

## Rationale

The per_instance_state contract is what keeps a card on the battlefield from
silently mutating its template's stats; the determinism contract is what
keeps two clients in sync over a turn.
