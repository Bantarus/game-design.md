---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-04-18"
entity: skills
schema:
  required: [id, name, school, focus_cost, roll]
  properties:
    id: { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name: { type: string, minLength: 1 }
    school: { enum: [lumen, umbral, iron, brine] }
    focus_cost: { type: integer, minimum: 1 }
    roll: { type: string }
    inflicts: { type: string }
    description: { type: string }
data_dir: ../../content/skills
count_target: 90
balance_refs:
  - "{balance_targets.skill_focus_cost}"
---

## Schema

A skill names the distribution it rolls (`roll:`, a `{distributions.<id>}`) and optionally the affliction node it inflicts (`inflicts:`, a `{states.affliction.<node>}`). Every entry also carries the content-entity header (`spec`, `spec_version`, `file_type`, `id`, `status`, `last_verified`, `implemented_in`).

## Representative Example

`content/skills/ashen_chant.yaml`:

```yaml
spec: game-design.md
spec_version: 0.3.0
file_type: content-entity
id: ashen_chant
status: draft
last_verified: "2026-04-18"
implemented_in: []
name: Ashen Chant
school: brine
focus_cost: 1
roll: "{distributions.ossuary_dust_roll}"
inflicts: "{states.affliction.dazed}"
description: "A brine chant; it leaves frost on the caster's teeth."
```

## Balance Notes

Tuned against `{balance_targets.skill_focus_cost}` in `gdd/economy-balance.md`.
