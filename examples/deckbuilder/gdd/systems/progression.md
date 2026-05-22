---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/ember_ascent/progression/**/*.py"]
---

## Tokens

This file contributes no tokens of its own. It exists to document the *prose conventions* for how the game scales difficulty across the three acts.

## Rationale

Ember Ascent has three acts (Foothills → Slope → Caldera), each ~10 minutes. Progression is purely a *content shape* concern — acts override default values in `{distributions.enemy_pack_size}` and `{distributions.reward_choice}` rather than adding new tokens. This is the spec's recommended pattern (§3 "prefer prose conventions over genre-specific tokens").

**Act 1 (Foothills).** Default weights from `gdd/systems/distributions.md` apply. Encounters are 1–3 enemies. Player learns burn × bellow.

**Act 2 (Slope).** Enemies have +50% HP; `enemy_pack_size` weights shift to `{ small: 0.25, medium: 0.50, large: 0.25 }`. Elite encounters introduce status effects beyond burning.

**Act 3 (Caldera).** Enemies have +100% HP; `enemy_pack_size` shifts to `{ small: 0.10, medium: 0.40, large: 0.50 }`. Boss has a unique two-phase intent deck (specified in `content/enemies/magma_drake.yaml`).

Difficulty *ascensions* (post-win modifiers) are deferred to v0.5; v0.1.1 only ships Ascension 0 (Normal). All `balance_targets.*_ascension_0` apply.

## Open Questions

- Whether the per-act override pattern should be lifted into a new `progression` namespace. Argument against: every override would still be the same distribution types, just re-parameterized; the prose convention is cleaner. Current call: keep as prose.
