---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-04-18"
entity: items
schema:
  required: [id, name, rarity, slot, weight, value]
  properties:
    id: { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name: { type: string, minLength: 1 }
    rarity: { enum: [worn, sound, gleaming, relic] }
    slot: { enum: [lantern, weapon, ward, trinket, tonic] }
    weight: { type: integer, minimum: 1 }
    value: { type: integer, minimum: 0 }
    grants: { type: string }
    description: { type: string }
data_dir: ../../content/items
count_target: 140
balance_refs:
  - "{balance_targets.items_per_rarity}"
---

## Schema

An item is a YAML object under `content/items/<id>.yaml` whose filename stem matches its `id`. `grants:` optionally names one skill (`{entities.skills.<id>}`) that the item teaches while carried. Every entry also carries the content-entity header (`spec`, `spec_version`, `file_type`, `id`, `status`, `last_verified`, `implemented_in`).

## Representative Example

`content/items/ashen_censer.yaml`:

```yaml
spec: game-design.md
spec_version: 0.3.0
file_type: content-entity
id: ashen_censer
status: draft
last_verified: "2026-04-18"
implemented_in: []
name: Ashen Censer
rarity: relic
slot: tonic
weight: 7
value: 167
grants: "{entities.skills.wick_cleave}"
description: A relic tonic stitched from moth-silk.
```

## Balance Notes

Tuned against `{balance_targets.items_per_rarity}` in `gdd/economy-balance.md`.
