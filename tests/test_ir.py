"""The compiled model behind `gdmd view` / `gdmd graph` (spec §9.9.1, D-027).

Property tests run on all 12 in-repo trees; they compare the IR against the
loader and the linter's own data, so the views can never disagree with
`lint` about the tree.
"""
from __future__ import annotations

import shutil
import textwrap
from collections import Counter
from pathlib import Path

import pytest

from game_design_md import linter, loader
from game_design_md.ir import backlink_matches, compile_tree, format_field
from game_design_md.refs import walk_refs
from game_design_md.tree import Tree
from tests.conftest import IN_REPO_TREES, REPO_ROOT

TREES = [REPO_ROOT / t for t in IN_REPO_TREES]
IDS = list(IN_REPO_TREES)

# The namespaces `orphaned-entity` checks (linter.rule_orphaned_entity).
ORPHAN_CHECKED = ("entities", "resources", "states", "rules", "loops",
                  "distributions", "feel", "balance_targets", "events", "clocks")


@pytest.fixture(scope="module", params=TREES, ids=IDS)
def model(request):
    return compile_tree(request.param)


def test_compose_equals_loader_read(model):
    """Composing + constructing gives exactly `loader.read`'s values."""
    ref = Tree.load(model.root)
    assert sorted(pf.rel_str for pf in ref.files) == sorted(model.tree.by_rel)
    for pf in ref.files:
        mine = model.tree.by_rel[pf.rel_str]
        assert mine.frontmatter == pf.frontmatter, pf.rel_str
        assert mine.body == pf.body, pf.rel_str


def test_token_blocks_reparse_verbatim(model):
    """Every token block's lines, read verbatim at its pointer, re-parse to the
    token's value (the lowering rule's 'token values verbatim')."""
    n = 0
    for b in model.blocks:
        if b.role not in ("token", "invariant"):
            continue
        n += 1
        sf = model.by_path[b.path]
        src = "\n".join(sf.slice(b.start, b.end)) + "\n"
        parsed = loader.load_yaml(textwrap.dedent(src))
        ns, tid = b.token_id.split(".", 1)
        assert parsed == {tid: model.tree.by_rel[b.path].frontmatter[ns][tid]}, b.secondary
        on_disk = (model.root / b.path).read_text(encoding="utf-8").split("\n")
        assert sf.slice(b.start, b.end) == on_disk[b.start - 1:b.end], b.secondary
    assert n > 0


def test_blocks_nest_and_never_overlap(model):
    for sf in model.files:
        owner: dict[int, int] = {}
        for b in model.blocks:
            if b.path != sf.path:
                continue
            assert 1 <= b.start <= b.end <= sf.n_lines, b.secondary
            if b.parent is not None:
                p = model.blocks[b.parent]
                assert p.start <= b.start and b.end <= p.end, (b.secondary, p.secondary)
                continue
            for ln in range(b.start, b.end + 1):
                assert ln not in owner, (b.secondary, model.blocks[owner[ln]].secondary)
                owner[ln] = b.index


def test_impl_blocks_nest_in_their_token(model):
    for b in model.blocks:
        if b.role == "impl" and b.parent is not None:
            parent = model.blocks[b.parent]
            assert parent.has_identity
            assert b.token_id == parent.token_id
            assert model.by_path[b.path].lines[b.start - 1].strip().startswith("implemented_in:")


def test_value_refs_are_walk_refs_exactly(model):
    """Frontmatter extraction is `walk_refs`, in order, with the same paths."""
    for sf in model.files:
        mine = [(o.ref, o.field) for o in model.occurrences
                if o.path == sf.path and o.kind == "value"]
        theirs = [(r, format_field(p)) for r, p in walk_refs(sf.pf.frontmatter or {})]
        assert mine == theirs, sf.path


def test_every_occurrence_is_on_its_line(model):
    for o in model.occurrences:
        assert "{" + o.ref + "}" in model.by_path[o.path].lines[o.line - 1], o.pointer


def test_unresolved_is_broken_ref_and_vice_versa(model):
    res = linter.run_all(model.tree)
    broken = Counter((f.file, f.message) for f in res.findings if f.rule == "broken-ref")
    unresolved = Counter((o.path, f"reference {{{o.ref}}} does not resolve")
                         for o in model.occurrences if o.outcome == "unresolved")
    assert broken == unresolved


def test_backlinks_are_the_orphan_predicate(model):
    """For each token `orphaned-entity` checks: no backlinks ⇔ an orphan finding;
    every backlink satisfies the predicate."""
    res = linter.run_all(model.tree)
    orphans = {f.location for f in res.findings if f.rule == "orphaned-entity"}
    checked = 0
    for ns in ORPHAN_CHECKED:
        for tid, (pf, val) in model.tree.tokens.get(ns, {}).items():
            if ns == "entities" and tid.count(".") > 1:
                continue
            if isinstance(val, dict) and (val.get("status") == "cut" or (
                    ns == "entities" and val.get("type") == "actor")):
                continue
            checked += 1
            links = model.backlinks(tid)
            assert all(backlink_matches(o.ref, tid) for o in links)
            assert (not links) == (tid in orphans), tid
    assert checked > 0


def test_every_token_has_a_block(model):
    for table in model.tree.tokens.values():
        for tid in table:
            b = model.blocks[model.by_id[tid]]
            assert b.token_id == tid and b.has_identity


def test_rationale_attribution_on_invariants():
    m = compile_tree(REPO_ROOT / "examples/deckbuilder")
    explained = {b.explains for b in m.blocks if b.explains}
    assert "invariants.damage_is_integer" in explained
    b = next(b for b in m.blocks if b.explains == "invariants.damage_is_integer")
    assert b.role == "rationale" and b.parent is not None
    assert b.primary == "gdd/architecture-invariants.md#Rationale/damage_is_integer"


# ---- positions on hand-written edge cases (fixtures, not examples) ----------------

EDGE_SUBFILE = """\
---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-21"
resources:
  # comment above mana: belongs to the token
  mana:
    scope: per_turn
    min: 0
    max: 3
    note: |
      a block scalar
      # a hash line inside the scalar, not a comment
    visibility: hud
    status: draft
    implemented_in: ["src/mana.py"]
  # comment after mana's value, directly above rage: belongs to rage
  rage: { scope: per_run, min: 0, max: 9, visibility: hud, status: draft, implemented_in: [] }

  # trailing comment after the last token: a gap
---

Intro text before the first section is a gap.

## Rationale

```yaml
## not a heading: inside a fence
```

### mana

Explains the token.
"""


@pytest.fixture
def edge_model(tmp_path: Path):
    (tmp_path / "gdd").mkdir()
    (tmp_path / "gdd/mechanics.md").write_text(EDGE_SUBFILE)
    return compile_tree(tmp_path)


def _by_primary(m, primary):
    return next(b for b in m.blocks if b.primary == primary)


def test_edge_extents(edge_model):
    m = edge_model
    mana = _by_primary(m, "{resources.mana}")
    assert (mana.start, mana.end) == (8, 18)       # leading comment; scalar's '#' line kept
    impl = next(b for b in m.blocks if b.role == "impl" and b.parent == mana.index)
    assert (impl.start, impl.end) == (18, 18)
    rage = _by_primary(m, "{resources.rage}")
    assert (rage.start, rage.end) == (19, 20)      # comment directly above belongs to rage
    sf = m.by_path["gdd/mechanics.md"]
    assert sf.outermost[7 - 1] is None             # namespace key line: gap
    assert sf.outermost[22 - 1] is None            # trailing comment: gap
    rat = _by_primary(m, "gdd/mechanics.md#Rationale")
    sub = _by_primary(m, "gdd/mechanics.md#Rationale/mana")
    assert sub.parent == rat.index and sub.explains == "resources.mana"
    assert (rat.start, rat.end) == (27, 35)
    assert (sub.start, sub.end) == (33, 35)
    assert not any("not a heading" in b.primary for b in m.blocks)


# ---- tree_sha ---------------------------------------------------------------------

def test_tree_sha(tmp_path: Path):
    src = REPO_ROOT / "templates/starters/deckbuilder"
    t = tmp_path / "t"
    shutil.copytree(src, t)
    a = compile_tree(t).tree_sha
    assert compile_tree(t).tree_sha == a                      # stable
    (t / "notes.txt").write_text("not a tree file\n")
    (t / "README-plain.md").write_text("# no frontmatter\n")  # not loaded
    assert compile_tree(t).tree_sha == a
    p = t / "gdd/loops.md"
    p.write_text(p.read_text() + " ")                         # one byte in a loaded file
    assert compile_tree(t).tree_sha != a


def test_compile_writes_nothing(tmp_path: Path):
    t = tmp_path / "t"
    shutil.copytree(REPO_ROOT / "templates/starters/tick-combat", t)
    before = {p: p.stat().st_mtime_ns for p in t.rglob("*")}
    compile_tree(t)
    assert {p: p.stat().st_mtime_ns for p in t.rglob("*")} == before
