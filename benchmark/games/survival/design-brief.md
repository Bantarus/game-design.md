# Driftwood — Design Brief

> A short survival game about being shipwrecked on a small island. Gather, craft, survive five days, light the signal, get rescued. The island is the whole game.

## What you are

You're a sailor from a passenger vessel that broke up in a storm. You came to on the beach with the clothes you had on, a small belt knife, and the cabin trunk that washed up beside you. Nothing else. The island is small enough to walk across in ten minutes; the rescue ship's route passes the island's signal point every five days. You have until the next pass.

## What you do

Four things, and four things only:

- **Gather.** Walk up to a resource node — a tree, a stone outcrop, a tidepool, a fiber plant — and harvest it. The yield depends on what tool you're carrying: bare hands gives a small amount, the right tool gives a useful amount. Resource nodes do not respawn within a single five-day run (except berry bushes, which renew at sunrise).
- **Craft.** At your camp, combine materials into items by recipe. Recipes are fixed and known — there is no recipe discovery, no random outcomes, no failure chance. Some recipes need a crafting station (sawhorse for planks, fire for cooking).
- **Eat, drink, sleep.** Hunger and thirst both decay over the in-game day; you die if either reaches zero. Eat cooked fish, raw berries, or other foodstuffs to refill hunger; drink at the spring or from a still to refill thirst. Sleeping in the basic shelter you craft skips night-time exposure damage; sleeping in the open at night costs you health each in-game hour.
- **Build the signal pyre.** The win condition. The pyre requires the most expensive recipe chain in the game — multiple tiers of wood, plenty of fiber rope to tie it together, a flint shard to light it, and assembling it at the island's high point. Once lit at sunset on the final day, you survive the night and the rescue ship sees you the next morning.

## What you're trying to do

Reach Day 5 alive, with the signal pyre lit and burning at sunset. The end.

## Day rhythm

Each in-game day breaks into four parts: morning, afternoon, evening, night. Morning and afternoon are gathering-friendly (visibility, dry tools). Evening is short and good for crafting at camp. Night is dangerous — too cold without shelter, and you cannot see the gather nodes well enough to harvest. A campfire extends the safe hours into evening; a built shelter lets you sleep safely through night. A real-time day is about six minutes wall-clock, so a full five-day run is roughly thirty minutes of play.

A first-time player misses the rescue (~80% of first runs) by under-gathering on Day 3 or running out of food on Day 4. The game restarts at Day 1 with the same island, same resource layout, same recipes — what they learned about the island's geography is the only thing that carries over.

## What you cannot do

- **No combat.** There are no wolves, no aggressive wildlife, no antagonists, no people. The island is empty of threats other than weather and time.
- **No procedural generation.** The island is hand-designed. Same island every run. Same nodes in the same places.
- **No metagame progression.** You don't unlock new recipes between runs, you don't have a permanent skill tree, you don't carry items across runs. Knowledge of the island is the only thing the player banks.
- **No multiplayer.** Single-player only.

## What it should feel like

Three pillars:

- **The graph is the game.** Recipes form a dependency tree: wood becomes planks at the sawhorse; fiber becomes rope; stone becomes a pickaxe that lets you mine flint. The player's plan IS reasoning about this tree — which nodes to visit in what order, which tool to craft first, when to stop gathering and start crafting. The recipe tree is shown to the player in a panel from the start of run one; nothing is hidden.
- **Time pressure, not difficulty pressure.** There are no enemies and no skill challenges. The whole challenge is that there isn't quite enough time to do everything inefficiently. Skill is route-planning across the five days. Bad routes leave you on Day 5 short of fiber rope and watching the rescue ship pass.
- **A real island, not a procedurally generated one.** The island has named places — the beach, the tree grove, the spring, the rocky coast, the cliff approach, the high point. They sit in fixed positions. Learning the island is a real skill that pays off across runs.

## Numbers worth knowing

Designer-intent numbers, tune at playtest.

- **Day length:** an in-game day is six minutes wall-clock; a full run is about thirty minutes.
- **Starting items:** the belt knife (durability for the whole run, used in tier-1 recipes) and nothing else.
- **Hunger and thirst:** both start at twelve units, both decrease by one per in-game hour. Hunger kills you at zero in three real-time minutes if ignored; cooked fish refills six, raw berries one. Thirst kills you faster (the spring is your friend); spring water refills eight. Both are integer counts, no fractions.
- **Tool durability:** wooden axe lasts twelve gathers; pickaxe lasts sixteen mines; stone axe lasts twenty-four gathers. Each individual tool tracks its own remaining uses.
- **Inventory:** twelve slots in your pack. Stackable raw materials (wood, fiber, stone, berries) stack eight per slot; tools and crafted unique items take one slot each and don't stack.
- **The signal pyre recipe:** eight wooden planks, six lengths of rope, one flint shard, assembled at the high point. Each plank needs two wood at the sawhorse (and the sawhorse needs three stone plus four wood to build). Each rope needs three fiber. So the full pyre needs about twenty wood, eighteen fiber, seven stone, and one flint — gatherable comfortably by Day 4 if the player crafts the axe early on Day 2.

## How the island is made

Hand-authored. The island has:

- **Six named regions:** beach (start point, camp location), tree grove, freshwater spring, rocky coast, cliff approach, high point.
- **A fixed set of resource nodes:** about thirty trees in the grove (one to three wood each, more with axe), about twelve stone outcrops, about twenty fiber plants, six berry bushes (renew per day), one spring (unlimited water), four tidepools (fish; harvestable per day), one flint outcrop (single flint shard, on the rocky coast).
- **A camp location** at the beach, where the player starts each day, where crafting stations get built, and where any items left behind on a previous day are still found.
- **The high point** at the island's peak where the pyre is built and lit.

To author a new region for the island, a designer needs: the region's name, its resource nodes (kind and per-node yield), its position on the island map, and any time-of-day restrictions (tidepools only at low tide, for example).

## The recipe tree

A short list, organized by tier. The full list is the content the game ships with.

- **Tier 0 — no tool needed:** rough campfire (three wood; lights at dusk for six in-game hours), water jug (two fiber; holds two drinks).
- **Tier 1 — needs the starting belt knife:** fiber rope (three fiber), wooden axe (three wood plus one rope), basic shelter (eight wood plus four fiber; built at camp, lets you sleep safely).
- **Tier 2 — needs wooden axe:** wooden plank (two wood, crafted at a sawhorse), fishing rod (two wood plus two fiber), still (three stone plus four wood, slowly distills seawater into drinking water).
- **Tier 3 — needs pickaxe:** pickaxe (three wood plus four stone plus one rope), stone axe (two wood plus six stone), sawhorse (three stone plus four wood; crafting station for planks).
- **Win tier — needs everything above:** signal pyre (eight planks plus six rope plus one flint shard; assembled at the high point on Day 4 or 5, lit at sunset on Day 5).

## What's not in the brief

What you build with all of this — the engine, the renderer, the input device, the save format, the visual style, the audio — is not part of the design. The design is the island, the four verbs, the recipe tree, and the five-day deadline. Whatever engine choices a builder makes, the design's three pillars (the graph is the game / time pressure not difficulty pressure / a real island) have to come through.

The brief doesn't specify how runs are saved either. A designer would expect the run to autosave periodically — losing twenty minutes of careful gathering to a crash is intolerable — but exactly when and how is for the engineering team to decide. The game must be safely interruptible at any in-game moment.

## Open questions a designer would flag

- Whether dying should end the run (permadeath) or respawn the player at sunrise of the day they died (with whatever they had left). Currently respawn at sunrise; permadeath is too punishing for a thirty-minute run where one wrong route on Day 4 kills you.
- Whether tidepool fishing should yield variable fish (small vs. big) or always the same. Currently always the same; variable fish would introduce randomness the brief is supposed to minimize.
- Whether berry bushes should renew per-day or per-run. Currently per-day; would be re-tuned to per-run if hunger turns out to be too easy at playtest.

## The story, in case someone asks

You woke up on the beach with a broken trunk and a belt knife. There is a ship that passes every five days. Light the pyre. You can go home.
