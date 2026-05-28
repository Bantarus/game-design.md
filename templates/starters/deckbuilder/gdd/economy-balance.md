---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/balance/**/*.py"]
balance_targets:
  energy_per_turn:
    target_kind: scalar
    target: 3
    tolerance: [3, 3]
    measure: "fixed energy budget at start of each combat_turn"
    status: draft
  win_rate_normal:
    target_kind: scalar
    target: 0.55
    tolerance: [0.45, 0.65]
    measure: "win rate over 1000 monte-carlo runs at Normal difficulty"
    status: draft
  average_run_length:
    target_kind: range
    target: { near: 30, tolerance: 10 }
    measure: "median end-to-end run length in minutes, Normal difficulty"
    status: draft
  cards_per_rarity:
    target_kind: distribution_over_categories
    target:    { common: 18, uncommon: 9, rare: 3 }
    tolerance: { common: 3,  uncommon: 2, rare: 1 }
    measure: "designed card count per rarity at ship"
    status: draft
---

## Tokens

Four balance targets, demonstrating each `target_kind` (D-003): `scalar`
(energy_per_turn, win_rate_normal), `range` (average_run_length), and
`distribution_over_categories` (cards_per_rarity).

## Rationale

**`energy_per_turn = 3`** is the load-bearing constraint that shapes every
deckbuilder card design — your cards' costs are calibrated against this. If
your design needs a different value, change this AND audit the per-card costs.

**`win_rate_normal = 0.55`** is a classic "challenging but fair" target. If
your game targets a different difficulty curve, adjust the target AND the
tolerance band; the linter doesn't enforce target values, but `gdmd diff` will
flag regressions if the value drifts outside the previous tolerance band.

**`cards_per_rarity`** demonstrates the distribution-over-categories shape;
tune the target counts to match your designed scope.

The `gdmd diff` command flags any `balance_targets.<id>.target` that moved
outside its previous `tolerance:` band as a `balance_regression` (exit code 1).
Treat regressions as blockers, not warnings.
