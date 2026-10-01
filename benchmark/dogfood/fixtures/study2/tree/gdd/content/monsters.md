---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-04-18"
entity: monsters
schema:
  required: [id, name, tier, max_vigor, skills, drops]
  properties:
    id: { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name: { type: string, minLength: 1 }
    tier: { enum: [minion, brute, elite, boss] }
    max_vigor: { type: integer, minimum: 1 }
    skills: { type: array, minItems: 1, maxItems: 2 }
    drops: { type: array, minItems: 1, maxItems: 3 }
    description: { type: string }
data_dir: ../../content/monsters
count_target: 60
balance_refs:
  - "{balance_targets.monster_vigor_curve}"
---

## Schema

A monster lists the skills it uses (`skills:`, one or two `{entities.skills.<id>}`) and the items it can drop (`drops:`, one to three `{entities.items.<id>}`). Every entry also carries the content-entity header (`spec`, `spec_version`, `file_type`, `id`, `status`, `last_verified`, `implemented_in`).

## Representative Example

`content/monsters/ashen_hound.yaml`:

```yaml
spec: game-design.md
spec_version: 0.3.0
file_type: content-entity
id: ashen_hound
status: draft
last_verified: "2026-04-18"
implemented_in: []
name: Ashen Hound
tier: brute
max_vigor: 28
skills:
  - "{entities.skills.fen_wail}"
  - "{entities.skills.yew_cleave}"
drops:
  - "{entities.items.rust_brand}"
description: A brute that gathers where the stairs turn.
```

## Balance Notes

Tuned against `{balance_targets.monster_vigor_curve}` in `gdd/economy-balance.md`.
