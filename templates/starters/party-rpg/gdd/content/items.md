---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: items
schema:
  required: [id, name, slot, effects]
  properties:
    id:      { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:    { type: string }
    slot:    { enum: [weapon, armor, accessory, consumable] }
    effects: { type: array }
data_dir: ../../content/items
count_target: 30
---

## Schema

Four required fields: `id` (slug), `name` (display), `slot` (where it's
equipped or how it's used), `effects` (array of effect objects).

## Representative Example

See `content/items/example_item.yaml`.
