---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/embergrave/balance/**/*"]
balance_targets:
  ember_velocity:
    target_kind: scalar
    target: 6
    tolerance: [4, 8]
    measure: "median {resources.ember} value at the moment of any in-level checkpoint touch, skilled-player tier-3 level"
    status: draft
  median_time_per_flight:
    target_kind: range
    target: { near: 7000, tolerance: 3000 }
    measure: "median wall-clock milliseconds from spawn-or-checkpoint to next death-or-checkpoint, all tiers"
    status: draft
  median_time_to_complete_level:
    target_kind: scalar
    target: 180000
    tolerance: [120000, 300000]
    measure: "median wall-clock milliseconds from level_entered to level_exit_reached, skilled player, tier-3 level"
    status: draft
  median_deaths_per_level:
    target_kind: distribution_over_categories
    target:    { tier_1: 2,  tier_2: 5,  tier_3: 10, tier_4: 18, tier_5: 30 }
    tolerance: { tier_1: 2,  tier_2: 3,  tier_3: 5,  tier_4: 8,  tier_5: 12 }
    measure: "median deaths-before-completion per tier, skilled player, level_progress reaching completed"
    status: draft
  ember_collected_pct_per_level:
    target_kind: scalar
    target: 0.80
    tolerance: [0.65, 0.95]
    measure: "median fraction of ember_pickups collected per completed level, skilled player, all tiers"
    status: draft
  skilled_player_run_completion_pct:
    target_kind: scalar
    target: 0.70
    tolerance: [0.55, 0.85]
    measure: "median fraction of levels in content/levels/ completed-to-summit in a single 90-minute session, skilled player"
    status: draft
  levels_per_region:
    target_kind: distribution_over_categories
    target:    { caverns: 8, fault_lines: 10, hot_springs: 12, summit: 10 }
    tolerance: { caverns: 2, fault_lines: 2,  hot_springs: 3,  summit: 2  }
    measure: "designed level count per region in content/levels/*.yaml"
    status: draft
---

## Tokens

Seven balance targets covering all three v0.2 `target_kind` values: four `scalar`, one `range`, and two `distribution_over_categories`. Each is referenced from at least one of: a loop's `balance_targets:`, a resource's `velocity_target:`, a content-schema's `balance_refs:`, or a `verify_targets[]` block (if/when added). Any target not referenced fires `orphaned-entity` (warning).

## Rationale

**`ember_velocity` is the binding hud-feel constraint.** Median ember of 6 (out of 12 max) at the moment of checkpoint-touch is the design call: visible-but-tense, with 6 ember representing roughly 2 dashes + 2 short glides of remaining mobility. A run where ember habitually maxes out (median 11-12) means the level over-supplies ember and tension is dead; a run where ember habitually empties (median 0-2) means the level under-supplies and the player can't recover from a bad route. The `[4, 8]` band defines the acceptable design space.

**`median_time_per_flight` is `target_kind: range` to make the band-shape explicit.** A flight is 5–10 seconds; the `{ near: 7000, tolerance: 3000 }` form expresses "7 seconds ± 3" — the same band as `[4000, 10000]` but the matcher-form makes the design intent clearer (the target *is* a band; the player should rarely complete a flight in 2 seconds and rarely take 15).

**`median_time_to_complete_level: 180000ms` (3 min) is the design contract.** Any tier-3 level that routinely exceeds 5 minutes has a missing checkpoint or a difficulty miscalibration. Tier-1 levels target ~90 seconds; tier-5 levels target ~5 minutes. The tolerance band `[120000, 300000]` is for the tier-3 median specifically; per-tier targets would be a v0.5 refinement.

**`median_deaths_per_level` uses `distribution_over_categories` to encode the difficulty curve.** Each tier has its own median-deaths target, and the per-category tolerance lets the easy tiers be more forgiving (tier_1: 0–4 deaths acceptable; tier_5: 18–42 deaths acceptable). This is a deliberate `distribution_over_categories` usage rather than five separate scalar targets because the tiers' relationship to each other is the *thing being balanced* — if tier_2 is 5 but tier_3 is also 5, the curve is wrong.

**`ember_collected_pct_per_level: 0.80` is the soft-completionist anchor.** A skilled player on a clean first-try should collect ~80% of in-level ember. The wide band `[0.65, 0.95]` is because mastery enables higher collection (the 95% upper bound) and difficulty rises (the 65% lower for tier_5 levels). The metric is per-completed-level, so failed attempts don't contaminate.

**`skilled_player_run_completion_pct: 0.70`** is the headline "is the curve reasonable" metric. A skilled player should complete 70% of designed levels in a 90-minute session. Less than 55% means the difficulty curve is too steep; more than 85% means the curve is too flat (the back levels aren't doing their job).

**`levels_per_region` uses `distribution_over_categories` for designed-count balance** — the four regions sum to 40, the `count_target` declared on the levels content-schema. Caverns (8 levels) is the shortest introductory region; hot_springs (12) is the bulk of the mid-game; summit (10) is the climax.

## Open Questions

- Whether `median_time_per_flight` should be per-tier rather than overall (tier_5 flights are presumably longer per-attempt). Argument for: more precise. Argument against: the headline number tells the design call ("flights are short"). Currently flat.
- Whether `ember_collected_pct_per_level` should split into a "first-clear" vs "clean-clear" pair (collection on a first-attempt vs. a routed-attempt-after-deaths). Currently aggregate. Re-evaluate after telemetry exists.
- Whether to add a `boss_completion_rate_per_region` target for the last-level-of-region soft gates. Currently no — the per-tier death counts already encode this implicitly. Re-evaluate if soft-gate frustration is reported.
