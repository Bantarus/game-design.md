---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-04-18"
implemented_in: ["impl/lanternfall/balance/**/*.py"]
balance_targets:
  oil_per_floor:
    target_kind: scalar
    target: 18
    tolerance: [14, 22]
    measure: median oil burned per floor sweep, depth 1-4
    status: draft
  coin_per_expedition:
    target_kind: scalar
    target: 240
    tolerance: [180, 320]
    measure: median grave coin banked per expedition
    status: draft
  turns_per_fight:
    target_kind: range
    target: { near: 5, tolerance: 2 }
    measure: median delve turns to clear a non-boss encounter
    status: draft
  expedition_length:
    target_kind: scalar
    target: "45 min"
    tolerance: ["35 min", "60 min"]
    measure: median wall-clock length of an expedition
    status: draft
  clear_rate:
    target_kind: scalar
    target: 0.4
    tolerance: [0.3, 0.5]
    measure: share of expeditions that clear the sanctum
    status: draft
  items_per_rarity:
    target_kind: distribution_over_categories
    target: { worn: 70, sound: 42, gleaming: 21, relic: 7 }
    tolerance: { worn: 10, sound: 8, gleaming: 5, relic: 3 }
    measure: designed item count per rarity in content/items/
    status: draft
  skill_focus_cost:
    target_kind: scalar
    target: 3.5
    tolerance: [2.5, 4.5]
    measure: mean focus_cost across content/skills/
    status: draft
  monster_vigor_curve:
    target_kind: range
    target: { between: [10, 60] }
    measure: max_vigor of non-boss monsters
    status: draft
  encounter_pack_size:
    target_kind: range
    target: { near: 3, tolerance: 1 }
    measure: monsters listed per encounter
    status: draft
---

## Tokens

Nine balance targets: five on the loops and resources, four on the content collections (referenced from each content-schema's `balance_refs:`).

## Rationale

**Oil per floor is the headline.** At 18 oil a floor and 120 oil a lantern, an unrefilled expedition sees about six floors. Everything else is tuned so that the sixth floor is where the sanctum becomes reachable.
