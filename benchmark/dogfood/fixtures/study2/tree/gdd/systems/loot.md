---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: prototyped
last_verified: "2026-04-24"
implemented_in: ["impl/lanternfall/loot/**/*.py"]
rules:
  roll_drops:
    given:
      verb: "{verbs.loot_remains}"
    target_selection: explicit
    do:
      - for_each_drop_of: "{target.drops}"
        keep_one_in: 3
      - sample: "{distributions.drop_quality}"
        into: quality
    outputs: [items_dropped]
    status: prototyped
    implemented_in: ["impl/lanternfall/loot/drop_tables.py"]
  resolve_salvage:
    given:
      verb: "{verbs.salvage_gear}"
    target_selection: explicit
    do:
      - sample: "{distributions.salvage_yield}"
        into: coins
      - { credit: "{resources.grave_coin}", amount_from: coins }
    outputs: [gear_salvaged]
    status: prototyped
    implemented_in: ["impl/lanternfall/loot/salvage.py"]
---

## Tokens

Two rules. `roll_drops` walks a defeated monster's `drops:` list and keeps each entry on a one-in-three roll, then rolls its quality. `resolve_salvage` turns worn satchel gear into grave coin.

## Rationale

**Drops are a map.** A monster's `drops:` list is authored, not random: the randomness is only whether each listed item survives the fight and in what condition. Players who learn the lists learn where to hunt.

**One in three.** The keep odds are fixed at one in three for every monster. Tuning them per tier was tried and made bosses feel like loot piñatas.
