---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
invariants:
  damage_is_integer:
    kind: numeric_domain
    rule: "All damage, hp, mp, and gold quantities resolve to integers. Continuous distributions clamp and round at apply."
    applies_to:
      - "{resources.hp}"
      - "{resources.mp}"
      - "{resources.gold}"
      - "{rules.action_resolution}"
    enforcement: lint
    severity: error
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed, the pity_floor draw sequence is reproducible. Two runs with the same seed see the same drops in the same order."
    applies_to:
      - "{distributions.damage_roll}"
      - "{distributions.critical_hit}"
      - "{distributions.loot_rarity}"
    enforcement: verify
    severity: error
  loot_pity_is_load_bearing:
    kind: architectural_pattern
    rule: "The pity_floor counters on {distributions.loot_rarity} persist across encounters within a quest. A counter MUST NOT reset when the player exits to the menu or restarts a battle."
    applies_to:
      - "{distributions.loot_rarity}"
      - "{rules.loot_resolution}"
    enforcement: advisory
    severity: warning
---

## Tokens

Three invariants. `damage_is_integer` is lint-checkable; `deterministic_given_seed` is verify-time; `loot_pity_is_load_bearing` is advisory.

## Rationale

### damage_is_integer

The numeric_domain check scans `content/items/*.yaml` for any `effects[].amount` that isn't an integer. Items that grant flat damage, flat healing, or flat resource boosts must declare integer amounts.

**Why:** Hollow Hold's UI shows integer damage; player trust in the math depends on the displayed number matching the applied number.

### deterministic_given_seed

The pity_floor distribution is *stateful* — a counter tracks "how many drops since last rare." For determinism, that counter must be seeded reproducibly and incremented in a fixed order. The verify adapter (when written) re-runs the same quest and asserts the same loot drops at the same encounter indices.

**Why:** without this, "share a seed with a friend" is a feature that lies. With it, Hollow Hold inherits Lockstep's replay-share property for free.

### loot_pity_is_load_bearing

Advisory because no clean static check exists for "the pity counter persists across encounters." The reminder lives here for code review; the verify adapter is the real enforcement.

**Why:** v0.0.1 internal had a regression where save-and-quit reset the pity counter, letting players grind it. The invariant exists to prevent that class of bug.
