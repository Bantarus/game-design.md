---
spec: game-design.md
spec_version: 0.3.0
file_type: core
name: "Lamplight"
short_pitch: "A fixture tree for the gdmd view / graph goldens."
genre_tags: [test]
status: draft
version: 0.1.0
last_updated: "2026-09-30"
target_platforms_neutral: [desktop]
pillars: ["P1", "P2", "P3"]
non_goals: ["NG1"]
player_experience_goals:
  primary: [discovery]
core_loop_ref: "{loops.day}"
files:
  mechanics: gdd/mechanics.md
  loops: gdd/loops.md
  invariants: gdd/architecture-invariants.md
  balance: gdd/economy-balance.md
  relics: gdd/content/relics.md
implementation_pointers:
  sim: "src/sim/**/*.py"
---

# Lamplight

> Intro text before the first section mentions `{resources.focus}`: a gap-line reference.

## High Concept

A day of study is `{loops.day}`.

## Glossary

None.
