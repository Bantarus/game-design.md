---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
---

## Tokens

This directory contains content-schema files (`cards.md`, `enemies.md`, ...).
Each content-schema file declares the shape every per-entity YAML file under
`content/<kind>/*.yaml` must validate against.

## Rationale

Content-heavy types (`count_target >= 20`) MUST live in external YAML files
per spec §6. Each content-schema file is the single place to update the entity
shape; the per-entity YAMLs are the authored content.
