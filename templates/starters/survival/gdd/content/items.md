---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: items
schema:
  required: [id, name, kind]
  properties:
    id:               { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:             { type: string }
    kind:             { enum: [tool, food, material, container] }
    max_durability:   { type: integer, minimum: 1 }
    max_stack:        { type: integer, minimum: 1, maximum: 64 }
    edible:           { type: boolean, default: false }
data_dir: ../../content/items
count_target: 20
---

## Schema

Item templates. Durability + stack-size limits are templates; runtime values
(current durability, current quantity) live on
`entities.inventory.per_instance_state`.

## Representative Example

See `content/items/example_item.yaml`.
