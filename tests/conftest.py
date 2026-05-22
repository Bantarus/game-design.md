"""Test infrastructure: a minimal valid baseline tree + fixture composition.

`make_tree` builds a complete minimal valid game-design.md tree in tmp_path
and lets each test override individual files. Used for rule-level unit tests.

`fixture_overlay` composes a baseline + the on-disk files under
`tests/fixtures/<name>/`. Used to exercise specific scenarios named in the
Step 4 brief (pity_floor, deterministic, dead-end, broken-ref,
invariant-violation).
"""
from __future__ import annotations

from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


BASELINE_FILES: dict[str, str] = {
    "game-design.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: core
name: "Tiny"
short_pitch: "Minimal valid tree used as a test baseline."
genre_tags: [test]
status: prototyped
version: 0.1.0
last_updated: "2026-05-21"
target_platforms_neutral: [desktop]
pillars: ["P1", "P2", "P3"]
non_goals: ["NG1"]
player_experience_goals:
  primary: [challenge]
core_loop_ref: "{loops.main}"
files:
  pillars: gdd/pillars.md
  loops: gdd/loops.md
  mechanics: gdd/mechanics.md
  invariants: gdd/architecture-invariants.md
  distributions: gdd/systems/distributions.md
  balance: gdd/economy-balance.md
  cards: gdd/content/cards.md
---

# Tiny

> Minimal valid tree used as a test baseline.

## High Concept

A baseline. `{loops.main}` is the only loop.

## Pillars & Non-Goals

See frontmatter.

## Player Experience Goals

Per the MDA aesthetics in the frontmatter.

## Core Gameplay Loop

`{loops.main}` — see `gdd/loops.md`.
""",
    "gdd/pillars.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
pillars: ["P1", "P2", "P3"]
non_goals: ["NG1"]
---

## Tokens

See frontmatter.
""",
    "gdd/loops.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
loops:
  main:
    timescale: moment
    duration: "~10s"
    sequence:
      - act: "{verbs.do_thing}"
    intended_dynamics: ["something happens"]
    intended_aesthetics: [challenge]
    status: prototyped
    implemented_in: []
---

## Tokens

The only loop is `{loops.main}`.
""",
    "gdd/mechanics.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
entities:
  player:
    type: actor
    properties: { hp: 10 }
    status: prototyped
    implemented_in: []
  cards:
    type: content_collection
    data_source: ../../content/cards
    count_target: 25
    status: prototyped
verbs:
  do_thing:
    actor: "{entities.player}"
    cost: 0
    target_schema: { type: system }
    effects:
      - { resolve: "{rules.do_thing_rule}" }
    status: prototyped
    implemented_in: []
resources:
  energy:
    scope: per_turn
    min: 0
    max: 1
    velocity_target: "{balance_targets.energy_target}"
    visibility: hud
    status: prototyped
    implemented_in: []
states:
  thing_state:
    initial: a
    nodes:
      - { id: a }
      - { id: b, terminal: true }
    transitions:
      - { from: a, event: go, to: b }
rules:
  do_thing_rule:
    given:
      verb: "{verbs.do_thing}"
    do:
      - sample: "{distributions.test_dist}"
    outputs: []
    status: prototyped
    implemented_in: []
---

## Tokens

The state machine `{states.thing_state}` is referenced indirectly.
""",
    "gdd/architecture-invariants.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
invariants:
  damage_int:
    kind: numeric_domain
    rule: "amounts are integers"
    applies_to: ["{resources.energy}"]
    enforcement: lint
    severity: error
---

## Tokens
""",
    "gdd/systems/distributions.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
distributions:
  test_dist:
    type: uniform
    range: [0.0, 1.0]
    status: prototyped
    implemented_in: []
---

## Tokens

`{distributions.test_dist}` is the baseline's only distribution.
""",
    "gdd/economy-balance.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
balance_targets:
  energy_target:
    target: 1
    tolerance: [1, 1]
    measure: "fixed"
    status: prototyped
---

## Tokens

`{balance_targets.energy_target}` is the only target.
""",
    "gdd/content/cards.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: content-schema
status: prototyped
last_verified: "2026-05-21"
entity: cards
schema:
  required: [id, name, cost]
  properties:
    id:   { type: string }
    name: { type: string }
    cost: { type: integer }
data_dir: ../../content/cards
count_target: 25
---

## Schema

See frontmatter.

## Representative Example

`content/cards/test_card.yaml` carries the canonical shape.

## Balance Notes

None — this is a test baseline.
""",
    "content/cards/test_card.yaml": """\
spec: game-design.md
spec_version: 0.1.1
file_type: content-entity
id: test_card
status: prototyped
implemented_in: []
name: "Test Card"
cost: 1
effects:
  - { kind: damage, amount: 5, distribution: "{distributions.test_dist}" }
""",
}


def _write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


@pytest.fixture
def make_tree(tmp_path: Path):
    """Build the minimal baseline + apply per-test overrides. Returns the path."""
    def _make(overrides: dict[str, str | None] | None = None) -> Path:
        _write_tree(tmp_path, BASELINE_FILES)
        if overrides:
            for rel, content in overrides.items():
                p = tmp_path / rel
                if content is None:
                    if p.exists():
                        p.unlink()
                    continue
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
        return tmp_path
    return _make


@pytest.fixture
def fixture_overlay(make_tree, tmp_path: Path):
    """Compose the baseline + every file under tests/fixtures/<name>/."""
    def _overlay(name: str) -> Path:
        root = make_tree()
        src = FIXTURES_DIR / name
        if not src.is_dir():
            raise FileNotFoundError(f"no on-disk fixture at {src}")
        for src_file in src.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(src)
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src_file.read_text())
        return root
    return _overlay
