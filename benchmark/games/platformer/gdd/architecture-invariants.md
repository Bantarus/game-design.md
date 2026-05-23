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
  data_behavior_separation:
    kind: architectural_pattern
    rule: "Simulation entities (moth, platforms, ember pickups, checkpoints, lethal regions) are data-only structures with no embedded methods. All simulation logic — jump arc resolution, dash dispatch, glide drain, gravity application, collision response, checkpoint touch, ember pickup — lives in stateless systems that query entity data and produce next-tick data. No simulation logic embedded in renderer, asset pipeline, or input handler. The simulation is a pure function from (input sequence, level data, initial state) to (per-tick state stream)."
    applies_to:
      - "{entities.player_moth}"
      - "{entities.ember_pickup}"
      - "{entities.checkpoint}"
      - "{rules}"
    enforcement: advisory
    severity: warning
  cross_layer_via_events:
    kind: communication
    rule: "The presentation layer (renderer, audio, HUD, particles, camera) observes simulation state and simulation-emitted events; it never calls into the simulation, holds simulation state, or blocks simulation progress. All sim → presentation signals — ember-pickup acquired, checkpoint touched, moth landed, dash issued, death — are emitted as discrete events the presentation layer subscribes to. In a headless run (replay verification, speedrun timing), no presentation layer is attached and the simulation produces identical per-tick state output."
    applies_to:
      - "{loops.flight}"
      - "{states.moth_movement}"
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

Six invariants govern the codebase. Each declares a *property of the generated code*, not a tool used to generate it. The spec explicitly forbids naming engines, frameworks, or renderers here. Each invariant is anchored in a specific claim from the design brief — the trace is in the per-invariant prose below. The brief's "Embergrave ships replay files as a feature" + "speedrunners can verify each other's times" + "60Hz fixed tick regardless of display Hz" together force the engineering posture: a deterministic, headlessly-runnable simulation built from integer state and addressed via events from presentation. The four numeric/determinism/layer invariants and the two architectural-pattern/communication invariants are the engineering shape that posture forces; none of them are declared because the spec has a kind for them.

## Rationale

Per-invariant prose follows. Each `###` heading matches an invariant id in the frontmatter; if you add an invariant to the YAML, add a `###` section here with the same id. Every invariant must carry a **brief trace** sentence — naming the design-brief claim or universal genre necessity that forces this engineering choice. The trace is the audit: an invariant whose trace reduces to "the spec defines this kind" must be cut.

### fixed_point_simulation_state

**Brief trace.** The brief says "Position is stored as integers, not as floating-point — fine enough that the moth feels smooth (one thousandth of a unit per tick of velocity), coarse enough that it's perfectly reproducible across machines." The invariant is the engineering form of that designer commitment.

The platformer cannot ship as a precision-skill game and also use floating-point position. Float position introduces non-deterministic rounding under different compilers, different CPU instruction sets, and different SIMD code paths — meaning the same input sequence on two installs produces different physics outcomes, and replay/leaderboards become fictions. Fixed-point integer state (micro_units = 1/1000 of a world unit) gives the simulation enough resolution for visually-smooth motion at 60Hz while remaining a finite integer domain that round-trips byte-for-byte.

**Why this specifically:** the same family of float-determinism failure the project fought at the cross-engine simulation layer (libm transcendental ULP drift, F-007 / D-016). The lesson applied here: integers don't drift.

**Statically checkable:** any numeric field in the simulation layer whose declared type is `float`/`double`/`real` (rather than `int` with `fixed_point:` annotation) is a violation. The linter scans entity-property declarations and rule-output types.

### fixed_timestep_simulation

**Brief trace.** The brief says "The physics simulation runs at 60 ticks per second, regardless of how fast the display refreshes." A render-coupled simulation would make the same input sequence diverge across hardware — which is the precise feature the brief forbids.

A platformer that updates simulation at render-frame rate gives different physics on a 144Hz monitor vs. a 30Hz one — short jumps on 30Hz can short the same jump on 144Hz, because the rounding-down of dt over many frames diverges. Embergrave commits to a 60Hz simulation tick regardless of display Hz. Render-frame interpolation between simulation ticks gives visual smoothness without coupling the simulation to display rate.

**Advisory at v0.2.0-alpha** because reliable static detection of "is the simulation tick rate-coupled to render?" requires AST analysis at the call-graph level. A future linter check could promote this to `enforcement: lint` once a project-supplied adapter declares the simulation-tick callsite.

### state_not_in_presentation

**Brief trace.** The brief says the cave's lethal regions, the moth's position, the ember meter are simulation truth and the player observes them through the ember's vision cone. Camera, animation frame, particles, and the ember's visual flicker are *how the player sees* the simulation, not *what the simulation is*. If those derived values lived in the simulation, they'd vary across machines (animation timing, particle counts) and break the same-input-same-outcome guarantee the brief commits to.

Statically checkable on a project that follows the recommended layout: scan presentation-layer source files (`implementation_pointers` map under `presentation:`, if declared) for mutations of fields owned by `{states.*}` or `{resources.*}`. Any write triggers the violation.

The carve-out for camera/animation/particles is deliberate — those are *derived* from simulation state, not simulation state proper. A camera that smoothly follows the moth's interpolated position is presentation; the moth's actual position is simulation.

### data_behavior_separation

**Brief trace.** The brief says "the game ships replay files as a feature: every death produces a recorded replay; the player can watch their attempts back, and speedrunners can verify each other's times." Replay verification means a third party can take an input sequence + level data + initial state and reproduce the run — and for speedrun verification specifically, that often runs on a headless server with no renderer, no audio, no display. That use case requires the simulation to be a pure function from (input, level, initial state) to (per-tick state stream), with no method calls into entities that might be entangled with renderer state.

Entities as data-only structures + logic in stateless systems is the engineering posture that makes pure-function simulation tractable. The opposite posture — entities-with-methods that internally call into a graphics or audio subsystem — would either fail in headless mode or force the renderer to exist even when nothing is watching, both of which break the replay-verification feature.

**Why this specifically:** the brief's combination of "input-deterministic" + "ship replay files" + "speedrunners verify times" is what *forces* this. A platformer brief that only said "fun jumps" would not force this invariant; the verifiability requirement is what does. Without that, declaring this invariant would be spec-coverage contamination.

**Advisory** at v0.2.0-alpha. Static detection requires identifying which source files belong to "simulation entities" vs. "systems" vs. "presentation," which depends on project layout conventions. Promotable to `lint` once a project's `implementation_pointers` declare the layers.

### cross_layer_via_events

**Brief trace.** Same brief root as `data_behavior_separation`. The replay-verification use case (headless run, no renderer) means the simulation cannot make synchronous calls into presentation — there is no presentation to call. Conversely, presentation effects in the live game (the ember flicker brightening on a clean dash, dust on landing, the "checkpoint touched" audio cue, the screen-edge vignette dimming with the ember meter) all need to *react to* simulation events. The clean engineering shape is: simulation emits events, presentation subscribes; in headless mode, no subscriber exists and the events vanish without affecting simulation state.

A direct simulation → presentation function call would either (a) crash in headless mode (nothing to call) or (b) require a stub presentation layer that exists only to absorb calls, which complicates the headless build for no gameplay benefit. The event-emission pattern is the cheap way to keep both modes — live with renderer, headless without — using the same simulation binary.

**Why this specifically:** like `data_behavior_separation`, it follows from the brief's replay/verifiability commitment. A platformer brief that only described the live experience would not force this; the headless run does.

**Advisory** at v0.2.0-alpha. Static detection of "does the simulation call into the renderer?" requires symbol-level cross-module analysis. Promotable once layers are declared.

### deterministic_given_input

**Brief trace.** The brief says "Movement is deterministic in the input → physics → outcome sense. Given the same sequence of button presses on the same level, the moth dies at the same place every time." This is the headline invariant — the design-level commitment of the whole simulation posture.

Embergrave ships *replay files* as a feature (every death produces a replay; players can re-watch their attempts; speedrunners can verify times). Replay correctness requires byte-identical state reconstruction from the same input sequence. This is verifiable at runtime — `gdmd verify` adapter runs the same input twice and asserts byte-identical state at every tick.

**Deferred to verify** because static reasoning about reproducibility requires running the code. The verify adapter would record one canary replay (input sequence + expected per-tick state hashes) and assert byte-identity on re-run.

## Open Questions

- Whether to introduce a `numeric_domain` invariant specifically for the ember resource (currently rolled into `fixed_point_simulation_state` because ember is an integer in `[0, 12]`). Argument for: ember has a maximum and the integer domain is naturally bounded; an invariant could declare the bounds. Argument against: the bounds are already in `{resources.ember.min}`/`max`. Currently rolled.
- Whether the simulation tick rate (60Hz) should be an invariant rather than prose in `fixed_timestep_simulation`. Argument for: a hard contract. Argument against: 60Hz is an implementation parameter; the invariant is "fixed, not variable," not "specifically 60." Currently prose.
- Whether `data_behavior_separation` and `cross_layer_via_events` should ratchet to `enforcement: lint` once a project's `implementation_pointers` declare which globs belong to which layer. Both are currently `advisory` because cross-module symbol analysis is non-trivial for the static linter; both have well-defined static checks once the layer map is declarable. A v0.3 candidate.
