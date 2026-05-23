---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/driftwood/distributions/**/*"]
distributions:
  gather_yield_deterministic:
    type: deterministic
    sequence: [1]
    status: draft
    implemented_in: ["src/driftwood/distributions/gather_yield_deterministic.py"]
  hunger_decay_per_in_game_hour:
    type: deterministic
    sequence: [1]
    status: draft
    implemented_in: ["src/driftwood/distributions/hunger_decay.py"]
  thirst_decay_per_in_game_hour:
    type: deterministic
    sequence: [1]
    status: draft
    implemented_in: ["src/driftwood/distributions/thirst_decay.py"]
  berry_bush_renewal_offset:
    type: weighted
    options:
      offset_0_hours: 1
      offset_3_hours: 1
      offset_6_hours: 1
      offset_9_hours: 1
    selection_rule: declaration_order_first_above
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/driftwood/distributions/berry_bush_renewal.py"]
---

## Tokens

Four distributions. Three are `type: deterministic` — Driftwood is by-pillar a low-RNG game, and most "random" surfaces in the brief are actually fixed-per-node deterministic values that the spec wraps in a constant distribution because every random outcome must resolve through a named distribution (§4.7). The one genuinely-stochastic distribution (`berry_bush_renewal_offset`) is a per-bush offset for when its daily renewal occurs, so the six bushes don't all renew at the exact same in-game minute — a small variety surface that does not change *whether* a bush is harvestable on a given day, only *when within the day*.

## Rationale

### gather_yield_deterministic

Wraps the per-node, per-tool yield lookup in a distribution because the spec requires every random outcome to be a named distribution. The actual yield is read from the resource node's `yield_per_harvest_baseline` (no tool) or `yield_per_harvest_with_correct_tool` (right tool) — both integers — and returned as-is. The wrapping is bookkeeping, not randomness.

### hunger_decay_per_in_game_hour, thirst_decay_per_in_game_hour

The brief states: "Hunger and thirst both start at twelve units, both decrease by one per in-game hour." That's a constant. Same wrapping reasoning as above.

### berry_bush_renewal_offset

The only distribution with actual randomness. The brief says berry bushes "renew at sunrise"; literal sunrise-clock would make all six bushes renew at the same in-game minute, which is uninteresting. This distribution picks an offset from sunrise (0, 3, 6, or 9 in-game hours) per bush, weighted uniformly. With six bushes the player's morning route is slightly varied across runs (some bushes ready immediately, some not until mid-morning) without affecting *whether* the bushes are accessible that day. Seeded `deterministic_per_run` so a given seed reproduces the same offset assignment.

This is a deliberately small RNG surface — it does not affect yields, does not affect availability over the day, and is invisible to the player except as "the bushes feel a little different each run." A pillar-honoring placement.

## Open Questions

- Whether to introduce a `fishing_yield` distribution (tidepools yielding small vs. big fish). The brief's open question flags this as a possible playtest revision; currently no, because the brief's "always the same" is the v1 commitment.
