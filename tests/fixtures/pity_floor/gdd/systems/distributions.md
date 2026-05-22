---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
distributions:
  test_dist:
    type: pity_floor
    table: [common, uncommon, rare, epic]
    weights: [0.6, 0.3, 0.08, 0.02]
    pity: { rare_within: 12, epic_within: 40 }
    seed: deterministic_per_run
    status: prototyped
    implemented_in: []
---

## Tokens

`{distributions.test_dist}` is a `pity_floor` distribution. The lint exercise here is: the loader accepts the type, the schema validates, the linter runs to completion without error.
