---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/invariants/**/*.py"]
invariants:
  meters_are_integer:
    kind: numeric_domain
    rule: "Hunger, thirst, fatigue, and durability are integer-valued."
    applies_to: ["{resources}"]
    enforcement: lint
    severity: error
  per_instance_state_is_writable:
    kind: layer_boundary
    rule: "Inventory item runtime writes mutate `per_instance_state` (durability, charges, quantity) ONLY. Item TEMPLATES are immutable."
    applies_to: ["{entities.inventory}"]
    enforcement: lint
    severity: error
  time_advances_only_via_clock:
    kind: communication
    rule: "World time advances ONLY via the `world_time` clock (which reads each verb's `time_cost.in_game_minutes`). Verbs do not directly mutate world-time state."
    applies_to: ["{clocks.world_time}"]
    enforcement: advisory
    severity: warning
---

## Tokens

Three invariants. The time_advances_only_via_clock invariant is the F-010
v0.3 binding contract — it's what prevents the "ad-hoc advance world time
in some rule's do[]" pattern that F-010 was the resolution for.
