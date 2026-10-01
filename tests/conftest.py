"""Test infrastructure: a minimal valid baseline tree + fixture composition.

`make_tree` builds a complete minimal valid game-design.md tree in tmp_path
and lets each test override individual files. Used for rule-level unit tests.

`fixture_overlay` composes a baseline + the on-disk files under
`tests/fixtures/<name>/`. Used to exercise specific scenarios named in the
Step 4 brief (pity_floor, deterministic, dead-end, broken-ref,
invariant-violation).
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parent.parent

# ---- the v0.3 world (D-051) -------------------------------------------------------
# The dogfood baseline world is built from the v0.3.0 tag, and some tests also
# run that world's gdmd from the v0.3 venv (benchmark/dogfood/README). Tests
# that need them carry @pytest.mark.v03_world (venv=True for the venv). Locally
# a missing tag or venv skips them; under CI ($CI set) it fails them, as D-050
# does for `build`, so a CI run cannot pass them by skipping.
V03_TAG = "v0.3.0"
V03_GDMD = Path.home() / ".local/share/gdmd-dogfood/venvs/gdmd-v0.3.0/bin/gdmd"


def v03_missing(venv: bool = False) -> str | None:
    """Why the v0.3 world is unavailable here, or None."""
    if subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "-q", "--verify",
                       f"{V03_TAG}^{{commit}}"], capture_output=True).returncode != 0:
        return f"needs the {V03_TAG} tag"
    if venv and not V03_GDMD.is_file():
        return "v0.3 venv not installed (see benchmark/dogfood/README)"
    return None


def pytest_runtest_setup(item):
    marker = item.get_closest_marker("v03_world")
    if marker is None:
        return
    reason = v03_missing(venv=marker.kwargs.get("venv", False))
    if reason is None:
        return
    if os.environ.get("CI"):
        pytest.fail(f"{reason}: the v0.3-world tests must run in CI (D-051)", pytrace=False)
    pytest.skip(reason)


def git_show(spec: str, *, partial: bool = False) -> str | None:
    """`git show <rev>:<path>` for tests that need git history (marked
    git_history). Without the history (a shallow clone): fail under CI, as the
    v0.3-world tests do (D-051); locally skip, or with `partial=True` return
    None so the test keeps the checks that need no history."""
    res = subprocess.run(["git", "-C", str(REPO_ROOT), "show", spec],
                         capture_output=True, text=True)
    if res.returncode == 0:
        return res.stdout
    reason = f"history not available ({spec})"
    if os.environ.get("CI"):
        pytest.fail(f"{reason}: the history-needing tests must run in CI (D-051)", pytrace=False)
    if partial:
        return None
    pytest.skip(reason)


# The 12 in-repo trees: 4 canonical examples, 2 benchmark games, 6 starters.
IN_REPO_TREES: tuple[str, ...] = (
    "examples/deckbuilder", "examples/tick-combat", "examples/party-rpg",
    "examples/tcg", "benchmark/games/platformer", "benchmark/games/survival",
) + tuple(f"templates/starters/{g}" for g in (
    "deckbuilder", "party-rpg", "platformer", "survival", "tcg", "tick-combat",
))


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
spec_version: 0.2.0-alpha
file_type: subfile
status: prototyped
last_verified: "2026-05-22"
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
      - { from: a, event: "{events.go}", to: b }
events:
  go:
    status: prototyped
    description: "Baseline test event used by thing_state's a → b transition."
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
spec_version: 0.2.0-alpha
file_type: subfile
status: prototyped
last_verified: "2026-05-22"
balance_targets:
  energy_target:
    target_kind: scalar
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


def tick_combat_out_of_tree(tmp_path: Path) -> tuple[Path, Path]:
    """D-038 (OI-002): the real tick-combat tree at `repo/docs/tick-combat`,
    with its engine code at the repository root (`repo/impl/`) and its
    implementation globs rewritten from `impl/...` to `../../impl/...`.
    `repo/.git` marks the repository root. Returns (repo, tree)."""
    import shutil
    src = REPO_ROOT / "examples/tick-combat"
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    tree = repo / "docs/tick-combat"
    shutil.copytree(src, tree, ignore=shutil.ignore_patterns("impl"))
    for rel in ("impl/xtreme/src", "impl/godot/src"):
        shutil.copytree(src / rel, repo / rel)
    shutil.copy(src / "impl/xtreme/Cargo.toml", repo / "impl/xtreme/Cargo.toml")
    for f in (tree / "game-design.md", *tree.glob("gdd/**/*.md")):
        f.write_text(f.read_text().replace('"impl/', '"../../impl/'))
    # Pin every mtime before the tree's earliest last_verified (2026-05-22), so
    # `stale-section` does not depend on when the checkout was made (a fresh
    # CI checkout gave 12 warnings).
    pinned = datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp()
    for p in repo.rglob("*"):
        if p.is_file():
            os.utime(p, (pinned, pinned))
    return repo, tree
