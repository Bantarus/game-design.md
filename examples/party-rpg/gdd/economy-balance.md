---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
balance_targets:
  median_battle_turns:
    target_kind: scalar
    target: 12
    tolerance: [8, 18]
    measure: "median turns from start_battle to claim_loot, over 1000 monte-carlo descents"
    status: draft
  win_rate_neutral_party:
    target_kind: scalar
    target: 0.65
    tolerance: [0.55, 0.75]
    measure: "win rate of the canonical four-character party over 1000 quests at Normal difficulty"
    status: draft
  gold_per_quest:
    target_kind: scalar
    target: 800
    tolerance: [600, 1100]
    measure: "expected gold from one full descent at Normal difficulty"
    status: draft
  legendary_drops_per_quest:
    target_kind: scalar
    target: 0.4
    tolerance: [0.2, 0.6]
    measure: "expected number of legendary-rarity items per descent, accounting for pity"
    status: draft
  average_quest_length:
    target_kind: scalar
    target: "25 min"
    tolerance: ["18 min", "35 min"]
    measure: "median wall-clock time of one full descent, Normal difficulty"
    status: draft
---

## Tokens

Five balance targets, all `target_kind: scalar`. `legendary_drops_per_quest` is the pity-floor verification target.

## Rationale

**`win_rate_neutral_party` at 0.65.** Higher than Lockstep's 0.5 because Hollow Hold is meant to feel like *progress* — players win most quests; the failure mode is the rare disastrous run.

**`legendary_drops_per_quest` at 0.4.** With 20 drops per quest and pity floor at 50 plus base 1% weight, the expectation is around 0.4 legendaries per quest on average. The tolerance `[0.2, 0.6]` catches both "pity floor isn't firing" (too few) and "weights are wrong" (too many).

**`average_quest_length` at 25 min.** Anchors `{pillars}[2]`. Wall-clock budget for 20 battles + setup + loot = 25 minutes median; the wide tolerance accommodates extra-cautious players (up to 35 min) and speedrunners (down to 18).
