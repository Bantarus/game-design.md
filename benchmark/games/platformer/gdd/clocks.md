---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/embergrave/clocks/**/*"]
clocks:
  physics:
    mode: continuous
    rate: { hz: 60 }
    drives:
      - "{rules.physics_tick}"
    status: draft
    implemented_in: ["src/embergrave/clocks/physics.py"]
---

## Tokens

This file owns the `clocks` namespace for Embergrave. The single clock `{clocks.physics}` drives `{rules.physics_tick}` at 60 Hz (the fixed-timestep simulation; see `{invariants.fixed_timestep_simulation}`).

## Rationale

**`{clocks.physics}` lifts the simulation tick out of the verb namespace.** Embergrave's per-frame physics simulation has no natural player-verb to attach to — the simulation advances every tick (60 Hz) regardless of input. Earlier modeling used a synthetic `verbs.advance_tick` whose sole purpose was to satisfy the spec's verb-triggers-rule pattern; F-010's v0.3 resolution (spec §4.7) makes time-passage a first-class primitive distinct from player verbs. The semantics are unchanged — `{rules.physics_tick}` still fires once per 60 Hz tick — but the contract is now structural rather than a "verb the player never issues."

**Rate is `hz: 60`** — matches the fixed-timestep contract declared in `{invariants.fixed_timestep_simulation}`. Either `hz:` or `period_ms:` would be legal per spec §4.7; `hz: 60` is the most natural expression of the 60 Hz frequency.

**`drives:` lists exactly one rule.** Embergrave's only clock-driven rule is `{rules.physics_tick}`. The other rules (input-resolution rules: `{rules.jump_resolution}`, `{rules.dash_resolution}`, `{rules.glide_resolution}`; system-resolution rules: `{rules.ember_collection}`, `{rules.checkpoint_activation}`, `{rules.respawn}`, `{rules.level_setup}`, `{rules.level_completion}`, `{rules.expedition_completion}`) are still verb-driven, fired by their respective input verbs or system events.
