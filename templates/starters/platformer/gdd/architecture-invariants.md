---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/invariants/**/*.py"]
invariants:
  gameplay_state_is_integer:
    kind: numeric_domain
    rule: "Gameplay state (position, velocity, lives) resolves to integers. Sub-pixel precision is internal; gameplay-visible state is integer-valued."
    applies_to: ["{resources}", "{states.player_state}"]
    enforcement: lint
    severity: error
  fixed_timestep_physics:
    kind: architectural_pattern
    rule: "Physics integration runs at a fixed timestep (60 Hz). Variable timesteps that depend on render rate are forbidden — they make movement feel different on different hardware."
    applies_to: ["{clocks.physics}"]
    enforcement: advisory
    severity: warning
  deterministic_given_seed:
    kind: determinism
    rule: "Given identical input sequence and identical seed, the player trajectory is byte-identical. Replays reproduce the original attempt."
    applies_to: ["{distributions}", "{distributions.hazard_variation}", "{entities.levels}"]
    enforcement: verify
    severity: error
---

## Tokens

Three invariants. The fixed_timestep_physics invariant is the load-bearing
one for movement feel; the deterministic invariant is what makes replays
honest.
