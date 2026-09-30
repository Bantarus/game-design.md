"""`gdmd view` (spec §9.9.2–§9.9.3, D-027).

The central properties run on all 12 in-repo trees:
- `--full` covers every non-blank line of every loaded file exactly once,
  verbatim at its line number;
- every source line any view emits equals the file's line at its number;
- every pointer names exactly the block it claims.
Functional cases use small hand-written trees under tmp_path, not examples.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest
from click.testing import CliRunner

from game_design_md.cli import main
from game_design_md.ir import compile_tree
from game_design_md.view_cmd import run_view
from tests.conftest import IN_REPO_TREES, REPO_ROOT

TREES = [REPO_ROOT / t for t in IN_REPO_TREES]
IDS = list(IN_REPO_TREES)

GAP_RE = re.compile(r"^\[gap\] (\S+):(\d+)-(\d+)$")
ELISION_RE = re.compile(r"^… (\d+) lines? · (\S+):(\d+)-(\d+)$")
BACKLINK_PTR_RE = re.compile(r"^    (\S+):(\d+) (value|prose) \S+$")


@pytest.fixture(scope="module", params=TREES, ids=IDS)
def model(request):
    return compile_tree(request.param)


def walk_output(model, lines: list[str]) -> Counter:
    """Follow a block-structured text view (--full, --grep, --ref's focus).

    Headers, `[gap]` markers and elision markers set the position; every
    other line must be the file's line at that position. Returns how many
    times each (path, line) was covered, verbatim or by an elision.
    """
    headers = {b.header(): b for b in model.blocks}
    covered: Counter = Counter()
    cur: tuple[str, int] | None = None
    for line in lines:
        if line.startswith("[view ") or line.startswith("[file] "):
            continue
        if line in headers:
            b = headers[line]
            if cur is not None and cur[0] == b.path and b.parent is not None:
                assert cur[1] == b.start, (line, cur)   # nested header sits in place
            cur = (b.path, b.start)
            continue
        m = GAP_RE.match(line)
        if m:
            cur = (m.group(1), int(m.group(2)))
            continue
        m = ELISION_RE.match(line)
        if m:
            path, a, z = m.group(2), int(m.group(3)), int(m.group(4))
            assert cur == (path, a), (line, cur)
            assert int(m.group(1)) == z - a + 1
            for ln in range(a, z + 1):
                covered[(path, ln)] += 1
            cur = (path, z + 1)
            continue
        assert cur is not None, line
        path, ln = cur
        assert model.by_path[path].lines[ln - 1] == line, (path, ln)
        covered[(path, ln)] += 1
        cur = (path, ln + 1)
    return covered


# ---- --full ------------------------------------------------------------------------

def test_full_covers_every_nonblank_line_exactly_once(model):
    out = run_view(model, "T", full=True).split("\n")
    assert out[0] == f"[view full] T tree_sha={model.tree_sha}"
    covered = walk_output(model, out[1:])
    for sf in model.files:
        for ln, text in enumerate(sf.lines, 1):
            n = covered[(sf.path, ln)]
            if text.strip():
                assert n == 1, (sf.path, ln, n)
            else:
                assert n <= 1


def test_full_json_sources_are_the_slices_at_their_pointers(model):
    data = json.loads(run_view(model, "T", full=True, as_json=True))
    assert data["tree_sha"] == model.tree_sha
    by_ptr = {(b.primary, b.secondary): b for b in model.blocks}
    for d in data["blocks"]:
        b = by_ptr[(d["id"], d["pointer"])]
        assert b.parent is None and d["role"] == b.role
        assert d["source"] == "\n".join(model.by_path[b.path].slice(b.start, b.end))
        assert [c["pointer"] for c in d["children"]] == \
            [model.blocks[c].secondary for c in model.descendants(b.index)]
    for g in data["gaps"]:
        path, a, z = re.match(r"^(\S+):(\d+)-(\d+)$", g["pointer"]).groups()
        assert g["source"] == "\n".join(model.by_path[path].slice(int(a), int(z)))


# ---- --grep ------------------------------------------------------------------------

@pytest.mark.parametrize("pattern", [r"status", r"\{", r"^##", r"the"])
def test_grep_lines_are_verbatim_and_every_block_match_is_shown(model, pattern):
    out = run_view(model, "T", grep=pattern).split("\n")
    covered = walk_output(model, out[1:])
    rx = re.compile(pattern)
    emitted = {k for k, v in covered.items() if v}
    elided_or_shown = set(covered)
    for sf in model.files:
        for ln, text in enumerate(sf.lines, 1):
            if rx.search(text) and sf.innermost[ln - 1] is not None:
                assert (sf.path, ln) in emitted, (sf.path, ln)
    # a unit never shows a line twice
    assert all(v == 1 for k, v in covered.items() if k in elided_or_shown)


def test_grep_json_selected_blocks_are_innermost(model):
    data = json.loads(run_view(model, "T", grep=r"implemented_in", as_json=True))
    by_ptr = {(b.primary, b.secondary): b for b in model.blocks}
    for unit in data["blocks"]:
        root = by_ptr[(unit["id"], unit["pointer"])]
        assert root.parent is None
        for sel in unit["selected"]:
            b = by_ptr[(sel["id"], sel["pointer"])]
            assert b.index == root.index or root.index in model.ancestors(b.index)
        sf = model.by_path[root.path]
        for ln in unit["matches"]:
            inner = sf.innermost[ln - 1]
            assert model.blocks[inner].secondary in [s["pointer"] for s in unit["selected"]]


# ---- --ref ---------------------------------------------------------------------------

def test_ref_focus_and_backlink_lines_are_verbatim(model):
    for b in model.blocks:
        if not b.has_identity or model.by_id.get(b.token_id) != b.index:
            continue
        out = run_view(model, "T", ref="{" + b.token_id + "}", hops=2).split("\n")
        assert out[1] == b.header()
        fwd = next(i for i, ln in enumerate(out) if ln.startswith("forward ("))
        covered = walk_output(model, out[1:fwd])
        assert [k for k, v in covered.items() if v] == \
            [(b.path, ln) for ln in range(b.start, b.end + 1)]
        for i, line in enumerate(out):
            m = BACKLINK_PTR_RE.match(line)
            if m:
                assert out[i + 1] == model.by_path[m.group(1)].lines[int(m.group(2)) - 1]


def test_ref_backlinks_are_exactly_the_predicate(model):
    for tid, idx in model.by_id.items():
        data = json.loads(run_view(model, "T", ref="{" + tid + "}", as_json=True))
        got = sorted(v["pointer"] + v["ref"] for n in data["backlinks"] for v in n["via"])
        want = sorted(o.pointer + "{" + o.ref + "}" for o in model.backlinks(tid))
        assert got == want, tid


# ---- pointers ------------------------------------------------------------------------

def test_every_json_pointer_names_its_block(model):
    by_ptr = {(b.primary, b.secondary) for b in model.blocks}
    overview = json.loads(run_view(model, "T", as_json=True))
    for rows in overview["namespaces"].values():
        for r in rows:
            assert (r["id"], r["pointer"]) in by_ptr
    flat = json.loads(run_view(model, "T", flat=True, as_json=True))
    assert len(flat["blocks"]) == len(model.blocks)
    for r in flat["blocks"]:
        assert (r["id"], r["pointer"]) in by_ptr


def test_overview_counts_content_entities_and_names_the_listing_view(model):
    out = run_view(model, "T")
    n = sum(1 for b in model.blocks if b.role == "content-entity")
    if n:
        assert f"… {n} content entities · gdmd view T --flat --role content-entity" in out
        flat = run_view(model, "T", flat=True, roles=("content-entity",)).split("\n")[1:]
        assert len(flat) == n and all(ln.startswith("content-entity ") for ln in flat)


# ---- functional cases on a hand-written tree ---------------------------------------

TINY = {
    "game-design.md": """\
---
spec: game-design.md
spec_version: 0.3.0
file_type: core
status: draft
core_loop_ref: "{loops.main}"
files:
  mechanics: gdd/mechanics.md
---

# Tiny

## High Concept

Uses `{resources.mana}`.
""",
    "gdd/mechanics.md": """\
---
spec: game-design.md
spec_version: 0.3.0
file_type: subfile
status: draft
last_verified: "2026-05-21"
resources:
  mana:
    scope: per_turn
    max: 3
    status: draft
    implemented_in: ["src/mana_impl.py"]
verbs:
  cast:
    cost: { resource: "{resources.mana}", amount: 1 }
    effects: ["{actor.power}", "{verbs.missing}"]
    status: draft
---

## Rationale

`{verbs.cast}` spends `{resources.mana.max}`.
""",
}


@pytest.fixture
def tiny(tmp_path: Path) -> Path:
    for rel, text in TINY.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path


def test_grep_inside_impl_selects_the_impl_block_within_its_token(tiny):
    m = compile_tree(tiny)
    data = json.loads(run_view(m, "T", grep="mana_impl", as_json=True))
    (unit,) = data["blocks"]
    assert unit["role"] == "token" and unit["id"] == "{resources.mana}"
    assert [s["role"] for s in unit["selected"]] == ["impl"]
    out = run_view(m, "T", grep="mana_impl").split("\n")
    assert out[1:] == [
        "[file] gdd/mechanics.md subfile",
        "[gap] gdd/mechanics.md:7-7",
        "resources:",
        "[token] {resources.mana} gdd/mechanics.md:8-12 status=draft",
        "  mana:",
        "… 3 lines · gdd/mechanics.md:9-11",
        "[impl] {resources.mana} gdd/mechanics.md:12-12",
        '    implemented_in: ["src/mana_impl.py"]',
    ]


def test_grep_role_filter_selects_the_enclosing_role(tiny):
    m = compile_tree(tiny)
    data = json.loads(run_view(m, "T", grep="mana_impl", roles=("token",), as_json=True))
    assert [s["role"] for s in data["blocks"][0]["selected"]] == ["token"]
    assert json.loads(run_view(m, "T", grep="mana_impl", roles=("meta",),
                               as_json=True))["blocks"] == []


def test_ref_lists_outcomes_and_names_the_sub_path(tiny):
    m = compile_tree(tiny)
    data = json.loads(run_view(m, "T", ref="{verbs.cast.cost}", as_json=True))
    assert data["focus"]["id"] == "{verbs.cast}" and data["sub_path"] == "cost"
    assert [(f["ref"], f["outcome"]) for f in data["forward"]] == [
        ("{resources.mana}", "resolved"),
        ("{actor.power}", "context-local"),
        ("{verbs.missing}", "unresolved"),
    ]
    back = json.loads(run_view(m, "T", ref="{resources.mana}", as_json=True))["backlinks"]
    kinds = sorted((n["block"]["role"], v["kind"]) for n in back for v in n["via"])
    # the verb's value ref, and two prose refs (one is a sub-path: mana.max)
    assert kinds == [("rationale", "prose"), ("rationale", "prose"), ("token", "value")]


def test_full_role_filter_emits_only_those_blocks(tiny):
    m = compile_tree(tiny)
    out = run_view(m, "T", full=True, roles=("impl",)).split("\n")
    assert [ln for ln in out if ln.startswith("[") and not ln.startswith("[view")
            and not ln.startswith("[file]")] == ["[impl] {resources.mana} gdd/mechanics.md:12-12"]


def test_cli_exit_codes(tiny):
    r = CliRunner()
    assert r.invoke(main, ["view", "--help"]).exit_code == 0
    res = r.invoke(main, ["view", str(tiny), "--ref", "{verbs.nope}"])
    assert res.exit_code == 2 and "{verbs.nope} does not resolve" in res.output
    assert r.invoke(main, ["view", str(tiny), "--ref", "{actor.power}"]).exit_code == 2
    assert r.invoke(main, ["view", str(tiny), "--grep", "zzz_no_match"]).exit_code == 0
    assert r.invoke(main, ["view", str(tiny), "--full", "--grep", "x"]).exit_code == 2
    assert r.invoke(main, ["view", str(tiny), "--grep", "("]).exit_code == 2
    # views never fail on lint findings: the tiny tree has a broken ref
    assert r.invoke(main, ["view", str(tiny)]).exit_code == 0


def test_views_are_deterministic_and_write_nothing(tmp_path: Path):
    t = tmp_path / "t"
    shutil.copytree(REPO_ROOT / "examples/deckbuilder", t)
    before = {p: p.stat().st_mtime_ns for p in t.rglob("*")}
    r = CliRunner()
    for args in ([], ["--full"], ["--grep", "energy"], ["--ref", "{resources.energy}",
                 "--hops", "3"], ["--flat"], ["--full", "--json"]):
        a = r.invoke(main, ["view", str(t), *args])
        b = r.invoke(main, ["view", str(t), *args])
        assert a.exit_code == 0 and a.output == b.output
    assert {p: p.stat().st_mtime_ns for p in t.rglob("*")} == before
