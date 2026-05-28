---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/clocks/**/*.py"]
clocks:
  physics:
    mode: continuous
    rate: { hz: 60 }
    drives: ["{rules.physics_tick}"]
    status: draft
    implemented_in: ["src/clocks/physics.py"]
---

## Tokens

One clock: `physics`, continuous mode at 60 Hz. It drives `{rules.physics_tick}`
— the rule that fires per frame to advance position, velocity, and collision.

## Rationale

**60 Hz fixed timestep is the precision-platformer convention.** Variable
timesteps make movement feel different on different hardware; fixed timesteps
make the game's feel reproducible — important for speedrunning and replay.

**The clock IS the game's heartbeat.** Player input is sampled per-frame but
acted on during the physics tick; rendering can run at a different rate
(typically display refresh) but never affects gameplay state.
