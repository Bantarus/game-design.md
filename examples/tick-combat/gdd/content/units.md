---
spec: game-design.md
spec_version: 0.1.1
file_type: content-schema
status: draft
last_verified: "2026-05-22"
entity: units
schema:
  required: [id, name, hp, attack, speed, role]
  properties:
    id:     { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:   { type: string, minLength: 1 }
    hp:     { type: integer, minimum: 1,  maximum: 200 }
    attack: { type: integer, minimum: 0,  maximum: 50 }
    speed:  { type: integer, minimum: 1,  maximum: 10 }
    role:   { enum: [tank_melee, ranged_dps, support, hybrid] }
    cost:   { type: integer, minimum: 0,  maximum: 10 }
    tags:   { type: array, items: { type: string } }
data_dir: ../../content/units
count_target: 24
balance_refs:
  - "{balance_targets.average_team_dps}"
---

## Schema

A unit is a YAML object under `content/units/<id>.yaml`. Required fields: `id`, `name`, integer `hp`, integer `attack`, integer `speed` (1–10), `role`. Optional: `cost` (gold to deploy), `tags`.

Integer constraints serve `{invariants.damage_is_integer}` — there's no path to fractional unit stats.

## Representative Example

The canonical unit is `content/units/volt_marine.yaml`:

```yaml
spec: game-design.md
spec_version: 0.1.1
file_type: content-entity
id: volt_marine
status: draft
implemented_in: []
name: "Volt Marine"
hp: 20
attack: 5
speed: 7
role: ranged_dps
cost: 3
tags: [common, ranged]
```

## Balance Notes

24 designed units. The `speed` field drives `{distributions.action_order}` — a unit with `speed: 10` always acts before `speed: 7` in the deterministic ordering, breaking ties by deployment order.

`{balance_targets.average_team_dps}` is computed across a hand-picked "balanced roster" of 5 units (one tank, one ranged DPS, one support, one hybrid, and one wildcard) — not across all 24 units uniformly.
