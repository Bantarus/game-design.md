---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-09-30"
invariants:
  focus_is_integer:
    kind: numeric_domain
    rule: "Focus resolves to an integer."
    applies_to: ["{resources.focus}"]
    enforcement: advisory
    severity: warning
---

## Rationale

### focus_is_integer

Fractional focus would make `{balance_targets.focus_per_day}` unmeasurable.
