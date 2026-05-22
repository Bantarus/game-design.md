---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-schema
status: draft
last_verified: "2026-05-22"
entity: encounters
schema:
  required: [id, name, enemy_units]
  properties:
    id:
      type: string
      pattern: "^[a-z][a-z0-9_]*$"
    name:
      type: string
      minLength: 1
    seed_offset:
      type: integer
      minimum: 0
    enemy_units:
      type: array
      minItems: 1
      maxItems: 5
      items:
        type: object
        required: [unit_id, deploy_order]
        properties:
          unit_id:      { type: string, pattern: "^[a-z][a-z0-9_]*$" }
          deploy_order: { type: integer, minimum: 0, maximum: 4 }
        additionalProperties: false
    twist:
      type: object
      description: "Optional rule modifiers active for this encounter."
data_dir: ../../content/encounters
count_target: 12
---

## Schema

An encounter is a YAML object at `content/encounters/<id>.yaml`. Required
fields: `id`, `name`, `enemy_units` (array of 1–5 unit references). Optional
fields: `seed_offset` (default 0; shifts the encounter PRNG without changing
the campaign-level seed), `twist` (free-form rule modifier object).

Each entry under `enemy_units:` references a unit declared in
`content/units/*.yaml` by id, with a `deploy_order` in `[0, 4]`. This is
how an encounter declares "the enemy squad" — the resolution of v0.2 Phase-2
ambiguity #7.

## Representative Example

The canonical first encounter is `content/encounters/shock_canyon_01.yaml`:

```yaml
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: shock_canyon_01
status: draft
implemented_in: []
name: "Shock Canyon (encounter 1)"
seed_offset: 0
enemy_units:
  - { unit_id: volt_marine, deploy_order: 0 }
  - { unit_id: shock_titan, deploy_order: 1 }
```

## Balance Notes

Twelve designed encounters scale roughly linearly in difficulty across the
campaign. Each encounter's enemy squad is hand-picked; `seed_offset` lets
two encounters share the same campaign seed but produce different per-tick
trajectories. The harness composes a campaign from a fixed ordered list of
encounters; the player faces them in sequence.

## Open Questions

- Whether the `twist:` field deserves a typed vocabulary (e.g., enum of
  named modifiers) rather than its current free-form object. Defer until at
  least two encounters use it.
- Whether to declare formation hints (`enemy_formation: ...`) per encounter
  or leave deployment to the AI side as deterministic from the unit list.
