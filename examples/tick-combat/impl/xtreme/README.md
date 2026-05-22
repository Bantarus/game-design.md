# tick-combat / xtreme implementation (Engine A)

> Engine-A (xtreme on Bevy ECS, Rust) implementation of the `tick-combat` spec
> tree at `examples/tick-combat/`. **Per the v0.2 kickoff addendum (D-007)
> this implementation contains no design value** — every number, rule, balance
> target, and state transition lives in the sibling `gdd/` tree. Code here only
> realizes the spec.

## "xtreme" note

At v0.2.0-alpha this crate uses **plain `bevy_ecs` only** (no rendering, no
`bevy` umbrella). That's the headless-deterministic floor xtreme is built on;
xtreme-specific primitives (the harness games will ship with) slot in as they
mature without changing the relationship between this code and the `gdd/`
tree. The directory is named `xtreme/` to reserve the path; readers who clone
this repo see a clean Bevy ECS implementation that follows the xtreme stance:
data-oriented ECS, headless-runnable, deterministic-given-seed.

## Reading order (from cold)

1. `../../gdd/architecture-invariants.md` — the codebase contract this crate
   must satisfy. `gameplay_state_is_integer` and `deterministic_given_seed`
   are load-bearing.
2. `../../gdd/mechanics.md` — entities, verbs, resources, states, events.
3. `../../gdd/systems/distributions.md` — the four named distributions.
4. `src/lib.rs` here — module map below.
5. `src/main.rs` — the headless harness entry point.

## Module map

| Module | Realizes |
| --- | --- |
| `src/components.rs` | `{entities.units}`, `{entities.player}` — data-only components. |
| `src/resources.rs` | `{resources.gold}` — Bevy `Resource` types for global state. |
| `src/distributions.rs` | The four `{distributions.*}` — deterministic, gaussian, uniform, weighted — fed by a shared ChaCha20 PRNG keyed by encounter seed. |
| `src/state.rs` | `{states.unit_lifecycle}`, `{states.combat_phase}` — state-machine types + `{events.*}` enum. |
| `src/rules.rs` | `{rules.tick_resolution}`, `{rules.combat_resolution}`. |
| `src/loops.rs` | `{loops.tick}` schedule wiring. |
| `src/lib.rs` | re-exports + the `Simulation` type the verify adapter (Phase 3) will drive. |
| `src/main.rs` | CLI: `tick-combat --seed <u64> [--ticks <n>]`. |

## Build & run

```bash
cd examples/tick-combat/impl/xtreme
cargo build
cargo run -- --seed 12345 --ticks 200
```

## Determinism contract

- All gameplay quantities are `i32` (or smaller integer types). No `f32`/`f64`
  storage in components or resources. The gaussian sampling is the *only* path
  on which a float touches the simulation; it is rounded via
  `f64::round_ties_even` *at apply* (`{rules.tick_resolution}`), per D-010 and
  `{distributions.damage_roll}.round_mode: half_to_even`.
- The shared PRNG is `rand_chacha::ChaCha20Rng` keyed by the encounter seed.
  Identical seed → identical state at every tick (the Phase-3 bar). The
  Phase-4 bar (integer trajectory equality across engines) is the same
  contract observed from the outside.
- `tick_resolution` is a single function; no implicit ordering from Bevy
  scheduling parallelism affects determinism.

## Status

- Scaffold: prototyped. The Cargo skeleton builds; module shells exist.
- End-to-end fixed-seed session: pending Phase 2 finish.
- Verify adapter: Phase 3 (separate crate, not here).
