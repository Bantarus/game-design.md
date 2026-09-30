"""Dogfood study 2's fixture (D-026): the generated "Lanternfall" tree.

- The generator reproduces its frozen output byte-for-byte (D-026 §5).
- The frozen answers, computed from the planted edge list, agree with the
  tools the views arm uses: `refs.walk_refs` + `Tree` resolution for the whole
  edge set, `gdmd view`'s BFS for the lookups and `gdmd graph --impact` for
  the impact tasks. This cross-check runs once, here; the checkers only read
  the frozen answers (D-026 §8, the frozen-fixtures rule).
- The tree lints 0/0, identically, under the matrix `gdmd` and the v0.3
  `gdmd` (D-026 §6), is schema-valid, and its content validates.
- No tree token id occurs in what `CLAUDE.md` imports, in either world, except
  the exempt collection tokens (D-026 §7).
No model calls.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from game_design_md import loader
from game_design_md.graph_cmd import impact
from game_design_md.ir import compile_tree, longest_prefix_target
from game_design_md.linter import CONTEXT_LOCAL_PREFIXES
from game_design_md.refs import walk_refs
from game_design_md.tree import SUBFILE_NAMESPACES, Tree
from tests.conftest import REPO_ROOT

STUDY2 = REPO_ROOT / "benchmark/dogfood/fixtures/study2"
TREE = STUDY2 / "tree"
V03_GDMD = Path.home() / ".local/share/gdmd-dogfood/venvs/gdmd-v0.3.0/bin/gdmd"

_spec = importlib.util.spec_from_file_location("study2_generate", STUDY2 / "generate.py")
gen = importlib.util.module_from_spec(_spec)
sys.modules["study2_generate"] = gen
_spec.loader.exec_module(gen)
sys.path.insert(0, str(REPO_ROOT / "benchmark/dogfood"))
import fixture  # noqa: E402

EDGES = json.loads((STUDY2 / "edges.json").read_text(encoding="utf-8"))
ANSWERS = {p.stem: json.loads(p.read_text(encoding="utf-8"))
           for p in sorted((STUDY2 / "answers").glob("*.json"))}


def _is_content(n: str) -> bool:
    return gen.is_content(n)


# ---- determinism ---------------------------------------------------------------------

def test_generator_reproduces_the_frozen_output_byte_for_byte():
    out = gen.render()
    have = gen.frozen()
    assert sorted(out) == sorted(have)
    assert [k for k in out if out[k] != have[k]] == []


# ---- D-026 §3-§4, §9 parameters ------------------------------------------------------------

def test_locked_construction_parameters():
    nodes = EDGES["nodes"]
    for kind, n in gen.KINDS.items():
        assert sum(1 for x in nodes if x.startswith(f"entities.{kind}.")) == n
    non_content = [n for n in nodes if not _is_content(n)]
    assert len(non_content) >= 60
    assert len({n.split(".")[0] for n in non_content}) >= 8
    assert len(EDGES["subfiles"]) >= 12
    assert EDGES["seed"] == 20260930


def test_prototyped_subset_points_at_existing_stubs():
    t = Tree.load(TREE)
    proto = 0
    for pf in t.files:
        for ns in SUBFILE_NAMESPACES:
            for tid, v in (pf.frontmatter.get(ns) or {}).items():
                if isinstance(v, dict) and v.get("status") == "prototyped":
                    proto += 1
                    assert v.get("implemented_in"), f"{ns}.{tid}"
                    for g in v["implemented_in"]:
                        assert list(TREE.glob(g)), g
    assert proto >= 5


# ---- the oracle cross-check (once, here) ------------------------------------------------

def _tool_edges() -> set[tuple[str, str]]:
    """Value edges by the linter's own semantics: `walk_refs` over frontmatter,
    attributed to the token (or content entity) whose value holds the
    reference, resolved to the longest registered prefix."""
    t = Tree.load(TREE)
    out: set[tuple[str, str]] = set()

    def add(src: str, value) -> None:
        for ref, _ in walk_refs(value):
            if ref.split(".", 1)[0] in CONTEXT_LOCAL_PREFIXES:
                continue
            dst = longest_prefix_target(t, ref)
            assert dst is not None, (src, ref)
            out.add((src, dst))

    for pf in t.files:
        fm = pf.frontmatter
        if pf.file_type == "content-entity":
            add(f"entities.{pf.abs_path.parent.name}.{fm['id']}", fm)
        elif pf.file_type == "subfile":
            for ns in SUBFILE_NAMESPACES:
                for k, v in (fm.get(ns) or {}).items():
                    add(f"{ns}.{k}", v)
            add(f"meta:{pf.rel_str}", {k: v for k, v in fm.items() if k not in SUBFILE_NAMESPACES})
        else:
            add(f"meta:{pf.rel_str}", fm)
    return out


def test_planted_edges_equal_the_linters_value_edges():
    planted = {(e["src"], e["dst"]) for e in EDGES["edges"]}
    assert _tool_edges() == planted


@pytest.fixture(scope="module")
def model():
    return compile_tree(TREE)


def _ids(m, found, hop=None, identity=True) -> set[str]:
    out = set()
    for n, (h, _) in found.items():
        if isinstance(n, tuple) or (hop is not None and h != hop):
            continue
        b = m.blocks[n]
        if identity and not b.has_identity:
            continue
        out.add(b.token_id)
    return out


def test_lookup_forward_answers_match_gdmd_view(model):
    for q in ANSWERS["s2_lookup_forward"]["questions"].values():
        found = model.bfs(model.by_id[q["start"]], "forward", q["k"])
        got = {n for n in _ids(model, found, hop=q["k"]) if gen.kind_of(n) == q["kind"]}
        assert got == set(q["answer"])


def test_lookup_backward_answers_match_gdmd_view(model):
    for q in ANSWERS["s2_lookup_backward"]["questions"].values():
        found = model.bfs(model.by_id[q["start"]], "back", q["k"])
        assert {n for n in _ids(model, found) if _is_content(n)} == set(q["answer"])


def test_impact_answers_match_gdmd_graph(model):
    q = ANSWERS["s2_impact_tokens"]["questions"]["Q1"]
    res = impact(model, model.by_id[q["start"]])
    got = {model.blocks[n].token_id for n, _, occs in res
           if not isinstance(n, tuple) and model.blocks[n].has_identity}
    assert got == set(q["answer"])
    q = ANSWERS["s2_impact_files"]["questions"]["Q1"]
    res = impact(model, model.by_id[q["start"]])
    subfiles = {pf.rel_str for pf in model.tree.files if pf.file_type == "subfile"}
    got = {model.blocks[n].path for n, _, _ in res
           if not isinstance(n, tuple) and model.blocks[n].has_identity
           and model.blocks[n].path in subfiles}
    assert got == set(q["answer"])


def test_prose_mentions_are_not_value_edges(model):
    """The graph's impact also lists prose leaves; the oracle (value edges
    only) excludes them, as D-026 amendment 1's prompts say."""
    q = ANSWERS["s2_impact_tokens"]["questions"]["Q1"]
    res = impact(model, model.by_id[q["start"]])
    roles = {model.blocks[n].role for n, _, _ in res if not isinstance(n, tuple)}
    assert roles <= {"token", "content-entity", "rationale", "meta", "invariant"}


# ---- lint, schema, content --------------------------------------------------------------

def _normalized_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "lanternfall"
    shutil.copytree(TREE, dest)
    for dirpath, _, names in os.walk(dest):
        for n in names:
            os.utime(Path(dirpath) / n, (fixture.FIXTURE_MTIME, fixture.FIXTURE_MTIME))
    return dest


def _lint(exe: list[str], root: Path) -> dict:
    return json.loads(subprocess.run([*exe, "lint", str(root)], capture_output=True,
                                     text=True).stdout)


def test_lints_clean_under_the_matrix_gdmd(tmp_path):
    res = _lint([str(REPO_ROOT / ".venv/bin/gdmd")] if (REPO_ROOT / ".venv/bin/gdmd").exists()
                else ["gdmd"], _normalized_copy(tmp_path))
    assert (res["summary"]["errors"], res["summary"]["warnings"]) == (0, 0), res["findings"]


@pytest.mark.skipif(not V03_GDMD.is_file(), reason="v0.3 venv not installed")
def test_lints_identically_under_the_v03_gdmd(tmp_path):
    root = _normalized_copy(tmp_path)
    v03 = _lint([str(V03_GDMD)], root)
    assert (v03["summary"]["errors"], v03["summary"]["warnings"]) == (0, 0)
    here = _lint([str(REPO_ROOT / ".venv/bin/gdmd")] if (REPO_ROOT / ".venv/bin/gdmd").exists()
                 else ["gdmd"], root)
    assert here == v03


def test_every_frontmatter_block_is_schema_valid_and_content_validates():
    v = jsonschema.Draft202012Validator(
        json.loads((REPO_ROOT / "schema/game-design.schema.json").read_text()))
    blocks = 0
    for p in sorted(TREE.rglob("*")):
        if p.suffix in (".md", ".yaml") and (fm := loader.read(p)[0]) is not None:
            blocks += 1
            assert not list(v.iter_errors(fm)), p
    assert blocks == 340
    entities = 0
    for cs in sorted((TREE / "gdd/content").glob("*.md")):
        fm = loader.read(cs)[0]
        if fm.get("file_type") != "content-schema":
            continue
        ev = jsonschema.Draft202012Validator(fm["schema"])
        for e in sorted((cs.parent / fm["data_dir"]).resolve().glob("*.yaml")):
            doc = loader.read(e)[0]
            assert not list(ev.iter_errors(doc)) and doc["id"] == e.stem, e
            entities += 1
    assert entities == 320


# ---- D-026 §7: no leak from the in-context spec ---------------------------------------

def _has_v03_tag() -> bool:
    return subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "-q", "--verify",
                           "v0.3.0^{commit}"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _has_v03_tag(), reason="needs the v0.3.0 tag")
def test_no_tree_token_id_in_what_claude_md_imports():
    res = gen.leak_check(REPO_ROOT, EDGES)
    assert res["hits"] == {}
    assert set(res["exempt"]) <= gen.LEAK_EXEMPT
    # the exempt collection tokens are never a question's start or answer
    for task in ANSWERS.values():
        for q in (task.get("questions") or {}).values():
            assert q["start"] not in gen.LEAK_EXEMPT
            assert not set(q["answer"]) & gen.LEAK_EXEMPT


def test_imported_files_cover_both_worlds_and_the_card():
    if not _has_v03_tag():
        pytest.skip("needs the v0.3.0 tag")
    v03 = gen.imported_files(REPO_ROOT, "v0.3")
    mat = gen.imported_files(REPO_ROOT, "matrix")
    for world in (v03, mat):
        assert {"CLAUDE.md", "AGENTS.md", "docs/spec.md", "schema/game-design.schema.json",
                "examples/deckbuilder/game-design.md"} <= set(world)
    assert "docs/spec-card.md" in mat
