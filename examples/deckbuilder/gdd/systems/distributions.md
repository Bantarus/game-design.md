---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/ember_ascent/rng/**/*.py"]
distributions:
  card_draw:
    type: shuffle_bag
    of: "{entities.cards}"
    refill_when: empty
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/ember_ascent/rng/card_draw.py"]
  damage_roll:
    type: gaussian
    mean: 6
    stddev: 1
    clamp: [1, 99]
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/ember_ascent/rng/damage_roll.py"]
  critical_hit:
    type: uniform
    range: [0.0, 1.0]
    threshold: 0.15
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/ember_ascent/rng/critical_hit.py"]
  enemy_pack_size:
    type: weighted
    options:
      small:  0.5
      medium: 0.35
      large:  0.15
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/ember_ascent/rng/enemy_pack_size.py"]
  reward_choice:
    type: weighted
    options:
      card_common:   0.50
      card_uncommon: 0.30
      card_rare:     0.10
      removal:       0.05
      heal:          0.05
    seed: deterministic_per_run
    status: draft
    implemented_in: ["src/ember_ascent/rng/reward_choice.py"]
---

## Tokens

Five distributions. **Every random outcome in Ember Ascent resolves through one of these** — the spec's `undefined-distribution` rule is `error`, so any ad-hoc roll anywhere in the tree is a hard lint failure.

## Rationale

`card_draw` is a `shuffle_bag` over `{entities.cards}` because deckbuilders care about *exhaustion* — once a card is drawn it does not return until the discard pile reshuffles. `refill_when: empty` is the canonical implementation.

`damage_roll` is `gaussian(6, 1)` clamped to `[1, 99]` and rounded by the resolver (`{rules.damage_resolution}`). The Gaussian shape gives a "feels right" hit-feel: most hits cluster near the card's printed value, with rare crunchy outliers. The integer rounding is required by `{invariants.damage_is_integer}`.

`critical_hit` is a `uniform` threshold roll. 0.15 = 15% baseline crit rate.

`enemy_pack_size` is `weighted` because pack composition is not a fixed table — early acts favor `small`, later acts favor `medium/large`. The 0.5/0.35/0.15 weights here are the Act 1 baseline; later acts override via `gdd/systems/progression.md` (prose convention).

`reward_choice` is `weighted` over reward types. The weights are tuned to deliver ~6 card-adds, ~1 removal, ~1 heal per run on average; `{balance_targets.cards_per_rarity}` enforces the rarity mix.

All five carry `seed: deterministic_per_run` — necessary precondition for `{invariants.deterministic_given_seed}`, which is verified in `gdd/verification.md`.

## Open Questions

- Whether `critical_hit` should be a `pity_floor` rather than `uniform`. Argument for: streaks of zero crits across a 4-turn fight feel bad. Argument against: pity floors quietly raise the *expected* crit rate, which would shift `{balance_targets.win_rate_ascension_0}` by ~3%. Current call: stay `uniform`, revisit if playtesters complain.
