---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: cards
schema:
  required: [id, name, cost, type, rarity]
  properties:
    id:     { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:   { type: string }
    cost:   { type: integer, minimum: 0, maximum: 10 }
    type:   { enum: [creature, spell, enchantment, artifact] }
    rarity: { enum: [common, uncommon, rare, mythic] }
    power:  { type: integer, minimum: 0 }
    toughness: { type: integer, minimum: 0 }
    abilities: { type: array }
data_dir: ../../content/cards
count_target: 50
balance_refs:
  - "{balance_targets.cards_per_rarity}"
---

## Schema

Required: id, name, cost, type, rarity. Optional: power, toughness, abilities
(typically required for creatures, optional for spells/enchantments).

## Representative Example

See `content/cards/example_card.yaml`.
