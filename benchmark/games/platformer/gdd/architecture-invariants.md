---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/embergrave/**/*"]
invariants:
  fixed_point_simulation_state:
    kind: numeric_domain
    rule: "All simulation-layer position, velocity, acceleration, and time quantities use fixed-point integer representation (micro_units = 1/1000 world unit; tick = 1/60 second). Floating-point is forbidden in the simulation layer. Presentation layer renders by integer-to-float conversion; the simulation never sees the converted floats."
    applies_to:
      - "{entities.player_moth}"
      - "{entities.ember_pickup}"
      - "{entities.checkpoint}"
    enforcement: lint
    severity: error
  fixed_timestep_simulation:
    kind: architectural_pattern
    rule: "The simulation advances at a fixed timestep of 1 tick = 1/60 second, independent of render frame rate. Input is buffered between ticks and resolved at tick boundaries. Render frames may interpolate between simulation states for visual smoothness but never advance simulation state."
    applies_to:
      - "{loops.flight}"
    enforcement: advisory
    severity: warning
  data_behavior_separation:
    kind: architectural_pattern
    rule: "Entities are composed of data-only structures; movement, collision, and ember-resource logic live in stateless systems that query them. No gameplay rules inside presentation/render code."
    applies_to:
      - "{entities.player_moth}"
      - "{entities.ember_pickup}"
      - "{entities.checkpoint}"
    enforcement: advisory
    severity: warning
  state_not_in_presentation:
    kind: layer_boundary
    rule: "Persistent simulation state (moth_movement, level_progress, position/velocity, ember/hp values) is owned by the simulation layer; the presentation layer reads but never owns or mutates it. Camera position, animation frame, and visual-effect particles MAY live in presentation."
    applies_to:
      - "{states.moth_movement}"
      - "{states.level_progress}"
      - "{resources.hp}"
      - "{resources.ember}"
    enforcement: lint
    severity: error
  cross_layer_via_events:
    kind: communication
    rule: "Communication between simulation and presentation layers is one-way asynchronous events emitted by the simulation; presentation never holds direct references to simulation objects."
    enforcement: advisory
    severity: warning
  deterministic_given_input:
    kind: determinism
    rule: "Given a fixed sequence of input events (each timestamped to a simulation tick), every simulation state at every tick is reproducible byte-for-byte. There is no internal RNG in the simulation path; {distributions.ember_flicker_jitter} is cosmetic-only and lives in presentation. Two replays of the same input sequence produce byte-identical simulation state at every tick."
    applies_to:
      - "{entities.player_moth}"
      - "{states.moth_movement}"
    enforcement: verify
    severity: error
---

## Tokens

Six invariants govern the codebase. Each declares a *property of the generated code*, not a tool used to generate it. The spec explicitly forbids naming engines, frameworks, or renderers here.

## Rationale

Per-invariant prose follows. Each `###` heading matches an invariant id in the frontmatter; if you add an invariant to the YAML, add a `###` section here with the same id.

### fixed_point_simulation_state

The platformer cannot ship as a precision-skill game and also use floating-point position. Float position introduces non-deterministic rounding under different compilers, different CPU instruction sets, and different SIMD code paths — meaning the same input sequence on two installs produces different physics outcomes, and replay/leaderboards become fictions. Fixed-point integer state (micro_units = 1/1000 of a world unit) gives the simulation enough resolution for visually-smooth motion at 60Hz while remaining a finite integer domain that round-trips byte-for-byte.

**Why this specifically:** the same family of float-determinism failure the project fought at the cross-engine simulation layer (libm transcendental ULP drift, F-007 / D-016). The lesson applied here: integers don't drift.

**Statically checkable:** any numeric field in the simulation layer whose declared type is `float`/`double`/`real` (rather than `int` with `fixed_point:` annotation) is a violation. The linter scans entity-property declarations and rule-output types.

### fixed_timestep_simulation

A platformer that updates simulation at render-frame rate gives different physics on a 144Hz monitor vs. a 30Hz one — short jumps on 30Hz can short the same jump on 144Hz, because the rounding-down of dt over many frames diverges. Embergrave commits to a 60Hz simulation tick regardless of display Hz. Render-frame interpolation between simulation ticks gives visual smoothness without coupling the simulation to display rate.

**Advisory at v0.2.0-alpha** because reliable static detection of "is the simulation tick rate-coupled to render?" requires AST analysis at the call-graph level. A future linter check could promote this to `enforcement: lint` once a project-supplied adapter declares the simulation-tick callsite.

### data_behavior_separation

Advisory because no fully reliable static check exists for "is this logic in the wrong layer?" The reminder is for human/agent review: an entity is plain data; logic that *transforms* an entity belongs in a system (`rules.*` when those are declared at status >= prototyped).

The platformer has a specific failure mode this invariant blocks: animation systems that "predict" the next physics tick to interpolate visually. If the animation system runs simulation logic ("if velocity_y > 0 then play falling_anim"), the visual-prediction can desync from actual physics — the moth visibly enters the falling animation a frame before it actually starts falling, breaking the "what I see is what I commit to" pillar.

### state_not_in_presentation

Statically checkable on a project that follows the recommended layout: scan presentation-layer source files (`implementation_pointers` map under `presentation:`, if declared) for mutations of fields owned by `{states.*}` or `{resources.*}`. Any write triggers the violation.

The carve-out for camera/animation/particles is deliberate — those are *derived* from simulation state, not simulation state proper. A camera that smoothly follows the moth's interpolated position is presentation; the moth's actual position is simulation.

### cross_layer_via_events

Advisory at v0.2.0-alpha because cross-layer call topology is hard to lint without an AST. A clean adapter for `gdmd verify` would observe event traffic and assert no direct references; that promotes this to `enforcement: verify` in a later version.

The platformer's specific application: the simulation emits `{events.jump_pressed}` when a jump becomes airborne, and the presentation listens to play the jump animation. The presentation does NOT poll `moth_movement.state == airborne` directly — it reacts to the transition event. This makes the presentation layer engine-replaceable.

### deterministic_given_input

The headline invariant for the platformer. Embergrave ships *replay files* as a feature (every death produces a replay; players can re-watch their attempts; speedrunners can verify times). Replay correctness requires byte-identical state reconstruction from the same input sequence. This is verifiable at runtime — `gdmd verify` adapter runs the same input twice and asserts byte-identical state at every tick.

**Deferred to verify** because static reasoning about reproducibility requires running the code. The verify adapter would record one canary replay (input sequence + expected per-tick state hashes) and assert byte-identity on re-run.

## Open Questions

- Whether to introduce a `numeric_domain` invariant specifically for the ember resource (currently rolled into `fixed_point_simulation_state` because ember is an integer in `[0, 12]`). Argument for: ember has a maximum and the integer domain is naturally bounded; an invariant could declare the bounds. Argument against: the bounds are already in `{resources.ember.min}`/`max`. Currently rolled.
- Whether the simulation tick rate (60Hz) should be an invariant rather than prose in `fixed_timestep_simulation`. Argument for: a hard contract. Argument against: 60Hz is an implementation parameter; the invariant is "fixed, not variable," not "specifically 60." Currently prose.
