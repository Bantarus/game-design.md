---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/ember_ascent/balance/**/*.py"]
balance_targets:
  energy_per_turn:
    target: 3
    tolerance: [3, 3]
    measure: "fixed energy budget at start of each combat_turn (Normal difficulty)"
    status: draft
  win_rate_ascension_0:
    target: 0.55
    tolerance: [0.45, 0.65]
    measure: "win rate over 1000 monte-carlo runs at Ascension 0 (Normal)"
    status: draft
  average_run_length:
    target: "32 min"
    tolerance: ["22 min", "45 min"]
    measure: "median end-to-end run length, Ascension 0, real wall-clock"
    status: draft
  median_turns_per_combat:
    target: 6
    tolerance: [4, 8]
    measure: "median turns to clear a non-boss encounter, Ascension 0"
    status: draft
  average_combo_length:
    target: 2.4
    tolerance: [2.0, 3.2]
    measure: "average number of synergistic cards (sharing a tag) played per turn"
    status: draft
  cards_per_rarity:
    target: { common: 110, uncommon: 80, rare: 30 }
    tolerance: [{ common: 100, uncommon: 70, rare: 25 }, { common: 120, uncommon: 90, rare: 35 }]
    measure: "designed card count per rarity in content/cards/*.yaml"
    status: draft
  average_card_cost:
    target: 1.6
    tolerance: [1.3, 1.9]
    measure: "mean of cost: across all content/cards/*.yaml"
    status: draft
---

## Tokens

Seven balance targets. Each is referenced from at least one of: a `loop.balance_targets:`, a `resource.velocity_target:`, a content-schema `balance_refs:`, or a `verify_targets[].target` in `gdd/verification.md`. Any target that isn't referenced from somewhere fires `orphaned-entity` (warning).

## Rationale

`energy_per_turn` has `tolerance: [3, 3]` — a hard target, not a band. Changing the energy budget rebalances every card in the deck, so it's locked at 3.

`win_rate_ascension_0` is the headline metric. The tolerance band `[0.45, 0.65]` is wide because we want challenge without frustration; tightening to `[0.50, 0.60]` is a v0.5 goal. The verify adapter (`gdd/verification.md`) drives a 200-session sim against this target.

`average_run_length` is in human time (string, not minutes-int) because the spec allows it (`target:` is permissive); the linter accepts `["22 min", "45 min"]` as a pair of comparable strings via prose convention.

`cards_per_rarity` is a composite target: target is `{ common, uncommon, rare }`, tolerance is a `[low_obj, high_obj]` pair. The linter does not statically interpret composite targets in v0.1.1 — the project is expected to validate via verify.

## Open Questions

- Whether `average_card_cost` should be split per rarity (rare cards may sustain higher cost without breaking energy_per_turn). Currently flat. Re-evaluate after Act 3 content is balanced.
- Whether `median_turns_per_combat` and `average_combo_length` are actually independent or correlated to the point of being one target. Telemetry pending.
