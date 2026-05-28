---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/clocks/**/*.py"]
clocks:
  tick:
    mode: continuous
    rate: { hz: 4 }
    drives: ["{rules.tick_resolution}"]
    status: draft
    implemented_in: ["src/clocks/tick.py"]
---

## Tokens

One clock: `tick`, continuous mode at 4 Hz (one tick every 250ms). It drives
`{rules.tick_resolution}` — the rule that fires per tick to resolve combat.

## Rationale

**4 Hz as the tick rate.** A typical auto-battler tick is in the 2-8 Hz band
— fast enough that combat feels responsive, slow enough that the player can
read what's happening. Tune to fit your game's feel.

**Continuous mode.** Time passes regardless of player input — this is what
makes it an *auto*-battler. If your game pauses between rounds, that's a UX
layer above the clock, not a clock change.

**Cross-engine determinism.** The clock advances in fixed-rate ticks; both
engines (whatever they are) MUST tick at the same wall-clock rate AND
produce identical integer trajectories per tick. The verify-adapter
machinery (§9.5) is how this gets validated.
