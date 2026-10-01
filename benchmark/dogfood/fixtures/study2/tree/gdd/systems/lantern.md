---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: prototyped
last_verified: "2026-04-24"
implemented_in: ["impl/lanternfall/lantern/**/*.py"]
rules:
  gutter_check:
    given:
      driver: "{clocks.lantern_burn}"
    target_selection: self
    do:
      - { burn: "{resources.lantern_oil}", amount_from: "verb.oil_cost" }
      - { below: 20, transition: "{states.lantern_state.dim}" }
      - { at_zero: true, transition: "{states.lantern_state.guttered}" }
    outputs: [oil_checked]
    status: prototyped
    implemented_in: ["impl/lanternfall/lantern/wick.py"]
  refill_lantern:
    given:
      verb: "{verbs.trim_wick}"
    target_selection: self
    do:
      - { restore: "{resources.lantern_oil}", amount: 30 }
      - { transition: "{states.lantern_state.lit}" }
    outputs: [lantern_refilled]
    status: draft
    implemented_in: ["impl/lanternfall/lantern/refill.py"]
---

## Tokens

Two rules: the per-verb oil check the lantern clock drives, and the refill a trimmed wick grants.

## Rationale

**Dim before dark.** The lantern dims at 20 oil, a full floor's warning before it gutters. Dimming is what invites wandering spawns, so the warning is also a threat.
