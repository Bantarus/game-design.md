---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-23"
pillars:
  - "Every jump is a commitment; hesitation dims the ember"
  - "The cave is the puzzle; light is the lens"
  - "Death is cheap; progress is sticky"
non_goals:
  - "Multiplayer"
  - "Procedural level generation"
  - "Combat"
  - "Story-driven cutscenes"
---

## Tokens

The three pillars and four non-goals (see frontmatter) are immutable for the life of the project. Any change here triggers a major-version bump in the root file.

## Rationale

**Every jump is a commitment.** Most platformers let the player feather inputs — tap-jump for a short hop, hold-jump for a long one, with mid-air course correction. Embergrave's jump arc is fixed at press time: hold and you commit to the full arc, tap and you commit to the short. There is no mid-air "rethinking." The ember reinforces this: the same moth that hesitates on the ledge also hesitates on the input, and the longer the ember dims, the harder the next leap reads. The pillar is mechanical *and* perceptual: commitment is rewarded twice, once in motion and once in visibility.

**The cave is the puzzle; light is the lens.** Embergrave is not a "platformer with environmental puzzles." It is a single coherent puzzle (the cave's geometry) viewed through the player's own diminishing tool (the light). A level isn't solved by reading a sign or finding a switch — it's solved by *seeing* the route, which requires keeping the ember bright, which requires moving well. Light is therefore not a hud element but a gameplay mechanic. This is the pillar that motivates the no-mini-map non-goal (implicit; the map is in the player's head from the ember's frame).

**Death is cheap; progress is sticky.** Every checkpoint is a hard save. Dying respawns the moth in under 200ms with no animation, no penalty, no resource loss except in-level ember progress. The cost of death is the time to retry the segment. The reward of progress is permanent: once a checkpoint is touched, it remains touched across deaths and across sessions until the level is completed. The pillar makes the difficulty curve honest — Embergrave can be punishing in moment-to-moment skill because it never punishes the player at session timescale. This pillar is also the load-bearing rebuttal to "isn't this just a hard platformer?"; the answer is "yes, and the failure cost is calibrated to make the difficulty fun rather than spiteful."

## Open Questions

- Whether to support "no-death" run scoring as a meta-layer (e.g. a leaderboard slot per level). Argument for: rewards skill expression beyond completion. Argument against: contradicts "death is cheap" by re-introducing a death penalty at the meta scale. Currently no; revisit after balance pass.
- Whether the ember-dimming-when-hesitating mechanic should be inverted in the final region (summit): the ember is bright at start and dims as you progress, regardless of motion. Argument: the climactic region needs to *feel* climactic. Argument against: changes the pillar's contract late. Currently no.

## Change Log

- 2026-05-23 — original three pillars + four non-goals set.
