---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-04-18"
entity: encounters
schema:
  required: [id, name, depth, monsters, spawn_roll]
  properties:
    id: { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name: { type: string, minLength: 1 }
    depth: { type: integer, minimum: 1, maximum: 5 }
    monsters: { type: array, minItems: 2, maxItems: 4 }
    spawn_roll: { type: string }
    description: { type: string }
data_dir: ../../content/encounters
count_target: 30
balance_refs:
  - "{balance_targets.encounter_pack_size}"
---

## Schema

An encounter lists its monsters (`monsters:`, two to four `{entities.monsters.<id>}`) and the pack distribution that decides how many wake (`spawn_roll:`). Every entry also carries the content-entity header (`spec`, `spec_version`, `file_type`, `id`, `status`, `last_verified`, `implemented_in`).

## Representative Example

`content/encounters/briny_alcove.yaml`:

```yaml
spec: game-design.md
spec_version: 0.3.0
file_type: content-entity
id: briny_alcove
status: draft
last_verified: "2026-04-18"
implemented_in: []
name: Briny Alcove
depth: 2
monsters:
  - "{entities.monsters.barrow_husk}"
  - "{entities.monsters.briny_lurker}"
  - "{entities.monsters.grave_lurker}"
spawn_roll: "{distributions.ossuary_pack}"
description: "Briny Alcove: a low room where the lantern throws long shadows."
```

## Balance Notes

Tuned against `{balance_targets.encounter_pack_size}` in `gdd/economy-balance.md`.
