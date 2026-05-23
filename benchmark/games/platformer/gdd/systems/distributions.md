---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/embergrave/distributions/**/*"]
distributions:
  ember_flicker_jitter:
    type: gaussian
    mean: 0
    stddev: 50
    clamp: [-200, 200]
    output_domain: real
    seed: nondeterministic
    status: draft
    implemented_in: ["src/embergrave/presentation/ember_flicker.py"]
---

## Tokens

A single distribution. By design.

## Rationale

**Embergrave has effectively no gameplay RNG.** This is not an oversight; it is the platformer's commitment to "every jump is a commitment" (`{pillars}`) and to deterministic replay (`{invariants.deterministic_given_input}`). Every outcome in the simulation layer must be reproducible from input alone: same inputs → same physics → same death-or-checkpoint outcome.

**`ember_flicker_jitter` is the only declared distribution and it is cosmetic-only.** It samples a Gaussian-shaped jitter (mean 0, stddev 50, clamped ±200) added to the rendered ember-light radius for visual variety — the ember flickers in the presentation layer to feel alive without affecting gameplay state. Critical properties:

- `output_domain: real` (not integer): the jitter is a render-time visual effect, not a state-affecting roll. The presentation layer can use any continuous distribution; the simulation layer never reads this value.
- `seed: nondeterministic` (not `deterministic_per_run`): explicitly non-cross-engine-deterministic — different installs can flicker differently without breaking replay. This is the carve-out the spec permits for cosmetic uses (§4.7's D-016 framing about gaussian being reserved for non-cross-engine cosmetic noise).
- `implemented_in:` points at the *presentation* layer (`src/embergrave/presentation/...`), not the simulation. The layer boundary invariant (`{invariants.state_not_in_presentation}`) is satisfied because the jitter is presentation-owned and produces no simulation-state mutation.

**Why declare it at all?** Without the declaration, any agent reading the spec would either invent a different visual-jitter solution (likely with the wrong determinism property — accidentally seeding from a gameplay clock, breaking replay) or omit the visual flicker entirely (the ember feeling dead). The declaration anchors the design intent and makes the cosmetic-only contract explicit.

**The contrast with deckbuilder / tick-combat is intentional.** Those games' surfaces are dominated by named distributions (card_draw, damage_roll, critical_hit, gold_drop, action_order). Embergrave's surface is dominated by *physics* (fixed-point integer arithmetic) and *state* (FSM transitions on input events). The probabilistic surface of the spec is deliberately underexercised here — Embergrave is the fresh game that tests "does the standard help an agent build a non-probabilistic game?" (see `docs/v0.2-phase5-pre-registration.md` §"Task set" for the deliberate-low-RNG framing).

If a future content addition needs a stochastic outcome (e.g. a "wind gust" hazard that pushes the moth randomly), it would be declared here as a new named distribution with `output_domain: integer` (state-affecting) and `seed: deterministic_per_run` (replay-compatible). Such a hazard does not currently exist in the design and would be a pillar-rejecting addition — every gust would break the "every jump is a commitment" contract because the player could not predict the outcome of a committed input.

## Open Questions

- Whether to declare a `dust_particle_jitter` distribution analogous to `ember_flicker_jitter` for background dust-mote effects. Currently no — visual particle systems are a presentation-layer implementation detail and don't merit a top-level distribution declaration unless they affect gameplay-state via collision (which they don't).
- Whether to ratchet `ember_flicker_jitter` to `discrete_sum` (integer-native) at some point to eliminate the only remaining floating-point declaration in the tree. Argument for: spec purity. Argument against: it's cosmetic, output_domain: real is permitted for cosmetic, and the discrete_sum form would be more verbose for zero gameplay benefit. Currently no.
