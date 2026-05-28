---
spec: game-design.md
spec_version: 0.3.0
file_type: content-schema
status: draft
last_verified: "2026-05-21"
entity: enemies
schema:
  required: [id, name, max_hp, intents]
  properties:
    id:     { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:   { type: string, minLength: 1 }
    max_hp: { type: integer, minimum: 1 }
    act:    { type: integer, minimum: 1, maximum: 3 }
    tags:   { type: array, items: { type: string } }
    intents:
      type: array
      minItems: 1
      items:
        type: object
        required: [kind]
        properties:
          kind:        { enum: [attack, defend, buff, debuff, ramp] }
          damage:      { type: integer, minimum: 0 }
          block:       { type: integer, minimum: 0 }
          targets_burn:{ type: boolean }
data_dir: ../../content/enemies
count_target: 30
balance_refs:
  - "{balance_targets.median_turns_per_combat}"
---

## Schema

An enemy is a YAML object under `content/enemies/<id>.yaml` whose filename stem matches its `id`. Required: `id`, `name`, `max_hp` (integer per `{invariants.damage_is_integer}`), `intents` (the action set the enemy telegraphs each turn). Optional: `act` (which act the enemy belongs to, 1–3) and `tags` (free-form).

Intents are pre-shown to the player ("intent telegraphing" in `{loops.encounter.intended_dynamics}`). The five legal intent kinds in v0.1.1: `attack`, `defend`, `buff`, `debuff`, `ramp`. An enemy may declare any number of intents; the runtime cycles or weights them via per-enemy logic (out of scope for the schema).

## Representative Example

The canonical enemy is `content/enemies/kindling_imp.yaml`:

```yaml
spec: game-design.md
spec_version: 0.3.0
file_type: content-entity
id: kindling_imp
status: draft
implemented_in: ["src/ember_ascent/enemies/kindling_imp.py"]
name: "Kindling Imp"
act: 1
max_hp: 14
tags: [act_1, common]
intents:
  - { kind: attack,  damage: 5 }
  - { kind: defend,  block: 4 }
  - { kind: debuff, targets_burn: true }
```

## Balance Notes

The 30 designed enemies are weighted toward Act 1 (12 enemies) > Act 2 (12) > Act 3 (6 including the boss). Bosses do *not* live in `enemies/`; they live in `enemies/` but are tagged `tags: [boss]` and reference an extended intent format (the `magma_drake` example shows the v0.1.1 minimum). `{balance_targets.median_turns_per_combat}` is computed across non-boss enemies only.
