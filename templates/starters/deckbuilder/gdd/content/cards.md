---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-28"
entity: cards
schema:
  required: [id, name, cost, type, rarity, effects]
  properties:
    id:      { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:    { type: string }
    cost:    { type: integer, minimum: 0, maximum: 5 }
    type:    { enum: [attack, skill, power] }
    rarity:  { enum: [common, uncommon, rare] }
    effects: { type: array }
data_dir: ../../content/cards
count_target: 30
balance_refs:
  - "{balance_targets.cards_per_rarity}"
---

## Schema

Six required fields per card: `id` (slug), `name` (display string), `cost`
(0-5 energy), `type` (attack / skill / power), `rarity`, and `effects` (array
of effect objects).

## Representative Example

See `content/cards/example_card.yaml` for the starter's example. When you
author new cards, mirror that shape: each effect inside `effects:` is an
object with a `kind:` discriminator + kind-specific fields.

## Balance Notes

`cards_per_rarity` in `gdd/economy-balance.md` declares the designed count
per rarity. Mismatches surface in `gdmd diff` once you ship a release.
