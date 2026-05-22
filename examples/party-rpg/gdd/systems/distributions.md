---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
distributions:
  damage_roll:
    type: gaussian
    mean: 12
    stddev: 3
    clamp: [1, 99]
    seed: deterministic_per_run
    status: draft
    implemented_in: []
  critical_hit:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.12
    seed: deterministic_per_run
    status: draft
    implemented_in: []
  loot_rarity:
    type: pity_floor
    table: [common, uncommon, rare, epic, legendary]
    weights: [0.50, 0.30, 0.15, 0.04, 0.01]
    pity:
      rare_within:      6
      epic_within:      20
      legendary_within: 50
    seed: deterministic_per_run
    status: draft
    implemented_in: []
---

## Tokens

Three distributions. `{distributions.loot_rarity}` is the load-bearing one — its `pity_floor` shape is the design's promise from `{pillars}`.

## Rationale

**`damage_roll` is gaussian.** Mean 12, stddev 3, clamped to `[1, 99]`. The wider stddev (vs Lockstep's 1) gives more punch variance per hit, which Hollow Hold's longer turn cycles can absorb.

**`critical_hit` at 12%.** Uniform threshold roll. Slightly higher than Lockstep because Hollow Hold has fewer hits per battle, so the crit rate per-fight stays similar.

**`loot_rarity` is `pity_floor` — the design's keystone.**

The base weights `[0.50, 0.30, 0.15, 0.04, 0.01]` reflect a "real" rarity curve before pity kicks in. The pity counters guarantee:
- **`rare_within: 6`** — by the 6th drop without seeing rare-or-better, the 6th roll *forces* rare.
- **`epic_within: 20`** — by the 20th drop without seeing epic-or-better, the 20th roll forces epic.
- **`legendary_within: 50`** — by the 50th drop without seeing legendary, the 50th roll forces legendary.

A 20-floor quest produces 20 drops. The legendary pity at 50 means a player who's *been unlucky for 50 encounters* is guaranteed a legendary *on their next drop* — by floor 30 of the next quest. The math is intentional: pity creates patience without breaking the joy of natural drops.
