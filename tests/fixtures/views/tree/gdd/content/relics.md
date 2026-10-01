---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-09-30"
entity: relics
schema:
  required: [id, name]
  properties:
    id: { type: string }
    name: { type: string }
data_dir: ../../content/relics
count_target: 2
balance_refs: ["{balance_targets.focus_per_day}"]
---

## Schema

See frontmatter.

## Representative Example

`content/relics/lamp.yaml`.
