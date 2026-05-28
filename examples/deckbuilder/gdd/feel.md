---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/ember_ascent/feel/**/*.py"]
feel:
  play_card:
    input:    "drag-and-release with momentum; snap-back on illegal target; haptic tick at release"
    response: "card translates to play zone over 180ms cubic-ease-out; energy meter decrements one frame later"
    context:  "energy meter pulses red when the held card costs more than current energy; play zone outlines green on legal hover"
    polish:   "screen flash (8% white, 80ms) on resolve; shake amplitude scales with damage dealt"
    metaphor: "playing a card feels like a definitive commit; no undo; the salamander inhales then exhales fire"
    rules:    "during the 180ms response window, no other verbs are accepted; queued inputs drop"
    status: draft
    implemented_in: ["src/ember_ascent/feel/play_card.py"]
---

## Tokens

One feel entry, for `{verbs.play_card}`. The other six verbs in `gdd/mechanics.md` deliberately do not declare `feel:` — they are mechanical glue (`draw_cards`, `end_turn`) or rare/non-haptic actions (`choose_path`, `claim_reward`). `feel.md` is only required by the spec when at least one verb declares `feel:` (§4.2), so this one entry is what triggers the file's existence.

## Rationale

`play_card` is the *single most-touched verb* in the game — a 200-turn run is ~200 invocations. Every dimension of Swink's six is tuned individually here, in YAML, because each value is normative (e.g. the 180ms response window is a hard contract on the input layer per `{invariants.cross_layer_via_events}`).

The `metaphor:` line ("the salamander inhales then exhales fire") is the *only* sentence in the document that connects the verb to the narrative. That is on purpose — feel is where mechanics and fiction meet.

## Open Questions

- Whether `end_turn` should grow a `feel:` block. Currently no — its haptic is implicit (turn timer bar fills, fade to enemy turn). Reconsider if playtesters report missing the moment.
