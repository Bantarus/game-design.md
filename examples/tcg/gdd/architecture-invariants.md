---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
invariants:
  damage_is_integer:
    kind: numeric_domain
    rule: "Card damage, life, and mana resolve to integers. Lattice has no continuous distributions — every numeric value is integer at the schema level."
    applies_to:
      - "{resources.life}"
      - "{resources.mana}"
      - "{rules.attack_resolution}"
    enforcement: lint
    severity: error
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed and the same two decklists, every game is byte-identical: the same draws, the same first-player coin flip, the same resolution order."
    applies_to:
      - "{distributions.card_draw}"
      - "{distributions.first_player}"
      - "{distributions.mulligan_decision}"
    enforcement: verify
    severity: error
  phase_order_is_immutable:
    kind: architectural_pattern
    rule: "The phase cycle in {states.phase_state} (untap → upkeep → main → combat → endphase → untap) cannot be reordered, skipped, or short-circuited by any card effect."
    applies_to:
      - "{states.phase_state}"
      - "{rules.card_play_resolution}"
    enforcement: advisory
    severity: warning
---

## Tokens

Three invariants. Two load-bearing (`damage_is_integer`, `deterministic_given_seed`); one advisory (`phase_order_is_immutable`).

## Rationale

### damage_is_integer

The simplest of the three — Lattice has no gaussian distribution; every card prints an integer value. The lint check is trivially passing on a clean design.

**Why:** the integer domain is what lets `{distributions.card_draw}`'s `shuffle_bag` be fully deterministic. Float math would re-introduce non-determinism through accumulated rounding.

### deterministic_given_seed

Lattice's flagship feature (in a future v0.2) is the **shareable seed** — paste a seed code into a friend's client, both clients play the same opening hands, the same mulligans, the same first-player. The contract is identical to Lockstep's.

**Why:** without seed-determinism, "replay this game" is a feature that lies.

### phase_order_is_immutable

Advisory because there's no clean static check for "no card breaks the phase cycle." The reminder lives here for code review and for verify-time observation: an adapter watching the phase machine should see exactly `untap → upkeep → main → combat → endphase → untap` per turn, no skips.

**Why:** the spec for the original Magic-style game allowed "skip your combat phase" cards. Those cards introduce edge cases the design isn't prepared to balance against in v0.1. Forbidden by invariant.
