---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/balance/**/*.py"]
balance_targets:
  average_turns_per_match:
    target_kind: range
    target: { near: 10, tolerance: 4 }
    measure: "median turns per match across mirror and varied matchups"
    status: draft
  win_rate_mirror_match:
    target_kind: scalar
    target: 0.50
    tolerance: [0.45, 0.55]
    measure: "in mirror matches, neither side has a structural advantage"
    status: draft
  cards_per_rarity:
    target_kind: distribution_over_categories
    target:    { common: 30, uncommon: 15, rare: 5 }
    tolerance: { common: 5,  uncommon: 3,  rare: 2 }
    measure: "designed card count per rarity"
    status: draft
---

## Tokens

Three balance targets. `win_rate_mirror_match` at 0.50 is the structural
fairness check; the others are pacing and content-scope targets.
