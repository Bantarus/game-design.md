---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/ember_ascent/**/*.py"]
invariants:
  damage_is_integer:
    kind: numeric_domain
    rule: "All damage, health, block, and burn-stack quantities resolve to integers. Continuous distributions (e.g. {distributions.damage_roll}) must clamp and round at the point of application."
    applies_to:
      - "{resources.health}"
      - "{resources.block}"
      - "{rules.damage_resolution}"
    enforcement: lint
    severity: error
  data_behavior_separation:
    kind: architectural_pattern
    rule: "Entities are composed of data-only structures; logic lives in stateless systems that query them. No gameplay rules inside presentation/render code."
    applies_to:
      - "{entities.player}"
      - "{entities.cards}"
      - "{entities.enemies}"
    enforcement: advisory
    severity: warning
  state_not_in_presentation:
    kind: layer_boundary
    rule: "Persistent game state (card_lifecycle, enemy_lifecycle, resource values, RNG seed) is owned by the simulation layer; the presentation layer reads but never owns or mutates it."
    applies_to:
      - "{states.card_lifecycle}"
      - "{states.enemy_lifecycle}"
    enforcement: lint
    severity: error
  cross_layer_via_events:
    kind: communication
    rule: "Communication between simulation and presentation layers is one-way asynchronous events emitted by the simulation; presentation never holds direct references to simulation objects."
    enforcement: advisory
    severity: warning
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed, every draw from {distributions.*} is reproducible. Two runs with the same seed and the same input verbs produce byte-identical state at every step."
    applies_to:
      - "{distributions.card_draw}"
      - "{distributions.damage_roll}"
      - "{distributions.critical_hit}"
      - "{distributions.enemy_pack_size}"
      - "{distributions.reward_choice}"
    enforcement: verify
    severity: error
---

## Tokens

Five invariants govern the codebase. Each declares a *property of the generated code*, not a tool used to generate it. The spec explicitly forbids naming engines, frameworks, or renderers here.

## Rationale

Per-invariant prose follows. Each `###` heading matches an invariant id in the frontmatter; if you add an invariant to the YAML, add a `###` section here with the same id.

### damage_is_integer

Statically checkable: any numeric field that resolves to a non-integer value at the moment of damage application is a violation. The `{distributions.damage_roll}` is a clamped Gaussian; the *resolver* rounds half-to-even at the boundary. If a future card or relic introduces fractional damage in prose, the linter flags it.

**Why:** integer damage keeps balance human-readable (a card hits for "6", not "5.87"). Fractional damage also breaks the equality assertions in `gdd/verification.md` behavioral-alignment tests.

### data_behavior_separation

Advisory because no fully reliable static check exists for "is this logic in the wrong layer?" The reminder is for human/agent review: an entity is plain data; logic that *transforms* an entity belongs in a system (`rules.*`).

**Why:** in v0.3 we shipped a regression where one card's effect was inlined into a render hook. Burn ticks doubled on screen. Fixed by lifting the effect into `{rules.damage_resolution}`.

### state_not_in_presentation

Statically checkable on a project that follows the recommended layout: scan presentation-layer source files (`implementation_pointers` map under `presentation:`, if declared) for mutations of fields owned by `{states.*}` or `{resources.*}`. Any write triggers the violation.

**Why:** if presentation owns state, the game is no longer deterministic given seed — the renderer's frame rate becomes a hidden input. This invariant exists to prevent exactly that.

### cross_layer_via_events

Advisory in v0.1.1 because cross-layer call topology is hard to lint without an AST. A clean adapter for `gdmd verify` (see `gdd/verification.md`) would observe event traffic and assert no direct references; that promotes this to `enforcement: verify` in a later version.

**Why:** an event boundary is the simplest decoupling that survives engine swaps. The spec is engine-neutral; this invariant is what makes the *implementation* engine-neutral too.

### deterministic_given_seed

Deferred to `verify` because static reasoning about reproducibility requires running the code. The verify adapter (`adapters.default` in `gdd/verification.md`) runs the same seed twice and asserts byte-identical state at each step.

**Why:** Ember Ascent ships *seed-shareable* runs as a feature; without this invariant, the feature is a lie. A regression here is a launch blocker, hence `severity: error`.

## Open Questions

- Whether to promote `cross_layer_via_events` to `enforcement: verify` in v0.1.2 (requires an adapter that observes events).
- Whether to add a `numeric_domain` invariant for *burn stacks* specifically (currently rolled into `damage_is_integer`).
