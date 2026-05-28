---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: experimental
last_verified: "2026-05-28"
verify_targets:
  - axis: behavioral_alignment
    target: "{balance_targets.legendary_drops_per_quest}"
    sessions: 1000
    expect:
      legendary_rate: { near: 0.4, tolerance: 0.1 }
  - axis: behavioral_alignment
    target: "{balance_targets.win_rate_neutral_party}"
    sessions: 1000
    expect:
      win_rate: { near: 0.65, tolerance: 0.05 }
  - axis: build_health
    expect: { builds: true, unresolved_refs: 0 }
adapters:
  default:      "./tools/verify-adapter"
  presentation: null
---

## Tokens

Three verify targets — two `behavioral_alignment` (legendary rate + win rate), one `build_health`.

## Rationale

`legendary_drops_per_quest` is the *pity-floor sanity check*: if the adapter sees ~0.4 legendaries per quest on average, the pity counters are working. If it sees ~0.2 (the base rate without pity), the pity floor regressed silently.

`win_rate_neutral_party` cross-checks `{balance_targets.win_rate_neutral_party}` and doubles as a *non-determinism canary* — two adapter runs at the same seed should produce identical drops, which the adapter can asserts byte-by-byte.

**Status: experimental.** No adapter ships in v0.1.1; the path `./tools/verify-adapter` is a declared contract per spec §9.5.
