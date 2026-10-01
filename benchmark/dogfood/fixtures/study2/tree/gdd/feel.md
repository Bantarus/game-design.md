---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-04-18"
implemented_in: ["impl/lanternfall/feel/**/*.py"]
feel:
  descend_stair:
    input: "hold to descend; release early to stay on the landing"
    response: the lantern swings and the stairwell darkens over 400ms
    context: the oil gauge ticks down by the stair's cost as the camera settles
    polish: "dust falls from the ceiling; the knell-bells hum at depth 3 and below"
    metaphor: a descent is a promise you cannot take back
    rules: no input is accepted during the 400ms transition
    status: draft
    implemented_in: ["impl/lanternfall/feel/descend_stair.py"]
  strike_foe:
    input: tap to strike the highlighted foe
    response: "the blow lands within 120ms; damage numbers rise from the target"
    context: the lantern flares on a crit
    polish: a short screen shake scaled to damage dealt
    metaphor: every strike is a spark struck in the dark
    rules: a second tap during the strike is queued, not dropped
    status: draft
    implemented_in: ["impl/lanternfall/feel/strike_foe.py"]
  ring_the_knell:
    input: hold for one full second to ring
    response: "a low toll rolls outward; every lit sconce flickers"
    context: the boss markers on the depth map pulse
    polish: the controller rumbles once per toll
    metaphor: ringing the knell wakes what should have stayed asleep
    rules: cannot be cancelled once the toll starts
    status: draft
    implemented_in: ["impl/lanternfall/feel/ring_the_knell.py"]
---

## Tokens

Three feel entries, one for each verb that declares `feel:`. The rest are mechanical glue.

## Rationale

**Commitment is the common thread.** Descending, striking and ringing the knell are the three moments the player cannot undo; each is tuned to feel like a commitment.
