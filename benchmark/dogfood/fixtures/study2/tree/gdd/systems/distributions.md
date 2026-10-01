---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: prototyped
last_verified: "2026-04-24"
implemented_in: ["impl/lanternfall/rng/**/*.py", "impl/lanternfall/loot/drop_tables.py"]
distributions:
  ashveil_roll:
    type: discrete_sum
    samples: 2
    range: [1, 6]
    clamp: [2, 12]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  barrowchill_roll:
    type: gaussian
    mean: 8
    stddev: 2
    clamp: [1, 20]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  candlegrit_roll:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.35
    selection_rule: less_than
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  duskbite_roll:
    type: weighted
    options:
      graze: 50
      hit: 35
      crit: 15
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  fenmurk_roll:
    type: discrete_sum
    samples: 2
    range: [1, 6]
    clamp: [2, 12]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  gravetide_roll:
    type: gaussian
    mean: 8
    stddev: 2
    clamp: [1, 20]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  hollowknell_roll:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.35
    selection_rule: less_than
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  ironsap_roll:
    type: weighted
    options:
      graze: 50
      hit: 35
      crit: 15
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  lichwick_roll:
    type: discrete_sum
    samples: 2
    range: [1, 6]
    clamp: [2, 12]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  mothglow_roll:
    type: gaussian
    mean: 8
    stddev: 2
    clamp: [1, 20]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  nightbrine_roll:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.35
    selection_rule: less_than
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  ossuary_dust_roll:
    type: weighted
    options:
      graze: 50
      hit: 35
      crit: 15
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  palecoil_roll:
    type: discrete_sum
    samples: 2
    range: [1, 6]
    clamp: [2, 12]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  rustmire_roll:
    type: gaussian
    mean: 8
    stddev: 2
    clamp: [1, 20]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  sablegleam_roll:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.35
    selection_rule: less_than
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  tallowgrin_roll:
    type: weighted
    options:
      graze: 50
      hit: 35
      crit: 15
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/skill_rolls.py"]
  shallows_pack:
    type: weighted
    options:
      pair: 60
      trio: 35
      quartet: 5
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/packs.py"]
  gallery_pack:
    type: weighted
    options:
      pair: 45
      trio: 40
      quartet: 15
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/packs.py"]
  ossuary_pack:
    type: weighted
    options:
      pair: 30
      trio: 50
      quartet: 20
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/packs.py"]
  undercroft_pack:
    type: weighted
    options:
      pair: 25
      trio: 50
      quartet: 25
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/packs.py"]
  deepvault_pack:
    type: weighted
    options:
      pair: 15
      trio: 50
      quartet: 35
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/packs.py"]
  sanctum_pack:
    type: weighted
    options:
      pair: 0
      trio: 40
      quartet: 60
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/packs.py"]
  depth_band:
    type: weighted
    options:
      depth_1: 35
      depth_2: 30
      depth_3: 20
      depth_4: 15
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/depth_band.py"]
  drop_quality:
    type: weighted
    options:
      worn: 60
      sound: 30
      gleaming: 10
    selection_rule: declaration_order_first_above
    seed: deterministic_per_expedition
    status: prototyped
    implemented_in: ["impl/lanternfall/loot/drop_tables.py"]
  salvage_yield:
    type: discrete_sum
    samples: 2
    range: [1, 4]
    clamp: [2, 8]
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/salvage_yield.py"]
  strike_roll:
    type: discrete_sum
    samples: 3
    range: [1, 4]
    clamp: [3, 12]
    seed: deterministic_per_expedition
    status: prototyped
    implemented_in: ["impl/lanternfall/rng/tables.py"]
  flight_chance:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.6
    selection_rule: less_than
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/flight_chance.py"]
  wander_chance:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.15
    selection_rule: less_than
    seed: deterministic_per_expedition
    status: draft
    implemented_in: ["impl/lanternfall/rng/wander_chance.py"]
---

## Tokens

Every random outcome in Lanternfall resolves through one of these distributions. Sixteen are skill rolls (each skill's `roll:` names one), six are encounter packs (each encounter's `spawn_roll:`), and six serve the systems rules.

## Rationale

**Skill rolls come in four shapes.** Dice sums for steady damage, a clamped normal for heavy blows, a threshold roll for all-or-nothing effects, and a weighted graze/hit/crit table. A skill picks the shape that matches its fantasy; several skills share a roll.

**Packs grow with depth.** A pack roll decides how many of an encounter's monsters wake. The deeper packs weight toward quartets.

**Drop quality is shared with the loot code.** `drop_quality` is sampled inside `impl/lanternfall/loot/drop_tables.py`, so this file lists that module in its `implemented_in:` alongside the RNG package.

## Open Questions

- Whether the four shapes should be tuned per school. Currently the shape follows the skill, not the school.
