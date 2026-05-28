---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: units
schema:
  required: [id, name, max_hp, attack, cost]
  properties:
    id:      { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:    { type: string }
    max_hp:  { type: integer, minimum: 1 }
    attack:  { type: integer, minimum: 0 }
    cost:    { type: integer, minimum: 0, maximum: 99 }
    tags:    { type: array }
data_dir: ../../content/units
count_target: 20
---

## Schema

Required: id, name, max_hp, attack, cost. Optional: tags (for synergy
identification — e.g., "infantry", "ranged", "armor").

## Representative Example

See `content/units/example_unit.yaml`. These are TEMPLATES — the runtime
hp / lifecycle of a DEPLOYED instance lives in
`entities.deployed_units.per_instance_state`.
