---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: prototyped
last_verified: "2026-05-22"
implemented_in:
  - "impl/xtreme/src/loops.rs"
  - "impl/xtreme/src/sim.rs"
loops:
  tick:
    timescale: moment
    duration: "~100ms"
    sequence: []                     # pure clock-driven loop; no player verbs
    clock: "{clocks.tick}"           # F-010 v0.3 resolution: time-passage is first-class
    intended_dynamics:
      - "one unit acts per tick; action order is deterministic given seed"
    intended_aesthetics: [challenge]
    feel_priority: low
    balance_targets:
      - "{balance_targets.median_ticks_per_combat}"
    status: draft
    implemented_in: []
  encounter:
    timescale: session
    duration: "~30-90s"
    sequence:
      - deploy:  "{verbs.deploy_unit}"
      - form:    "{verbs.set_formation}"
      - start:   "{verbs.start_combat}"
      - ticking: "{loops.tick}"
      - resolve: "{verbs.resolve_combat}"
      - collect: "{verbs.collect_reward}"
    intended_dynamics:
      - "setup decisions outweigh tick-time outcomes"
      - "formation buffs reward planned synergy"
    intended_aesthetics: [challenge, expression]
    feel_priority: medium
    balance_targets:
      - "{balance_targets.average_team_dps}"
    status: draft
    implemented_in: []
  campaign:
    timescale: meta
    duration: "~20min"
    sequence:
      - loop: "{loops.encounter}"
    intended_dynamics:
      - "gold economy creates a meta-decision between unit-add and unit-upgrade"
    intended_aesthetics: [challenge, discovery]
    feel_priority: low
    balance_targets:
      - "{balance_targets.gold_per_encounter}"
    status: draft
    implemented_in: []
---

## Tokens

Three loops at three timescales: `{loops.tick}` (moment) inside `{loops.encounter}` (session) inside `{loops.campaign}` (meta).

## Rationale

`{loops.tick}` is the *unit of determinism* — one tick advances one unit's action. The whole point of `{distributions.action_order}` being `type: deterministic` is so that two clients observing the same encounter see the same tick fire on the same unit in the same order.

`{loops.encounter}` is the *unit of play*: a complete setup → ticking → resolution cycle. Encounters are short by design (`{balance_targets.median_ticks_per_combat}` targets ~120 ticks ≈ 12 seconds wall-clock).

`{loops.campaign}` is the *unit of progression* — a 20-minute session strings together ~20 encounters with gold accumulating between them.
