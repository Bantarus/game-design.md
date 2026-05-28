---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: levels
schema:
  required: [id, name, spawn_point, exit_point]
  properties:
    id:           { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:         { type: string }
    spawn_point:  { type: object }
    exit_point:   { type: object }
    hazards:      { type: array }
data_dir: ../../content/levels
count_target: 10
---

## Schema

Required: id, name, spawn_point, exit_point. Optional: hazards (array of
hazard placements with positions + types).

## Representative Example

See `content/levels/example_level.yaml`.
