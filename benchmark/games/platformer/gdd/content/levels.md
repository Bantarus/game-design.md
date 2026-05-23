---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-schema
status: draft
last_verified: "2026-05-23"
entity: levels
schema:
  required: [id, name, region, difficulty_tier, entry, exit, time_target_ms, checkpoints, platforms, ember_pickups, lethal_regions]
  properties:
    id:               { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:             { type: string, minLength: 1 }
    region:           { enum: [caverns, fault_lines, hot_springs, summit] }
    difficulty_tier:  { type: integer, minimum: 1, maximum: 5 }
    time_target_ms:   { type: integer, minimum: 60000, maximum: 600000 }
    entry:
      type: object
      required: [x, y]
      properties:
        x: { type: integer }
        y: { type: integer }
    exit:
      type: object
      required: [x, y]
      properties:
        x: { type: integer }
        y: { type: integer }
    checkpoints:
      type: array
      minItems: 1
      maxItems: 5
      items:
        type: object
        required: [x, y]
        properties:
          x: { type: integer }
          y: { type: integer }
    platforms:
      type: array
      minItems: 1
      items:
        type: object
        required: [x, y, width, height]
        properties:
          x:       { type: integer }
          y:       { type: integer }
          width:   { type: integer, minimum: 1 }
          height:  { type: integer, minimum: 1 }
          surface: { enum: [solid, one_way] }
    ember_pickups:
      type: array
      items:
        type: object
        required: [x, y, ember_value]
        properties:
          x:           { type: integer }
          y:           { type: integer }
          ember_value: { type: integer, minimum: 1, maximum: 4 }
    lethal_regions:
      type: array
      items:
        type: object
        required: [x, y, width, height, tag]
        properties:
          x:      { type: integer }
          y:      { type: integer }
          width:  { type: integer, minimum: 1 }
          height: { type: integer, minimum: 1 }
          tag:    { enum: [lava, spike, void, crusher] }
    notes:      { type: string }
data_dir: ../../content/levels
count_target: 40
balance_refs:
  - "{balance_targets.levels_per_region}"
  - "{balance_targets.median_deaths_per_level}"
  - "{balance_targets.median_time_to_complete_level}"
---

## Schema

A level is a YAML object under `content/levels/<id>.yaml` whose filename stem matches its `id`. The schema (frontmatter `schema:`) is JSON-Schema-shaped: `required` lists the required keys; `properties` declares per-key constraints.

Positions (`entry`, `exit`, `checkpoints[*]`, `ember_pickups[*]`, `lethal_regions[*]`, `platforms[*]`) are integer coordinates in micro_units — the fixed-point unit declared by `{invariants.fixed_point_simulation_state}`. The coordinate system origin is the level's bottom-left; +x is east, +y is up. A level's playable region is implicitly the bounding box of all declared positions; geometry outside that box is not simulated.

`platforms` is the level's *passable geometry* — the rectangles the moth lands on. Each is an axis-aligned bounding box at `(x, y)` with `(width, height)` in micro_units, plus an optional `surface` tag (`solid` = collides from all six sides, the default; `one_way` = collides only from above, the moth can jump up through it from below). A level's platforms are what makes the cave traversable; a level with no platforms is unplayable (`minItems: 1`).

`lethal_regions` is a list of axis-aligned bounding boxes the moth dies on contact with. Four tags are legal: `lava` (animated, in the caverns/fault_lines/hot_springs visual sets), `spike` (static, all regions), `void` (an off-level death — falling into space below the playable region, no visual but lethal on contact), `crusher` (timed-cycle obstacles in hot_springs and summit). The tag drives presentation only; all four are equally lethal at simulation level (single hit, instant respawn).

The level schema is intentionally complete: an agent given the schema plus one representative entity below should be able to author a new playable level *entirely from the schema* — every rectangle, every position, every value the moth's simulation needs. There is no opaque "layout file" pointer; the schema describes the level fully.

## Representative Example

The canonical level is `content/levels/caverns_01_first_breath.yaml`:

```yaml
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: caverns_01_first_breath
status: draft
implemented_in: ["src/embergrave/levels/caverns_01_first_breath.py"]
name: "First Breath"
region: caverns
difficulty_tier: 1
time_target_ms: 90000
entry:  { x: 1000,  y: 1500 }
exit:   { x: 12000, y: 1500 }
checkpoints:
  - { x: 4000, y: 1500 }
  - { x: 8000, y: 1500 }
platforms:
  - { x: 500,   y: 1000, width: 2500, height: 200, surface: solid }
  - { x: 3500,  y: 1000, width: 2000, height: 200, surface: solid }
  - { x: 6000,  y: 1000, width: 2500, height: 200, surface: solid }
  - { x: 9000,  y: 1000, width: 3500, height: 200, surface: solid }
ember_pickups:
  - { x: 3000, y: 1800, ember_value: 1 }
  - { x: 5500, y: 2500, ember_value: 1 }
  - { x: 9000, y: 2100, ember_value: 2 }
lethal_regions:
  - { x: 0, y: 0, width: 13000, height: 200, tag: void }
notes: "Tutorial level. Four solid platforms with small gaps the player jumps across; the gaps between platforms are over the void floor, which is the only lethal region. Two checkpoints (at the second and third platform). Three ember pickups demonstrate the resource without making it scarce. Tier 1: 0-4 deaths is the acceptable balance band."
```

This level is the *unit test* for the schema: from it alone, an agent should be able to implement a new level of similar shape (e.g. a new tier-1 caverns level, or a new tier-3 fault_lines level by extrapolating tier/region differences from the design intent) without further reference. The level is *completely described* by the schema — there is no opaque external file the agent needs to author. If that fails, the schema is under-specified — surface the gap rather than work around it (see §11.1 of `docs/spec.md`).

## Balance Notes

The 40 designed levels target the distribution `levels_per_region = { caverns: 8, fault_lines: 10, hot_springs: 12, summit: 10 }` (with tolerance, see `{balance_targets.levels_per_region}`). Median deaths per level per tier follow `{balance_targets.median_deaths_per_level}`; the time targets per level follow `{balance_targets.median_time_to_complete_level}`.

Checkpoints (`minItems: 1`) — every level has at least one checkpoint. A level with one checkpoint means the player only respawns at the level entry (the first checkpoint is implicitly the entry position itself, conventionally). A level with five checkpoints means the level is long, and the player gets a fresh respawn ~every 30 seconds of clean play.

Ember pickups (no `minItems`) — a level may have zero ember pickups if it is designed for ember-conservative play (no glide, minimal dash). Tier-5 levels in the summit region are designed for low ember-pickup counts to force a tight ember economy.

Lethal regions (no `minItems`) — a level may have zero declared lethal regions if all death-on-contact is encoded in the `layout_ref` geometry. A level should typically declare at least one `void` lethal region for the bottom-of-level out-of-bounds, but tutorial levels with closed geometry can omit this.

## Open Questions

- Whether to introduce a `secret_ember_pickups:` array as a sibling to `ember_pickups:`, for the discoverable hidden-route collectibles. Argument for: encodes the "discovery" secondary aesthetic. Argument against: the schema can already represent them as `ember_pickups` with `ember_value: 4` placed in a hidden location. Currently no; revisit if discoverability becomes a v0.5 design goal.
- Whether to support per-level `pillars_override:` (a level that emphasizes a specific pillar more than others). Currently no — pillars are immutable per-project; per-level emphasis is encoded in the geometry, not in the schema.
- Whether `lethal_regions[*].tag` should drive *simulation* behavior (e.g. `crusher` having a movement pattern). Currently no — all four are equally lethal at simulation; the tag is presentation. If `crusher` needs a movement cycle, that would extend the schema with a `crusher_cycles:` array (or similar) declaring movement period and amplitude — explicitly *in* the schema, not in an opaque external file.
