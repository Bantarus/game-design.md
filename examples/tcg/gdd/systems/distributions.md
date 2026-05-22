---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
distributions:
  card_draw:
    type: shuffle_bag
    of: "{entities.cards}"
    refill_when: empty
    seed: deterministic_per_run
    status: draft
    implemented_in: []
  first_player:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.5
    seed: deterministic_per_run
    status: draft
    implemented_in: []
  mulligan_decision:
    type: weighted
    options:
      keep_seven: 0.55
      mull_to_six: 0.30
      mull_to_five: 0.12
      mull_to_four: 0.03
    seed: deterministic_per_run
    status: draft
    implemented_in: []
---

## Tokens

Three distributions, all covered types — `shuffle_bag`, `uniform`, `weighted`. No gaussian (no continuous damage rolls), no pity_floor (no rarity gating in a fixed-deck format), no deterministic explicit (the *whole game* is deterministic via seed; the distributions are reproducibly stochastic).

## Rationale

**`card_draw` is `shuffle_bag`** — the standard TCG abstraction. A 60-card deck is a bag; every card is drawn once before any card is drawn twice. Refill happens on shuffle (when a "shuffle your library" effect resolves) or on bag-empty (an unusual end-game state in Lattice; usually the game has ended by then).

**`first_player` is a uniform coin flip at 0.5.** Deterministic per seed — two clients running the same seed flip the same way.

**`mulligan_decision` is a weighted model of how players actually mulligan.** Used by the verify adapter to simulate realistic mulligan behavior across 1000-match runs. Not used by the live game (real players make their own mulligan choices); this is a *simulation prior*.
