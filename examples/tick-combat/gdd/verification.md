---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-22"
verify_targets:
  - axis: behavioral_alignment
    target: "{balance_targets.median_ticks_per_combat}"
    sessions: 1000
    expect:
      median_ticks: { between: [80, 200] }
  - axis: behavioral_alignment
    target: "{balance_targets.win_rate_neutral_formation}"
    sessions: 1000
    expect:
      win_rate: { near: 0.5, tolerance: 0.05 }
  - axis: build_health
    expect: { builds: true, unresolved_refs: 0 }
adapters:
  default:      "./tools/verify-adapter"
  presentation: null
---

## Tokens

Three verify targets. Two `behavioral_alignment` (median ticks + win-rate symmetry); one `build_health`. No `presentation_usability` — Lockstep doesn't ship presentation assertions in v0.1.

## Rationale

`{invariants.deterministic_given_seed}` is declared `enforcement: verify`, so the lint pass is silent and the verify adapter is responsible for catching regressions. The adapter (when written) should run each verify target twice with the same seed and assert byte-identical state at every tick.

`win_rate_neutral_formation` is a behavioral check that doubles as a *non-determinism canary*: if two adapter runs at the same seed produce different win rates, determinism is broken.

**Status: experimental.** The adapter executable does not exist in v0.1.1. `gdmd verify examples/tick-combat` will exit with the "adapter not found" message until a real adapter ships.
