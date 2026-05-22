---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-schema
status: draft
last_verified: "2026-05-21"
entity: cards
schema:
  required: [id, name, cost, type, rarity, effects]
  properties:
    id:      { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:    { type: string, minLength: 1 }
    cost:    { type: integer, minimum: 0, maximum: 3 }
    type:    { enum: [attack, skill, power] }
    rarity:  { enum: [common, uncommon, rare] }
    tags:    { type: array, items: { type: string } }
    effects:
      type: array
      minItems: 1
      items:
        type: object
        required: [kind]
        properties:
          kind:         { enum: [damage, apply_state, gain_block, draw_cards, exhaust_self, scale_burning] }
          amount:       { type: integer, minimum: 0 }
          distribution: { type: string, pattern: "^\\{distributions\\.[a-z0-9_]+\\}$" }
          state:        { type: string, pattern: "^\\{states\\.[a-z0-9_]+\\.[a-z0-9_]+\\}$" }
          duration:     { type: integer, minimum: 1 }
          stacks:       { type: integer, minimum: 1 }
          count:        { type: integer, minimum: 1 }
data_dir: ../../content/cards
count_target: 220
balance_refs:
  - "{balance_targets.cards_per_rarity}"
  - "{balance_targets.average_card_cost}"
---

## Schema

A card is a YAML object under `content/cards/<id>.yaml` whose filename stem matches its `id`. The schema (frontmatter `schema:`) is JSON-Schema-shaped: `required` lists the required keys; `properties` declares per-key constraints. `effects:` is an array of typed operation objects — `kind` is the discriminator.

Six `kind` values are legal in v0.1.1: `damage`, `apply_state`, `gain_block`, `draw_cards`, `exhaust_self`, `scale_burning`. Any `damage` effect must reference a `distribution:` (see `{invariants.damage_is_integer}` — gaussian damage must round at apply time). Any `apply_state` effect must reference a `state:` of the form `{states.<machine>.<node>}`.

## Representative Example

The canonical card is `content/cards/ember_strike.yaml`:

```yaml
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: ember_strike
status: draft
implemented_in: ["src/ember_ascent/cards/ember_strike.py"]
name: "Ember Strike"
cost: 1
type: attack
rarity: common
tags: [attack, fire]
effects:
  - kind: damage
    amount: 6
    distribution: "{distributions.damage_roll}"
  - kind: apply_state
    state: "{states.enemy_lifecycle.burning}"
    duration: 2
    stacks: 1
```

This card is the *unit test* for the schema: from it alone, an agent should be able to implement a new card of similar shape without further reference. If that fails, the schema is under-specified — surface the gap rather than work around it (see §11.1 of `docs/spec.md`).

## Balance Notes

The 220 designed cards target the distribution `cards_per_rarity = { common: 110, uncommon: 80, rare: 30 }` (with tolerance, see `{balance_targets.cards_per_rarity}`). Mean `cost` across the set targets `{balance_targets.average_card_cost} = 1.6`.

Cards with `kind: scale_burning` are the *bellow* category from `{pillars}`; they intentionally do not declare a fixed damage amount because their value is `burn_stacks × multiplier` at apply time.
