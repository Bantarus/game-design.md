---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: prototyped
last_verified: "2026-05-28"
implemented_in:
  - "impl/xtreme/src/loops.rs"
  - "impl/xtreme/src/sim.rs"
clocks:
  tick:
    mode: continuous
    rate: { hz: 10 }
    drives:
      - "{rules.tick_resolution}"
    status: prototyped
    implemented_in: ["impl/xtreme/src/loops.rs"]
---

## Tokens

This file owns the `clocks` namespace for Lockstep. The single clock `{clocks.tick}` drives `{rules.tick_resolution}` at 10 Hz (~100ms per tick).

## Rationale

**`{clocks.tick}` is the unit of determinism.** Lockstep's whole point — byte-identical replays given the seed — depends on the tick being a *clean* primitive: one tick advances one unit's action, the action order is deterministic per `{distributions.action_order}`, and the clock fires the resolution rule with no ambiguity about whether a player intent gates the advancement (it doesn't). The earlier modeling — a synthetic `verbs.advance_tick` whose sole purpose was to satisfy the spec's verb-triggers-rule pattern — buried that contract in a "verb the player never issues." F-010's v0.3 resolution lifts time-passage to a first-class clock primitive (spec §4.7), so the contract is structural rather than convention.

**Rate in `hz:` not `period_ms:`.** Either is legal per spec §4.7; `hz: 10` matches the wall-clock-to-game-tick conversion used elsewhere in this tree's prose (`{loops.tick}.duration: "~100ms"`).

**`drives:` lists exactly one rule.** A tick fires `{rules.tick_resolution}` — that single rule walks the deterministic action order (`{distributions.action_order}`) and applies one unit's action per firing. No other rule is clock-driven in Lockstep; non-tick-driven rules (`{rules.combat_resolution}`) are still verb-driven, fired by their respective system verbs (`{verbs.resolve_combat}`).
