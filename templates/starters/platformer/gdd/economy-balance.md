---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-28"
implemented_in: ["src/balance/**/*.py"]
balance_targets:
  target_jump_height_pixels:
    target_kind: scalar
    target: 96
    tolerance: [88, 104]
    measure: "pixels of maximum jump height from rest, integer"
    status: draft
  average_attempts_per_level:
    target_kind: range
    target: { near: 6, tolerance: 4 }
    measure: "median attempts to clear a level, mid-game difficulty"
    status: draft
---

## Tokens

Two balance targets — one is feel-load-bearing (jump height in pixels), the
other is pacing (attempts-to-clear).

## Rationale

Jump height in pixels is the canonical platformer feel-load-bearing number;
every hazard placement, every gap width, every ceiling height is calibrated
against it. Treat as architecturally significant: a change to jump height
requires re-auditing every level.
