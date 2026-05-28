---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
loops:
  tick:
    timescale: moment
    duration: "~250ms"
    clock: "{clocks.tick}"
    sequence: []
    intended_dynamics:
      - "each tick resolves one round of unit-on-unit damage"
    intended_aesthetics: [challenge]
    feel_priority: high
    balance_targets:
      - "{balance_targets.average_ticks_per_match}"
    status: draft
    implemented_in: ["src/loops/tick.py"]
  match:
    timescale: session
    duration: "~30-90s"
    sequence:
      - deploy:  "{verbs.deploy_units}"
      - fight:   "{loops.tick}"
      - resolve: "{verbs.resolve_match}"
    intended_dynamics:
      - "a match runs until one side has no units alive"
    intended_aesthetics: [challenge]
    balance_targets:
      - "{balance_targets.win_rate_neutral_formation}"
    status: draft
    implemented_in: ["src/loops/match.py"]
---

## Tokens

Two nested loops. The `tick` loop is pure-clock-driven (F-010 v0.3) — its
`clock:` field references `{clocks.tick}` and its `sequence:` is empty,
because the clock IS the loop iteration. The `match` loop is the session
loop, bracketing one match with deployment + fight + resolution phases.

## Rationale

**Empty `sequence:` on the tick loop is intentional.** Per F-010 v0.3, a
loop with `clock:` populated may have empty `sequence:` — the iteration is
clock-driven, not verb-driven. Tick-combat is the canonical case for this
shape; without F-010 you'd have had to model the tick as a synthetic
"advance_tick" verb whose sole purpose was to trigger the resolution rule.
