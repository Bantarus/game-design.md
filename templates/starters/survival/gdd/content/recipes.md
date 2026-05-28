---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: recipes
schema:
  required: [id, name, inputs, output]
  properties:
    id:     { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:   { type: string }
    inputs: { type: array }
    output: { type: object }
data_dir: ../../content/recipes
count_target: 15
---

## Schema

Crafting recipes. Each recipe declares its `inputs:` (array of
`{ item_id, quantity }`) and an `output:` (one item template + quantity).

## Representative Example

See `content/recipes/example_recipe.yaml`.
