---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-21"
pillars:
  - "Every turn, a meaningful hand-shape decision"
  - "Synergy between burn and bellow is discoverable, not memorizable"
  - "A run is short enough to finish on a lunch break"
non_goals:
  - "Multiplayer"
  - "Real-time combat"
  - "Persistent meta-progression unlocks (the run is the meta)"
---

## Tokens

The three pillars and three non-goals (see frontmatter) are immutable for the life of the project. Any change here triggers a major-version bump in the root file.

## Rationale

**Hand-shape decision.** Most deckbuilder turns are "play the obvious sequence." Ember Ascent treats the hand as a *shape*: which 2 of 5 cards survive together, which one gets exhausted, which one is held for the next turn's bellow. The decision is combinatorial, not about card power.

**Burn × bellow.** Burn is a damage-over-time on enemies; *bellow* is a verb category that multiplies burn. The discovery is not knowing they exist — it is noticing that *holding* a bellow for two turns is sometimes correct. Tooltips deliberately do not spell this out.

**Thirty minutes.** A traditional roguelike-deckbuilder run is 60–90 minutes. Internal playtest data: lunch-break players abandon at ~25 minutes regardless of state. Median run budget is therefore 32 minutes (see `{balance_targets.average_run_length}`).

## Change Log

- 2026-04-12 — original three pillars set.
- 2026-05-10 — non-goal "persistent meta-progression unlocks" added after playtest data showed it diluted the 30-minute promise.
