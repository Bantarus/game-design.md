# Addendum to the v0.2 Kickoff — Engine Selection & Determinism Bar

> Apply alongside `game-design-md-v0.2-kickoff.md`. This **supersedes** that doc's "Engine choices" section and every engine-B reference in the spine and in Phase 4. It also consolidates a determinism refinement that was agreed verbally at the Phase 1 checkpoint but never written down. Where this addendum and the kickoff conflict, **this addendum wins.**

## 1. Engine A — locked

Engine A is the **`xtreme` engine (built on Bevy ECS)**. This is real dogfooding against the harness games will actually ship in. Rust, compiled, data-oriented, ECS.

## 2. Engine B — corrected to Unreal Blueprints

The kickoff named TypeScript as engine B. **TypeScript is a simulation host, not a game engine — discard it.** Engine B is **Unreal Engine Blueprints.**

The decision criterion is *paradigmatic distance from xtreme-on-Bevy-ECS*, and the two obvious Unreal-adjacent alternatives are not equivalent under it:

- **Unity DOTS is rejected.** DOTS is itself a data-oriented ECS. DOTS-vs-xtreme is ECS-vs-ECS — the same paradigm twice. The `data_behavior_separation` invariant maps trivially to both, so a clean Phase 4 on DOTS would prove only "the spec works in two ECS engines," the weak form of the neutrality claim, and would teach us nothing.
- **Unreal Blueprints is selected.** Visual dataflow over a GC'd actor/object model — genuinely far from Rust ECS. This is where neutrality is actually stressed.

## 3. Engine B's purpose — reframed

Engine B is no longer just "a maximally different paradigm." Blueprints accrete design into the node graph over time; the graph becomes a *de facto* design document. That makes Unreal the **hardest** environment in which to keep `game-design.md` as the single source of truth — and therefore the most valuable place to prove it.

**The Phase 4 objective for engine B is therefore: force the Blueprint graph to be a pure *consumer* of the spec.** Logic is realized in nodes; every design decision — numbers, rules, balance, state transitions — stays in the `.md` and the graph points back at it via `implemented_in:`. No design value originates in the graph. If you can hold that line in the engine most prone to absorbing design into itself, that is a strong and novel anti-drift result, not just a neutrality checkmark.

## 4. Determinism bar — corrected and tightened

This consolidates the refinement agreed at the Phase 1 checkpoint (verbal only until now) and adds the Blueprint-specific consequence.

- **Integer / fixed-point simulation math is now a HARD requirement for tick-combat, not advisory.** Promote the `numeric_domain` invariant's scope to *all* gameplay-affecting quantities for this example, `enforcement: lint`. Cross-engine determinism is impossible with floats — different rounding and transcendental implementations between Rust and the Blueprint VM guarantee divergent replays that will masquerade as spec bugs. A visual graph makes a stray float node *easier to introduce and harder to spot* than typed Rust, so stay vigilant.
- **Phase 4 cross-engine bar is corrected from "byte-identical replay hash" to "identical canonical integer state trajectory."** Byte-identical serialization across two engines is a red herring — serialization-format differences break it even with identical logic. What you prove instead: both engines, given the same seed, walk the *same sequence of actions and the same integer game state at each tick*.
- **Within a single engine (Phase 3), byte-identical replay still applies** — there it is the correct determinism check.
- **Fallback:** if per-tick trajectory capture proves impractical in Unreal's headless mode, *terminal-state + action-sequence equality* is an acceptable degradation — weaker than full trajectory identity, still a strong spec-compliance claim. Use it only if the full trajectory genuinely can't be instrumented; don't reach for it preemptively.

## 5. Verify adapter — cost note for engine B

The Unreal verify adapter is materially heavier than the Bevy one: commandlet / `-nullrhi` / automation harness rather than a quick headless Bevy run. Budget for it as real engineering, and stand the Unreal build up as a headless deterministic sim early — the adapter depends on it.

## 6. The finding to watch in Phase 4

Engine A *is* ECS, so `data_behavior_separation` maps to it for free. Engine B is the real test: **does the architecture invariant survive in a non-ECS, actor-based, visual-dataflow engine — or was it ECS smuggled in under a neutral name?** If a Blueprint implementation can honor "data-only structures, logic in stateless graphs that query them" without being a formal ECS, the invariant is genuinely neutral. If it can't, that is a first-class finding for `docs/v0.2-findings.md`, not a failure to hide.

## 7. Unchanged invariant

The `gdd/` tree still names **no** engine. Both `xtreme` and Unreal live only under `examples/tick-combat/impl/<engine>/`. Pointers go one direction: spec → nothing, impl → spec. This binds harder for Unreal precisely because its native idiom resists it.
