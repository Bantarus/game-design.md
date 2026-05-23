---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-schema
status: draft
last_verified: "2026-05-23"
entity: recipes
schema:
  required: [id, name, tier, inputs, output]
  properties:
    id:        { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:      { type: string }
    tier:      { type: integer, minimum: 0, maximum: 4 }
    inputs:
      type: array
      items:
        type: object
        required: [item, quantity]
        properties:
          item:     { type: string, pattern: "^[a-z][a-z0-9_]*$" }
          quantity: { type: integer, minimum: 1 }
    output:
      type: object
      required: [item, quantity]
      properties:
        item:     { type: string, pattern: "^[a-z][a-z0-9_]*$" }
        quantity: { type: integer, minimum: 1 }
        tag:      { enum: [food, drink, tool, station, material, win] }
        starting_durability: { type: integer, minimum: 1 }
        hunger_restore_value: { type: integer, minimum: 0 }
    station_required: { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    tool_required:    { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    in_game_minutes_to_craft: { type: integer, minimum: 0 }
data_dir: ../../content/recipes
count_target: 12
balance_refs:
  - "{balance_targets.pyre_input_total}"
---

## Schema

A recipe is an immutable (inputs → output) transformation. All recipes have:

- `id`: stable lowercase identifier; matches the filename stem in `content/recipes/<id>.yaml`.
- `name`: human-readable, used in UI panel text.
- `tier`: 0 (no tool) → 1 (knife) → 2 (wooden axe) → 3 (pickaxe) → 4 (signal pyre — special). Tier governs which prior tool/station is implied as a prerequisite.
- `inputs`: array of `{ item, quantity }` pairs; all must be present in the player's inventory at craft time.
- `output`: single `{ item, quantity, tag }` with optional `starting_durability` (for tools), `hunger_restore_value` (for food items). The `tag` field categorizes the output for UI filtering and for verb routing (`verbs.eat` accepts items with `tag: food`, etc.).
- `station_required` (optional): the station kind (`campfire`, `sawhorse`, `still`) the player must be adjacent to. Tier-2+ recipes typically require one.
- `tool_required` (optional): the tool the player must have in inventory (with remaining durability > 0). Tier-1+ recipes typically require the knife or higher.
- `in_game_minutes_to_craft`: the action's `time_cost`. Defaults to 60 if not specified; some recipes are fast (rope is 30; pyre layers are 90).

Recipes are immutable at runtime — see the `recipe_data_immutable_at_runtime` invariant in `gdd/architecture-invariants.md` (Act 3). They are bundled with the game; new recipes are added by writing new YAML files in `content/recipes/` between releases, not at runtime.

## Representative Example

The wooden axe is the canonical tier-1 tool — it appears early in every run and gates access to all higher tiers:

```yaml
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: wooden_axe
status: draft
implemented_in: ["src/driftwood/content/recipes/wooden_axe.py"]
name: "Wooden Axe"
tier: 1
inputs:
  - { item: wood,        quantity: 3 }
  - { item: fiber_rope,  quantity: 1 }
output:
  item: wooden_axe
  quantity: 1
  tag: tool
  starting_durability: 12
tool_required: belt_knife
in_game_minutes_to_craft: 60
```

This says: at the player's camp (no station required), with the starting belt knife in inventory, consume 3 wood + 1 fiber_rope to produce 1 wooden_axe with 12 remaining uses. The craft action takes 1 in-game hour.

## Balance Notes

The recipe tree's total material cost for the signal pyre is the load-bearing balance target — see `{balance_targets.pyre_input_total}`. Each recipe's contribution to that total is summed across the tree; a recipe with bloated inputs (e.g., 8 wood for a single plank) would push the total past the gather budget the brief implies. The 12-recipe count is the v0.1 commitment; the recipe tree is shallow enough that a designer can hold the whole tree in mind while authoring.

## Open Questions

- Whether to introduce a `recipe_unlock_condition` field for recipes that should appear in the panel only after certain conditions (e.g., the still recipe only unlocks after the player has built the campfire). Currently no — the brief says "all recipes shown from the start" — but a future v2 of the game might want a slower-drip discovery for a "newcomer tutorial mode."
- Whether the `tool_required` field should accept a *list* (any of) or a single item (current). v0.1 single; revisit if a recipe naturally accepts multiple equivalent tools.
