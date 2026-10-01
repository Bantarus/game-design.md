# Embergrave — C-condition prompt

> Pre-registered under `27a4381` (Phase 5 pre-reg v6). Frozen before trial zero; this file's SHA at trial-harness commit is the locked C-prompt.

You're building a precision platformer called Embergrave. The player is a moth in dark vertical caves, navigating by their own small ember light. The ember dims when the player hesitates — moving well keeps it bright; standing still or hanging on ledges dims it. A dim ember makes the cave hard to see, so hesitation literally darkens what's ahead.

The moth's vocabulary is three actions: a jump (arc fixed at the moment of input, no air control), a dash (a brief burst of horizontal motion in the direction held, costs ember), and a glide (slows the fall, widens the light cone, drains ember slowly while held). That's everything. No double jumps, no wall-clings, no combat. The cave is the whole puzzle; deadly geometry (lava, spikes, falling crushers) kills instantly and respawns the player at the last checkpoint they touched, with no penalty beyond the time to retry. Each level is a single hand-crafted cave segment, roughly three minutes at skilled pace, with a few checkpoints along the natural path.

The game ships around forty levels across four regions (caverns, fault lines, hot springs, summit), forming a climb from the lava-flooded base to the volcano's peak. A skilled player finishes in about an hour; first-timers take three to eight hours across multiple sessions. The pillars are *commitment* (no take-backs on the jump arc), *vision through motion* (the ember is both light and resource, so moving well is rewarded with seeing well), and *cheap death, sticky progress* (death is under a fifth of a second; checkpoint progress carries across deaths and across sessions).

Physics is deterministic — same input sequence on the same level produces the same outcome every time, on any machine — because the game ships replay files as a feature (speedrunners can verify each other's times).
