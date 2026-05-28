---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-22"
implemented_in: []
invariants:
  gameplay_state_is_integer:
    kind: numeric_domain
    rule: "All gameplay-affecting quantities — hp, attack, speed, cost, gold, damage, critical thresholds, tick number, action-order positions — resolve to integers (or deterministic fixed-point). No simulation arithmetic produces, consumes, or stores a float. Distributions whose sampling theory is float-valued (e.g. {distributions.damage_roll} gaussian) must round half-to-even at apply time so the simulation state remains integer-domain. This is the cross-engine determinism floor: floating-point divergence between Rust and the Blueprint VM is the canonical cause of replay drift, so the spec forbids floats in the simulation hot path."
    applies_to:
      - "{resources.gold}"
      - "{entities.units}"
      - "{rules.tick_resolution}"
      - "{rules.combat_resolution}"
      - "{distributions.action_order}"
      - "{distributions.damage_roll}"
      - "{distributions.critical_hit}"
      - "{distributions.gold_drop}"
    enforcement: lint
    severity: error
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed and identical setup: (a) within a single engine, every encounter produces byte-identical state at every tick — this is the Phase-3 bar; (b) across two engines, both produce the same canonical integer state trajectory — same action sequence, same integer game state at each tick — this is the Phase-4 bar. Byte-identical serialization across engines is explicitly NOT the contract; serialization-format differences would break it even with identical logic. Fallback when per-tick trajectory capture is impractical in a given engine's headless mode: terminal-state + action-sequence equality. The deterministic action order is the load-bearing piece."
    applies_to:
      - "{distributions.action_order}"
      - "{distributions.damage_roll}"
      - "{distributions.critical_hit}"
      - "{distributions.gold_drop}"
    enforcement: verify
    severity: error
  units_act_only_when_alive:
    kind: architectural_pattern
    rule: "A unit in state {states.unit_lifecycle.dead} or {states.unit_lifecycle.stunned} produces no actions on its tick."
    applies_to:
      - "{states.unit_lifecycle}"
      - "{rules.tick_resolution}"
    enforcement: advisory
    severity: warning
---

## Tokens

Three invariants. The two load-bearing ones (`gameplay_state_is_integer`, `deterministic_given_seed`) are the contract that makes Lockstep's replay-share feature — and the v0.2 cross-engine neutrality proof — actually work. Renamed from `damage_is_integer` at v0.2.0-alpha when the scope broadened from "damage + hp + gold" to all simulation quantities (per the v0.2 kickoff addendum's tightened determinism bar).

## Rationale

### gameplay_state_is_integer

Every gameplay-affecting quantity is integer-domain (or deterministic fixed-point). The content-schema `units.md` constrains `hp`, `attack`, `speed`, `cost` to integers. The gaussian `{distributions.damage_roll}` rounds half-to-even at apply, never at sample time, so the rounding boundary is fixed and predictable. The `lint` enforcement currently checks `effects[].amount` integerness in `content/units/*.yaml`; the broader scope (entity properties, rule outputs, distribution rounding semantics) is the codebase contract that Phase 2 will exercise end-to-end and Phase 3's adapter will assert against.

**Why broaden in v0.2.** Cross-engine determinism is *impossible* with floats. Rust's `f64`, the Blueprint VM's float ops, and any transcendental math all differ subtly in rounding and order-of-operations. Two engines running the same seed will diverge within a few hundred ticks if the simulation is float-domain. Integer-only closes that source. A visual graph engine (Phase 4's Unreal Blueprints target) makes a stray float node easier to introduce and harder to spot than typed Rust — the invariant declared here is what gives reviewers something concrete to point at.

### deterministic_given_seed

Two bars at two scales:

- **Within a single engine (Phase 3):** byte-identical state at every tick. The verify adapter runs the same encounter twice and diffs the per-tick snapshot. Any difference is a non-determinism bug in that engine's implementation.
- **Across two engines (Phase 4):** identical canonical integer state trajectory. Same action order, same integer game state at each tick, in the engine-neutral canonical form. Byte-identical serialization across engines is NOT the bar — different engines serialize state objects differently even when the logic is identical. The trajectory equality form decouples *what the simulation computes* from *how a given engine writes it to disk*.
- **Fallback:** if per-tick trajectory capture proves impractical in a given engine's headless mode, terminal-state + action-sequence equality is an acceptable degradation. Still a strong spec-compliance claim, just weaker than full trajectory identity. Use it only when full instrumentation is genuinely unavailable.

**Why:** the entire replay-share feature lives or dies on (a). The cross-engine neutrality claim — the v0.2 deliverable — lives or dies on (b). A regression in either is a launch blocker.

### units_act_only_when_alive

Advisory — there's no clean static check. The reminder is for code review: when a unit's turn comes up in the deterministic order, the tick resolver must consult `{states.unit_lifecycle}` before invoking its action.

**Why:** v0.0.3 internal had a regression where stunned units still attacked. The state check fixes it; the invariant prevents regression.
