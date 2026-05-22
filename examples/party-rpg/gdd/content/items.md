---
spec: game-design.md
spec_version: 0.1.1
file_type: content-schema
status: draft
last_verified: "2026-05-22"
entity: items
schema:
  required: [id, name, rarity, slot, effects]
  properties:
    id:     { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:   { type: string, minLength: 1 }
    rarity: { enum: [common, uncommon, rare, epic, legendary] }
    slot:   { enum: [weapon, armor, trinket, consumable] }
    tags:   { type: array, items: { type: string } }
    effects:
      type: array
      minItems: 1
      items:
        type: object
        required: [kind]
        properties:
          kind:   { enum: [damage, heal, gain_mp, apply_buff, revive, gain_gold] }
          amount: { type: integer, minimum: 0 }
          target: { enum: [self, ally, enemy, party] }
          duration: { type: integer, minimum: 1 }
data_dir: ../../content/items
count_target: 50
balance_refs:
  - "{balance_targets.legendary_drops_per_quest}"
  - "{balance_targets.gold_per_quest}"
---

## Schema

An item is a YAML object under `content/items/<id>.yaml` whose filename matches its `id`. Required: `id`, `name`, `rarity` (one of five buckets), `slot` (weapon/armor/trinket/consumable), `effects` (one or more typed operations).

Six effect kinds in v0.1: `damage`, `heal`, `gain_mp`, `apply_buff`, `revive`, `gain_gold`. Numeric `amount:` is always integer per `{invariants.damage_is_integer}`.

## Representative Example

The canonical item is `content/items/ember_blade.yaml`:

```yaml
spec: game-design.md
spec_version: 0.1.1
file_type: content-entity
id: ember_blade
status: draft
implemented_in: []
name: "Ember Blade"
rarity: rare
slot: weapon
tags: [weapon, fire]
effects:
  - { kind: damage, amount: 14, target: enemy }
  - { kind: apply_buff, target: self, duration: 3 }
```

## Balance Notes

50 designed items, distributed roughly per the base weights of `{distributions.loot_rarity}` adjusted for design pressure (rare/epic/legendary items get more design attention per item to support pity-floor expectations).

`{balance_targets.legendary_drops_per_quest} = 0.4` means a player sees ~1 legendary every 2-3 quests. The 5 legendary items in the pool need to feel distinct enough that running into the same one twice still feels like a celebration.
