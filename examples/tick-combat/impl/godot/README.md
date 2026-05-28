# tick-combat — Godot 4 / GDScript reference implementation (engine B)

Engine-B reference implementation of [`examples/tick-combat/`](../../) per the v0.2 kickoff addendum. **Substituted for Unreal Blueprints** at Phase 4 — see [docs/v0.2-findings.md F-006](../../../../docs/v0.2-findings.md) for the substitution rationale and what it preserves vs loses.

## Run

```bash
# From examples/tick-combat/
./tools/verify-adapter-godot --target '{loops.tick}' --seed 12345 \
    --trajectory /tmp/godot_traj.jsonl
```

Requires Godot 4.x at `~/.local/bin/godot` or on `$PATH`. The shell wrapper auto-locates.

Implements spec §9.5.6 invocation contract:

```
verify-adapter-godot --target <token-ref> --seed <int>
                     [--trajectory <path>] [--max-steps <int>]
```

Emits a `VerifyResult` JSON object to stdout; writes canonical JSONL trajectory (§9.5.5) to `--trajectory` when supplied.

## Architecture

| File | Realizes | Notes |
| --- | --- | --- |
| [`project.godot`](project.godot) | Godot project file | Minimal: name + features. No scenes. |
| [`verify_adapter.gd`](verify_adapter.gd) | spec §9.5.6 CLI entry point | `SceneTree` subclass; parses args, runs the sim, emits result + trajectory. |
| [`src/components.gd`](src/components.gd) | `{entities.units}` + `Side` / `Lifecycle` / `UnitRole` enums | **Pure data** — D-008 §6 audit: no methods on Unit beyond `_init` and `clone`. |
| [`src/state.gd`](src/state.gd) | `{states.combat_phase}` + `{states.unit_lifecycle}` transitions | Static functions; no state held on the class. |
| [`src/distributions.gd`](src/distributions.gd) | `{distributions.*}` | Wraps Godot's `RandomNumberGenerator` (PCG-family). Implements `half_to_even` manually because GDScript `round()` is half-away-from-zero. |
| [`src/simulation.gd`](src/simulation.gd) | `{rules.tick_resolution}` + `{rules.combat_resolution}` + canonical JSONL serializer | All logic is stateless functions reading explicit data. Tick-start snapshotting per D-012 (provably equivalent to apply-time under no-mid-tick-mutation invariant). |
| [`tests/engine_b_seed_12345.jsonl`](tests/engine_b_seed_12345.jsonl) | Engine-B reference trajectory at seed 12345 | 18 lines, terminal tick 17, terminal gold 6. **Does not match xtreme's golden** — see spec-ambiguities #12–#14 in [docs/v0.2-phase2-spec-ambiguities.md](../../../../docs/v0.2-phase2-spec-ambiguities.md). |

## Cross-engine status (Phase 4)

- **Within-engine determinism:** PASS. Two runs at seed 12345 → byte-identical.
- **Seed responsiveness (negative control):** PASS. Seed 99999 produces a different trajectory than seed 12345.
- **Cross-engine trajectory match against xtreme:** **FAIL — diverges at tick 1.** Root cause: spec §4.8 doesn't pin the PRNG algorithm (#12) or the gaussian sampling algorithm (#13). xtreme uses ChaCha20 + Marsaglia polar via Rust's `rand_distr`; Godot uses PCG-family + Box-Muller via core `randfn()`. **Both engines are spec-compliant; the spec under-constrains randomness.**

Per the Phase-4 discipline (spec is the judge, golden is the goal): **Godot is NOT patched to match xtreme**. The resolution is to pin the PRNG + sampling algorithm in §4.8 and re-lock both engines' goldens (Phase-4+ commit, deferred for the closed-vocabulary decision).

## D-008 §6 audit (adapted)

Did `data_behavior_separation` survive in Godot's actor/object engine? **Yes, in this implementation.** Unit holds no behavior; all logic is in stateless functions in distributions.gd / simulation.gd / state.gd, each citing the `{spec.token}` it realizes. But Godot's GDScript is text-authored, so the *Blueprint-specific* failure mode (visual graph absorbs design) wasn't probed. F-006 records this as a caveat — a real Phase-4 Unreal pass is needed to close the original §6 question.

## Limitations / future work

- Hardcoded unit stats in `deploy_demo_roster()` — should come from `content/units/*.yaml` via a v0.3-spec'd loader. Same pattern as xtreme.
- Threshold 0.10 and clamp `[1, 99]` are inlined per spec values rather than sourced from `{distributions.critical_hit}` / `{distributions.damage_roll}` declarations at runtime. Acceptable at v0.2 (no spec contract for runtime YAML loading); flagged for v0.3.
- The Phase-4+ spec lock for #12 (PRNG) will require replacing Godot's `RandomNumberGenerator` with whichever algorithm the spec pins. ChaCha20 has no native Godot support; a GDScript port or GDExtension binding would be needed.
