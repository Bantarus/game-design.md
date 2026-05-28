---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/driftwood/feel/**/*"]
feel:
  gather:
    input:    "select node → confirm; longer hold to harvest 'all in this stack' where the node has remaining harvests"
    response: "tool animation plays for ~1s (axe swings, pickaxe strikes); inventory icon flashes when the new item lands"
    context:  "node visually depletes (tree loses leaves, stone outcrop shrinks); the tool's durability meter on HUD nudges down by one segment"
    polish:   "subtle dust/leaves particle on harvest; audio thump scaled to tool tier (knife thin, axe full, pickaxe heavy); inventory icon-add chime"
    metaphor: "harvesting feels like *taking* — a deliberate transfer from world to pack, not magical destruction"
    rules:    "during the harvest animation, no other verb is accepted; cancellation requires waiting through the animation"
    status: draft
    implemented_in: ["src/driftwood/feel/gather.py"]
  craft:
    input:    "open the recipes panel → select recipe → confirm if inputs and station present, dim if not"
    response: "recipe icon translates from panel to inventory over 300ms; affected input icons in inventory deplete in lock-step"
    context:  "recipes panel highlights newly-craftable recipes (turned from gray to colored) when the player gathers the final missing input — the panel is a live planning surface"
    polish:   "completion chime; the new item briefly pulses in inventory; if recipe required a station, the station emits a small visual confirmation (fire flares for cooking, sawhorse drops sawdust)"
    metaphor: "crafting feels like *making* — inputs transform into an output that didn't exist a moment ago; nothing is hidden, nothing is randomized"
    rules:    "during craft animation, panel remains open and other verbs are accepted (the player can queue the next action while the icon is in flight)"
    status: draft
    implemented_in: ["src/driftwood/feel/craft.py"]
  eat:
    input:    "select food item in inventory → eat; long-hold to eat to-full (multiple items at once if multiple are present)"
    response: "hunger meter bar fills up over ~400ms after the eat animation completes"
    context:  "hunger meter on HUD is visible at all times; the food item icon disappears from inventory"
    polish:   "soft eating audio (crunch for berries, sizzle-and-bite for cooked fish); the hunger-meter fill animation is smooth, not stepwise — refilling 6 units shows the fill"
    metaphor: "eating feels like *sustenance* — practical, not gluttonous; the brief's tone is sailor-on-an-island, not feasting"
    rules:    "no movement during eat animation; the action is interruptible (player can stop mid-eat, food remains uneaten)"
    status: draft
    implemented_in: ["src/driftwood/feel/eat.py"]
  drink:
    input:    "select water source (spring / still) when adjacent → drink"
    response: "thirst meter fills similarly to eat; spring water shows a brief water-sound + cup-tilt animation"
    context:  "thirst meter on HUD; the still has a visible water-level that drops by one drink"
    polish:   "spring has subtle ambient water-burble audio that the player can navigate to without looking; the still adds a quiet drip when actively distilling"
    metaphor: "drinking feels like *relief* — the brief implies thirst is the faster-killing meter; refill is a sigh"
    rules:    "drink animation ~600ms; not interruptible (drinking is a single action commitment)"
    status: draft
    implemented_in: ["src/driftwood/feel/drink.py"]
  place_station:
    input:    "select crafting station recipe in panel → place ghost at camp location → confirm"
    response: "ghost station materializes into solid; inputs deplete from inventory; station becomes immediately interactable"
    context:  "the camp area on the island map gradually populates with built stations across the run — the campsite is the visible expression of the player's progress"
    polish:   "construction sound (hammering, sawhorse-clack); brief 1s 'building' animation between ghost and solid"
    metaphor: "building feels like *settling* — the camp accretes character across the run; players who finish their run with a fully-built camp leave it behind as their mark"
    rules:    "station placement is final — once placed, cannot be moved (only rebuilt elsewhere with fresh inputs); placement is restricted to the camp region (except the pyre, which goes at the high point)"
    status: draft
    implemented_in: ["src/driftwood/feel/place_station.py"]
  sleep:
    input:    "select 'sleep' from main menu when at night-state and adjacent to shelter (or anywhere if accepting open-air penalty)"
    response: "screen fade to black over 800ms; HUD updates show day count incrementing; meters tick (no decay from sleep itself, but hp penalty if no shelter)"
    context:  "the world transitions from night to dawn; the shelter's animation has a brief 'closing-eyes' moment if sleeping inside; open-air sleep has a brief ambient 'cold-wind' audio cue"
    polish:   "fade-to-black timing is the rhythm beat of the run — the player feels the day-end ritual; dawn-sound (faint bird, surf) accompanies the wake"
    metaphor: "sleep feels like *passage* — the time skip is felt as a rhythm, not as a menu interaction"
    rules:    "sleep is unskippable once started — the fade plays through, the day advances, no mid-sleep interruption"
    status: draft
    implemented_in: ["src/driftwood/feel/sleep.py"]
  assemble_pyre:
    input:    "select 'assemble pyre' when at high_point AND adjacent to remaining pyre-layer recipe inputs in inventory"
    response: "construction animation per layer (~2s), one layer per action; pyre's visible silhouette grows on the high point"
    context:  "the pyre is visible from the camp on a clear day — the player can see their progress from anywhere on the island"
    polish:   "each layer's completion has its own sound — base-laid is a thud, middle is interlocked logs, top is the capstone landing; the pyre's silhouette is a real visual achievement"
    metaphor: "assembly feels like *committing* — each layer is a chunk of resources you cannot easily walk back; the final layer is the point of no return for the run's strategy"
    rules:    "no other verbs during assemble animation; assembly must be at the high_point (no other coordinate works)"
    status: draft
    implemented_in: ["src/driftwood/feel/assemble_pyre.py"]
  light_pyre:
    input:    "select 'light' when pyre.assembled_layers == 4 AND world_clock.day == 5 AND world_clock.part == evening AND flint_shard in inventory"
    response: "flint-strike animation; the pyre ignites; the world view pulls back to show the lit pyre on the high point; HUD freezes for ~2s before the night transition"
    context:  "the entire game compresses to this moment — every gather, every craft, every meter-tick led here"
    polish:   "the lighting is the game's climax — extended fire-catching animation, audio swells, the rescue-ship horn is faintly audible from out at sea; the screen does not dim or change controls until the rescue confirmation"
    metaphor: "lighting feels like *signaling* — your existence on this island is finally addressed to the world; the rescue is implicit in the act"
    rules:    "once lit, no further verbs are needed or accepted — the run proceeds automatically to the rescue cutscene at dawn-of-Day-6"
    status: draft
    implemented_in: ["src/driftwood/feel/light_pyre.py"]
---

## Tokens

Eight feel blocks covering the player-actor verbs. One verb (`start_day`) is infrastructure — it doesn't have player-facing feel, because the player doesn't issue it directly; it's part of the day-cycle engine under the hood. Per-action world-time advancement is no longer a verb (F-010 v0.3 resolution lifted it to `{clocks.world_time}` — see `gdd/clocks.md`). The eight player verbs each declare their six Swink dimensions per spec §4.9.

## Rationale

Each verb's feel matches its tier on the design's *commitment ladder*: gathering and eating are low-commitment / frequent / cheap-feel; crafting and drinking are mid-commitment / planned; building a station is high-commitment / accretive; sleeping is a rhythm beat; assembling and lighting the pyre are the run's climax beats and carry the heaviest feel weight.

The `metaphor:` field for each verb is the most opinionated — it names what the action *means* to the player beyond its mechanical effect. "Gathering as taking, not destroying" and "lighting as signaling, not winning" are the design's tone; these would drift first if the prose is forgotten.

## Open Questions

- Whether `feel.gather` should be one block (current) or per-node-kind blocks (chop-tree-feel differs from fish-tidepool-feel). v0.1 keeps it one block with conditional prose; revisit if playtest reveals the conflation feels generic.
- Whether `feel.assemble_pyre` should escalate per layer (capstone heavier than base) inside the same `feel:` block. Currently single-block; v0.1 simplification.
