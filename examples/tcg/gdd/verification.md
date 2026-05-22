---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-22"
verify_targets:
  - axis: behavioral_alignment
    target: "{balance_targets.win_rate_archetype_neutral}"
    sessions: 1000
    expect:
      win_rate: { near: 0.5, tolerance: 0.05 }
  - axis: behavioral_alignment
    target: "{balance_targets.average_game_turns}"
    sessions: 1000
    expect:
      median_turns: { between: [5, 12] }
  - axis: build_health
    expect: { builds: true, unresolved_refs: 0 }
adapters:
  default:      "./tools/verify-adapter"
  presentation: null
---

## Tokens

Three verify targets. The matchup symmetry test is the heaviest — it must run 6 archetype pairings × 1000 matches = 6000 games per verify pass.

## Rationale

`{balance_targets.win_rate_archetype_neutral}` is the design's promise; the verify adapter must simulate matches across every archetype pair and report each pair's win rate. The 0.05 tolerance is tight, reflecting the high stakes of asymmetric balance.

`average_game_turns` cross-checks the curve. A regression that makes games shorter (over-tuned aggression) or longer (control creeps in) is caught here.

**Status: experimental.** No adapter ships in v0.1.1; the declared path `./tools/verify-adapter` is a contract per spec §9.5.
