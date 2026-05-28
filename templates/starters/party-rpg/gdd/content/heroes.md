---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: heroes
schema:
  required: [id, name, max_hp, max_mp, attack, defense, speed]
  properties:
    id:       { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:     { type: string }
    max_hp:   { type: integer, minimum: 1 }
    max_mp:   { type: integer, minimum: 0 }
    attack:   { type: integer, minimum: 0 }
    defense:  { type: integer, minimum: 0 }
    speed:    { type: integer, minimum: 1 }
---

## Schema

Hero templates. The fields here are IMMUTABLE — read at simulation time as
the upper bound or base value (max_hp, attack, etc.). Runtime mutable fields
(current hp, current mp) live on `entities.party_members.per_instance_state`.

## Representative Example

See `content/heroes/example_hero.yaml`.
