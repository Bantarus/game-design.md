---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-23"
pillars:
  - "The graph is the game"
  - "Time pressure, not difficulty pressure"
  - "A real island, not a procedurally-generated one"
non_goals:
  - "Combat"
  - "Procedural generation"
  - "Metagame progression across runs"
  - "Multiplayer"
---

## Tokens

Three pillars, four non-goals. Both lists are immutable for the life of the project under the v0.2.0-alpha stability guarantee. Any addition or removal here is a project-wide event and requires a major-version bump of the root file.

## Rationale

### The graph is the game

The recipe tree is the primary object of player attention. The player's plan is a partial order over `gather` and `craft` actions across the five days; a good plan minimizes wasted gathers, sequences tool-upgrades correctly, and arrives at the signal pyre's materials by midday on Day 4. The graph is shown in a recipes panel from the start — there is no recipe-discovery layer, no "find the formula" mechanic, no hidden requirements. The player has full information about what depends on what; the entire challenge is reasoning under that information against the deadline.

This pillar rejects two common survival-genre patterns: **recipe discovery** (where the player wanders trying combinations) and **opaque dependency graphs** (where the recipe panel shows only the immediate inputs and the player has to walk back through three tiers manually). Both add friction that distracts from the actual planning game.

### Time pressure, not difficulty pressure

There are no enemies, no skill challenges, no twitch tests. The game does not present moments where the player can lose by failing an input. The only way to lose is by running out of in-game time — either dying to hunger/thirst because food/water gathering was deprioritized, or arriving at Day 5 with the pyre incomplete because tools were crafted in the wrong order.

This pillar is the load-bearing rebuttal to "isn't this just another action survival game?" The 30-minute run is **slack-free**, not **hard**. A skilled player on a clean route finishes Day 5 with a few in-game hours to spare and the pyre lit; a first-timer running an inefficient route finishes Day 5 with no rope tied yet and watches the rescue ship pass. The penalty for inefficiency is timing-out, never dying-to-an-enemy.

### A real island, not a procedurally-generated one

The island is hand-designed, six named regions, in fixed positions, with fixed resource nodes. Knowing where the flint outcrop is on the rocky coast is a *real skill* that a player gains across runs — it lets them plan around the high point's distance, makes Day 4's flint-fetch a known commitment rather than an exploration. Procedural generation would make this knowledge worthless (the flint moves every run), defeating the cross-run learning the game's run-length budget assumes.

This pillar rejects the survival-genre default of "every world is fresh." Driftwood's run is short enough (~30 minutes) that across-run learning is what gives the game its replayability surface; procedural would make each run a re-survey rather than a re-plan.
