---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-04-18"
invariants:
  vigor_is_integer:
    kind: numeric_domain
    rule: Vigor, ward focus and every monster's max_vigor resolve to integers.
    applies_to:
      - "{resources.vigor}"
      - "{resources.ward_focus}"
      - "{entities.monsters}"
    enforcement: lint
    severity: error
  oil_only_via_clock:
    kind: architectural_pattern
    rule: "Lantern oil changes only through the lantern clock and the rules it drives; no verb writes oil directly."
    applies_to:
      - "{clocks.lantern_burn}"
      - "{resources.lantern_oil}"
    enforcement: advisory
    severity: warning
  seeded_rolls:
    kind: determinism
    rule: Given a fixed expedition seed, strikes, drop quality and depth bands are reproducible.
    applies_to:
      - "{distributions.strike_roll}"
      - "{distributions.drop_quality}"
      - "{distributions.depth_band}"
    enforcement: verify
    severity: error
  sim_owns_lantern_state:
    kind: layer_boundary
    rule: "The simulation owns the lantern state machine; presentation only reads it."
    applies_to:
      - "{states.lantern_state}"
    enforcement: lint
    severity: error
  events_one_way:
    kind: communication
    rule: "The simulation emits events to presentation; presentation never calls back into it."
    enforcement: advisory
    severity: warning
---

## Tokens

Five invariants: one numeric domain, one architectural pattern, one determinism contract, one layer boundary and one communication rule.

## Rationale

**Oil is sacred.** Every design decision in Lanternfall assumes oil moves only through the clock. A verb that refilled oil directly would break the per-verb delta and with it every balance target on this tree.
