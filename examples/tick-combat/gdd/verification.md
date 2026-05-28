---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: implemented
last_verified: "2026-05-22"
verify_targets:
  # Headline behavioral_alignment — the locked seed-12345 demo encounter.
  # The adapter runs the simulation at seed 12345, writes a canonical JSONL
  # trajectory (§9.5.5) to --trajectory, and `gdmd verify` checks byte-identity
  # against the golden fixture. The negative_control (seed 99999) catches an
  # adapter that ignores --seed — the trajectory at 99999 MUST differ.
  - axis: behavioral_alignment
    target: "{loops.tick}"
    seed: 12345
    expect:
      trajectory:
        matches_golden: ./impl/xtreme/tests/golden_seed_12345.jsonl
    negative_control:
      seeds: [99999]
      expect: { trajectory_diverges_from_primary: true }
  # build_health — adapter built and invoked without errors.
  - axis: build_health
    expect: { builds: true, unresolved_refs: 0 }
adapters:
  default:      "./tools/verify-adapter"          # engine A — xtreme / Bevy ECS / Rust
  godot:        "./tools/verify-adapter-godot"    # engine B — Godot 4 / GDScript (Phase 4 substitute for Unreal)
  presentation: null
trajectory:
  unit: tick
  schema:
    tick:        { type: integer, minimum: 0 }
    phase:       { enum: [setup, ticking, resolved] }
    gold:        { type: integer, minimum: 0 }
    units:
      type: array
      sort_by: [side, deploy_order]
      items:
        id:           { type: string }
        side:         { enum: [player, enemy] }
        deploy_order: { type: integer, minimum: 0 }
        hp:           { type: integer, minimum: 0 }
        lifecycle:    { enum: [alive, stunned, dead] }
---

## Tokens

Two `verify_targets` — one `behavioral_alignment` (trajectory match against the locked golden, with a negative-control seed) and one `build_health`. The headline `behavioral_alignment` IS the cross-engine integer-trajectory contract (D-009): both this engine (xtreme/Bevy ECS) and a future Unreal Blueprint port at Phase 4 must produce byte-identical JSONL given seed 12345.

The `trajectory:` block declares the per-game canonical JSONL schema (§9.5.5). At v0.2.0-alpha the schema body is advisory — `verify` checks byte-identity against the golden, not field-by-field validation. A v0.3 lint rule will validate every trajectory line against the schema.

## Rationale

`{invariants.deterministic_given_seed}` is declared `enforcement: verify`, so the lint pass is silent and the verify adapter is responsible for catching regressions. The contract (§9.5.6) invokes the adapter as:

```
./tools/verify-adapter --target '{loops.tick}' --seed 12345 \
  --trajectory <path> --max-steps 500
```

The adapter writes the canonical JSONL trajectory to `<path>` and emits a single-result `VerifyResult` JSON object to stdout. `gdmd verify` reads the trajectory and compares to `./impl/xtreme/tests/golden_seed_12345.jsonl`. For the negative_control invocation, `gdmd verify` substitutes seed `99999`, captures that trajectory, and asserts byte-divergence from the primary.

**Why integer state.** The `gameplay_state_is_integer` invariant (D-009) keeps the trajectory PRNG-portable. ChaCha20 produces canonical real-valued samples; xtreme rounds (`half_to_even`) at apply-time per D-010; the resulting integer state is the cross-engine bar. Unreal Blueprints will use the same PRNG, sample → clamp continuous → round → integer clamp, and emit the same JSONL.

**Why a negative control.** Without it, an adapter that hard-codes a trajectory and ignores `--seed` would pass the primary trajectory match vacuously. The negative_control seeds must produce a different trajectory — that's the spec-level mechanism (§9.5.7) forcing the adapter to actually respond to its input.

## Open Questions

- The session-based targets (`median_ticks_per_combat`, `win_rate_neutral_formation`) defined in `gdd/economy-balance.md` were experimental verify targets in v0.1.1. They are NOT exercised by the v0.2 adapter — adding multi-seed statistical aggregation is a v0.3 concern. The targets remain valid balance specs; they're just not in `verify_targets` until the adapter supports the `sessions:` field.
- Cross-engine bar (D-009, Phase 4): Unreal Blueprints will produce its own `VerifyResult` against the *same* golden fixture. If the trajectories diverge, the divergence is either a spec ambiguity (to be surfaced as a new entry in `docs/v0.2-phase2-spec-ambiguities.md`) or an engine-side bug — never a per-engine acceptable difference.

## Adapter location

- **Adapter (project-level entry point):** [`./tools/verify-adapter`](../tools/verify-adapter) — a thin shell wrapper that `gdmd verify` invokes per `adapters: default:`. It builds the Rust binary on demand.
- **Engine-A implementation (xtreme/Bevy ECS):** [`./impl/xtreme/src/bin/verify_adapter.rs`](../impl/xtreme/src/bin/verify_adapter.rs) — the Rust binary that actually runs the simulation and emits canonical JSONL + VerifyResult.
- **Locked golden fixture:** [`./impl/xtreme/tests/golden_seed_12345.jsonl`](../impl/xtreme/tests/golden_seed_12345.jsonl) — 24 lines, terminal tick 23, terminal gold 26.
