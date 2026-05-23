# Embergrave — Design Brief

> A precision platformer about climbing a collapsing volcano shaft by the light of your own dimming ember. No combat. No story. The cave is the whole game.

## What you are

You are a moth. Palm-sized, drawn to dying light. You have a small ember that you carry with you — it is both how you see the cave around you and what fuels the harder parts of your movement. The ember is the entire HUD: it's bright when you're moving well; it dims when you're hanging on a ledge thinking; it goes out if you run out, and then you cannot see the next jump until you find another one.

## What you do

Three things, and three things only:

- **Jump.** Press a button, the moth jumps. The arc is fixed at the moment of input — tap for a short hop, hold (at the moment of press) for a long arc. You cannot rethink the arc after takeoff. If you press the button while in the air, nothing happens.
- **Dash.** Press a different button while in the air. The moth shoots in the direction you're holding for about a fifth of a second, then gravity comes back. A dash costs some ember. If you don't have enough, the dash is rejected — nothing happens, your ember flashes dim.
- **Glide.** Hold the jump button while in the air, past a brief grace window. The moth slows its fall to a third of normal gravity, and gives you a wider light cone so you can see further ahead. It drains ember slowly while you're holding. Release to fall again at full speed.

That is everything. There are no double jumps, no wall-clings, no air-control. The moth's six-frame jump and the dash/glide modifications are the entire vocabulary, and learning when to commit to which is the whole skill ceiling.

## What you're trying to do

Climb a collapsing volcano shaft. Each level is a single segment of the shaft, a tight cave roughly three minutes to clear at skilled pace, with one to five checkpoints along the way that let you respawn there if you die. There are about 40 levels across four regions:

- **Caverns** — the introductory region, mostly horizontal traversal with simple gaps. You learn the moth's jump arc here. Roughly 8 levels.
- **Fault lines** — vertical descents and tight diagonal climbs. You learn dash here, and how to use ember pickups to budget mobility. Roughly 10 levels.
- **Hot springs** — the bulk of the mid-game. Geyser timing puzzles, crusher cycles, and the first levels where ember is genuinely scarce. Roughly 12 levels.
- **Summit** — the final region. Long, brutal, ember-tight, with every mechanic combined. Reaching the top is the end of the game. Roughly 10 levels.

Embers are scattered through every level — small glowing collectibles that refill your ember meter on contact. A typical level has seven to fifteen embers; collecting all of them is the soft-completionist meta layer.

You can also die. Dying respawns you at the last checkpoint you touched, in under a fifth of a second — no animation, no penalty, no resource loss except whatever ember you spent in the doomed flight. The cost of death is the time to retry the segment between the last checkpoint and where you died. A typical level might cost you ten deaths on a clean run, more on harder tiers. That's fine. Death is cheap.

## What you cannot do

No combat. There are no enemies. There are deadly things in the world — lava at the bottom of pits, spikes on the ceiling, falling crushers in the hot springs and summit — but they are level geometry, not characters. You die on contact; you respawn; there is no fighting back.

No story-driven moments. There are no NPCs, no cutscenes, no text. The cave is the entire content of the game. If a player asks "what's the story," the answer is "you're a moth, and there is a light at the top."

No procedural generation. Every level is hand-crafted, hand-tuned, hand-checkpointed. The difficulty curve is designed, not generated.

No multiplayer. Single-player only.

## What it should feel like

The three pillars, said three different ways:

**Commitment.** The moth's six-frame jump arc is fixed at the moment of input. You commit, you read the consequence, you live with it. Hesitation is not a feature — and hesitation dims your light, so it doubly punishes you. The pillar runs from input through physics through vision: the same indecision that delays your button press also dims the cave around you.

**Vision through motion.** The cave is the puzzle, and the ember is the lens you read it through. A bright ember shows the route ahead; a dim ember shows three feet of darkness. The way to keep the ember bright is to move well. So the player's reward for skill is *vision*, not damage or score — and the player's punishment for fumbling is the cave getting harder to read.

**Cheap death, sticky progress.** Death is fast and free. Progress is permanent: once a checkpoint is touched, it stays touched, across deaths and across sessions, until the level is completed. This is the load-bearing rebuttal to "isn't this just a hard platformer?" The game is hard in the moment but never punishes the player at the meta scale.

A run from caverns to summit takes a skilled player roughly an hour, and a first-time player anywhere from three to eight hours spread across many sessions. The session is a self-contained climb; the game does not persist run state across sessions in any way that would let one session "buy" easier difficulty in the next.

## Numbers worth knowing

These are designer-intent numbers, not the final balance. Tune at playtest.

- Ember capacity: about 12 units. A dash costs 3; a second of gliding costs 1; jumping is free.
- A skilled player on a tier-3 level finishes with about 6 ember in the meter — visible but tense. If the meter routinely tops out, the level is over-supplying. If it routinely zeros, the level is under-supplying.
- Median time to complete a tier-3 level: about 3 minutes. Tier-1 levels target about 90 seconds; tier-5 levels target about 5 minutes.
- Median deaths per level by tier: roughly 2 / 5 / 10 / 18 / 30 for tiers 1 through 5. Tier-5 levels in the summit region expect a lot of dying. That's fine — every death is under a fifth of a second.
- A skilled player should complete about 70% of the designed levels in a single 90-minute session.
- A skilled player should collect about 80% of the ember pickups in each level they clear.
- Across the 40 levels, the regions split roughly 8 / 10 / 12 / 10. The hot springs are the longest because that's where the mid-game machinery lands.

## How the cave is made

Each level is a single cave segment. It has:

- An entry point where the moth spawns when you first enter the level (or restart).
- An exit point where reaching it ends the level.
- Between one and five checkpoints, placed along the natural path. Touching a checkpoint makes it your respawn point for the rest of the level.
- Some number of ember pickups, scattered along the route or on optional sub-paths for completionists. Worth one to four ember each, depending on placement.
- Some lethal regions — lava pits, spike fields, falling crushers, the void at the bottom of the shaft. Touching any of them kills the moth instantly.
- The geometry itself: the platforms, walls, ceilings, ramps the moth collides with non-lethally. This is the actual cave — handcrafted, axis-aligned bounding boxes assembled into the level's shape.

To author a new level, a designer needs: the entry and exit positions; the checkpoint positions; the ember positions and values; the lethal-region rectangles; and the platform geometry — the rectangles the moth lands on. That's it. Everything else is presentation.

## How the moth moves

Movement is deterministic in the input → physics → outcome sense. Given the same sequence of button presses on the same level, the moth dies at the same place every time. This matters because the game ships replay files as a feature: every death produces a recorded replay; the player can watch their attempts back, and speedrunners can verify each others' times.

The physics simulation runs at 60 ticks per second, regardless of how fast the display refreshes. Position is stored as integers, not as floating-point — fine enough that the moth feels smooth (one thousandth of a unit per tick of velocity), coarse enough that it's perfectly reproducible across machines.

The moth's state at any moment is one of: standing on a platform, in the air with normal gravity, in the middle of a dash (a fifth of a second, gravity off), gliding (slowed fall, ember draining), or dead (respawning to the last checkpoint). Transitions between these are driven by inputs and by physics — landing on a platform from the air, walking off a ledge, dashing off the level into a lethal region, etc.

## What's not in the brief

What you build with all of this — the asset pipeline, the renderer, the input-handling code, the platform geometry data format, the audio — is not part of the design. The design is the moth, the cave, the ember, and the three verbs. Whatever engine choices a builder makes, they have to make those three verbs feel the way the commitment / vision / cheap-death pillars demand. That is the design.

## Open questions a designer would flag

- Whether levels should ever penalize collection (e.g. ember pickups that require committing to a death). Argument for: completionists like risk. Argument against: contradicts "death is cheap, progress is sticky" by punishing players who try to collect. Leaning no.
- Whether to add a "no-death" run scoring system as a meta-layer (leaderboard slot per level for clean clears). Argument for: rewards mastery. Argument against: contradicts "death is cheap" at the meta scale, where death now has a permanent cost. Leaning no for v1.
- Whether the ember-dimming-with-hesitation should be inverted in the summit region (ember dims with progress, regardless of motion). Argument for: climactic feel. Argument against: contradicts the pillar contract late in the game. Leaning no.

## The story, in case someone asks

You are a moth. There is a light at the top. The volcano is falling apart underneath you. That is enough.
