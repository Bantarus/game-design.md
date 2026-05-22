---
spec: game-design.md
spec_version: 0.1.1
file_type: content-schema
status: draft
last_verified: "2026-05-22"
entity: cards
schema:
  required: [id, name, mana_cost, archetype, type, effects]
  properties:
    id:        { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:      { type: string, minLength: 1 }
    mana_cost: { type: integer, minimum: 0, maximum: 10 }
    archetype: { enum: [spark, bulwark, veil, forge, neutral] }
    type:      { enum: [creature, spell, artifact] }
    power:     { type: integer, minimum: 0 }
    toughness: { type: integer, minimum: 0 }
    tags:      { type: array, items: { type: string } }
    effects:
      type: array
      minItems: 1
      items:
        type: object
        required: [kind]
        properties:
          kind:     { enum: [deal_damage, draw, summon, destroy, exile, gain_life] }
          amount:   { type: integer, minimum: 0 }
          target:   { enum: [opponent, self, any_creature, any_card] }
data_dir: ../../content/cards
count_target: 220
balance_refs:
  - "{balance_targets.win_rate_archetype_neutral}"
  - "{balance_targets.mana_per_turn}"
---

## Schema

A card is a YAML object under `content/cards/<id>.yaml`. Required: `id`, `name`, integer `mana_cost` (0-10), `archetype` (one of five), `type` (creature | spell | artifact), at least one effect.

Optional `power` / `toughness` for creatures. Both integers (no fractional combat stats — `{invariants.damage_is_integer}`).

## Representative Example

The canonical card is `content/cards/circuit_strike.yaml`:

```yaml
spec: game-design.md
spec_version: 0.1.1
file_type: content-entity
id: circuit_strike
status: draft
implemented_in: []
name: "Circuit Strike"
mana_cost: 2
archetype: spark
type: spell
tags: [burn, fast]
effects:
  - { kind: deal_damage, amount: 3, target: opponent }
```

## Balance Notes

220 designed cards across the four archetypes + neutral pool. The archetype mix targets matchup-pair balance via `{balance_targets.win_rate_archetype_neutral}` — the verify adapter must run 1000 matches per pair to catch outliers.

Card cost distribution targets `{balance_targets.mana_per_turn} = 4` as the average — too many high-cost cards in one archetype tilts the curve.
