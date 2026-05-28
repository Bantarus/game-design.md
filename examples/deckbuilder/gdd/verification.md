---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: experimental
last_verified: "2026-05-28"
verify_targets:
  - axis: behavioral_alignment
    target: "{balance_targets.win_rate_ascension_0}"
    sessions: 200
    expect: { win_rate: { near: 0.55, tolerance: 0.05 } }
  - axis: behavioral_alignment
    target: "{loops.combat_turn}"
    seed: 12345
    expect:
      median_turns_per_combat: { between: [4, 8] }
  - axis: behavioral_alignment
    target: "{balance_targets.cards_per_rarity}"
    expect:
      cards_per_rarity:
        common:   { near: 110, tolerance: 10 }
        uncommon: { near: 80,  tolerance: 10 }
        rare:     { near: 30,  tolerance: 5 }
  - axis: build_health
    expect: { builds: true, unresolved_refs: 0 }
adapters:
  default:      "./tools/verify-adapter"
  presentation: null
---

## Tokens

Four `verify_targets`: three `behavioral_alignment` and one `build_health`. No `presentation_usability` target — `adapters.presentation: null` skips that axis (per spec §9.5.1, the absence is not a failure). The third behavioral target exercises a `target_kind: distribution_over_categories` balance target — the adapter must match observed counts per-category against per-category tolerances, not against a single scalar.

## Rationale

**This is the engine-neutral surface of the dynamic loop.** The standard does not run the game; the project-supplied `adapters.default` does. The adapter is an executable (here a placeholder path `./tools/verify-adapter`) that builds the project, runs a fixed-seed session, and emits a `VerifyResult` JSON document on stdout conforming to `$defs.VerifyResult` in `schema/game-design.schema.json`.

The two `behavioral_alignment` targets together exercise both core loops:

- `{balance_targets.win_rate_ascension_0}` — 200-session sim measuring win rate against the 0.55 target. The `{invariants.deterministic_given_seed}` invariant requires that each session is reproducible, so the adapter can rerun any failed seed in isolation to debug.
- `{loops.combat_turn}` — a single fixed-seed run (`seed: 12345`) measuring turns-to-clear. Asserts the encounter pace is within tolerance.

`build_health` is intentionally minimal in v0.1.1: it just asserts the project builds and lints cleanly with zero unresolved cross-references (the same set `gdmd lint` checks under `broken-ref`). A v0.2 adapter could grow it to include startup assertions (e.g. all `implemented_in` paths resolve, all assets load).

**Status: experimental** — see §9.5 of `docs/spec.md`. No real adapter ships in this v0.1.1 tree; `./tools/verify-adapter` is the *declared contract* for whichever adapter the project later writes. `gdmd verify` will refuse to run with exit code 2 ("no adapter") until the file exists and is executable.

## Open Questions

- Whether to promote the `cross_layer_via_events` invariant to `enforcement: verify` here (would add a fourth verify target observing the simulation→presentation event boundary).
- Whether `presentation_usability` is worth shipping at all given the spec's engine-neutrality. The current call is to leave it null and let downstream forks opt in.
