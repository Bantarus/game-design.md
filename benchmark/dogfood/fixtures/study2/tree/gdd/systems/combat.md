---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: prototyped
last_verified: "2026-04-24"
implemented_in: ["impl/lanternfall/combat/**/*.py"]
rules:
  resolve_strike:
    given:
      verb: "{verbs.strike_foe}"
    target_selection: explicit
    do:
      - sample: "{distributions.strike_roll}"
        plus: "{actor.might}"
      - apply_damage_to: "{target.max_vigor}"
    outputs: [damage_dealt]
    status: prototyped
    implemented_in: ["impl/lanternfall/combat/strike.py"]
  resolve_skill:
    given:
      verb: "{verbs.invoke_skill}"
    target_selection: explicit
    do:
      - { spend: "{resources.ward_focus}", amount_from: "{target.focus_cost}" }
      - roll_via: "{target.roll}"
      - inflict_if_present: "{target.inflicts}"
    outputs: [skill_resolved]
    status: draft
    implemented_in: ["impl/lanternfall/combat/skills.py"]
  apply_relic:
    given:
      verb: "{verbs.use_relic}"
    target_selection: explicit
    do:
      - field: charges
        decrement: 1
      - { restore: "{resources.vigor}", amount: 6 }
    outputs: [relic_used]
    status: draft
    implemented_in: ["impl/lanternfall/combat/relics.py"]
  resolve_flight:
    given:
      verb: "{verbs.flee_upward}"
    target_selection: none
    do:
      - sample: "{distributions.flight_chance}"
        into: escaped
      - { on_failure_spend: "{resources.vigor}", amount: 5 }
    outputs: [flight_resolved]
    status: draft
    implemented_in: ["impl/lanternfall/combat/flight.py"]
  affliction_tick:
    given:
      driver: "{clocks.lantern_burn}"
    target_selection: self
    do:
      - { for_each_in: "{states.affliction}" }
      - { damage_while: "{states.affliction.bleeding}", amount: 1 }
    outputs: [affliction_ticked]
    status: draft
    implemented_in: ["impl/lanternfall/combat/afflictions.py"]
---

## Tokens

Five rules: strikes, skills, relics, flight and the affliction tick. Only `resolve_strike` has code so far.

## Rationale

**Skills read their own content.** `resolve_skill` spends the skill's `focus_cost`, rolls its `roll:` and applies its `inflicts:` node, all bound from the targeted skill at apply time. The rule itself names no skill.

**Afflictions tick on oil, not turns.** Bleeding costs vigor each time the lantern clock advances, so a wounded lamplighter who dawdles bleeds more.
