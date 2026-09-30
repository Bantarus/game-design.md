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
import re
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


# ---- the harness: placement, guarded fixtures, checkers, --study (D-026) -------------------

import run as dogfood_run  # noqa: E402

TASKS = fixture.load_tasks()
S2 = sorted(t for t in TASKS if TASKS[t].study == 2)
PLACED = "examples/lanternfall"


def _copy(task: str, tmp_path: Path, world: str = "matrix", judge=None, card=False):
    return fixture.prepare_copy(TASKS[task], tmp_path / f"{task}-{world}", world=world,
                                judge=judge, card=card)


def _gdmd(copy, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["gdmd", *args], cwd=copy.root, env=copy.env(),
                          capture_output=True, text=True)


def _check(task: str, copy) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(TASKS[task].checker_path), str(copy.root)],
                          env=copy.env(), capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


def _failed(report: dict) -> set[str]:
    return {k for k, v in report["criteria"].items() if not v["pass"]}


def test_study2_registry():
    assert S2 == ["s2_impact_files", "s2_impact_tokens", "s2_lookup_backward",
                  "s2_lookup_forward", "s2_maintenance", "s2_negative_control"]
    for t in S2:
        task = TASKS[t]
        assert task.tree == PLACED and task.fixture_tree == "study2"
        assert task.prompt_path.is_file() and task.checker_path.is_file()
        assert task.prompt() == (STUDY2 / "prompts" / f"{t}.md").read_text()
    assert TASKS["s2_maintenance"].prompt() == TASKS["s2_negative_control"].prompt()
    assert all(TASKS[t].study == 1 for t in TASKS if not t.startswith("s2_"))


def test_prompts_name_only_the_start_tokens():
    for t in ("s2_lookup_forward", "s2_lookup_backward", "s2_impact_tokens", "s2_impact_files"):
        prompt = TASKS[t].prompt()
        assert f"answers/{t}.txt" in prompt
        named = set(re.findall(r"\{([a-z_]+\.[a-z0-9_.]+)\}", prompt))
        starts = {q["start"] for q in ANSWERS[t]["questions"].values()}
        # the only tree tokens a prompt names are its questions' start tokens;
        # the rest are generic placeholders ({ns.id}, {entities.<kind>.<id>})
        assert named & set(EDGES["nodes"]) == starts, (t, named)
        assert not {n for n in named - starts
                    if n.split(".")[0] not in ("ns", "namespace", "verbs", "entities")}
        for q in ANSWERS[t]["questions"].values():
            assert not set(q["answer"]) & named


def test_copy_places_the_tree_in_the_baseline_commit(tmp_path):
    c = _copy("s2_lookup_forward", tmp_path)
    assert (c.root / PLACED / "game-design.md").is_file()
    assert not (c.root / "benchmark/dogfood").exists()
    tracked = fixture.git(c.root, "ls-files", PLACED).splitlines()
    assert len(tracked) == sum(1 for p in TREE.rglob("*") if p.is_file()
                               and "__pycache__" not in p.parts)
    for rel in tracked[:: max(1, len(tracked) // 25)]:
        assert (c.root / rel).read_bytes() == (TREE / rel[len(PLACED) + 1:]).read_bytes()
    res = json.loads(_gdmd(c, "lint", PLACED).stdout)["summary"]
    assert (res["errors"], res["warnings"]) == (0, 0)


def test_study1_copies_do_not_get_the_tree(tmp_path):
    c = fixture.prepare_copy(TASKS["lookup_refs"], tmp_path / "s1")
    assert not (c.root / PLACED).exists()


def test_judge_agrees_in_both_worlds_before_and_after_the_patches(tmp_path):
    sha = fixture.git(REPO_ROOT, "rev-parse", "HEAD")
    judge = fixture.make_judge(tmp_path / "judge", sha)
    worlds = ["matrix"] + (["v0.3"] if V03_GDMD.is_file() else [])
    for world in worlds:
        for t in ("s2_lookup_forward", "s2_maintenance", "s2_negative_control"):
            c = _copy(t, tmp_path, world=world, judge=judge)   # raises on disagreement
            assert c.world == world
    c = _copy("s2_impact_tokens", tmp_path, judge=judge, card=True)
    assert (c.root / "docs/spec-card.md").is_file()


def test_maintenance_fixture_makes_exactly_the_two_subfiles_stale(tmp_path):
    c = _copy("s2_maintenance", tmp_path)
    changed = fixture.git(c.root, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert changed == [ANSWERS["s2_maintenance"]["patched"]]
    res = json.loads(_gdmd(c, "lint", PLACED).stdout)
    warn = sorted((f["rule"], f["file"]) for f in res["findings"] if f["severity"] != "info")
    assert warn == [("stale-section", "gdd/systems/distributions.md"),
                    ("stale-section", "gdd/systems/loot.md")]
    hook = _gdmd(c, "hook", "check", PLACED, *changed).stdout
    assert "gdd/systems/loot.md" in hook and "gdd/systems/distributions.md" in hook


def test_negative_control_fixture_is_invisible(tmp_path):
    c = _copy("s2_negative_control", tmp_path)
    changed = fixture.git(c.root, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert changed == [ANSWERS["s2_negative_control"]["patched"]]
    res = json.loads(_gdmd(c, "lint", PLACED).stdout)["summary"]
    assert (res["errors"], res["warnings"]) == (0, 0)
    assert _gdmd(c, "hook", "check", PLACED, *changed).stdout.strip() == ""


def _write_answer(c, task: str, tweak=None, paths=False) -> None:
    lines = []
    for q, spec in sorted(ANSWERS[task]["questions"].items()):
        items = list(spec["answer"])
        if tweak:
            items = tweak(q, items)
        lines.append(f"{q}:")
        lines += [x if paths else "{" + x + "}" for x in items]
    (c.root / "answers").mkdir(exist_ok=True)
    (c.root / "answers" / f"{task}.txt").write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize("task", ["s2_lookup_forward", "s2_lookup_backward",
                                  "s2_impact_tokens", "s2_impact_files"])
def test_answer_checkers(task, tmp_path):
    paths = task == "s2_impact_files"
    c = _copy(task, tmp_path)
    rc, rep = _check(task, c)
    assert rc == 1 and "answer_file_written" in _failed(rep)
    _write_answer(c, task, paths=paths)
    rc, rep = _check(task, c)
    assert rc == 0 and not _failed(rep), rep
    assert all(v["detail"]["jaccard"] == 1.0 for k, v in rep["criteria"].items()
               if k.endswith("_correct"))
    # normalizations: repo-relative paths, bullets, backticks, one-line lists
    if paths:
        _write_answer(c, task, tweak=lambda q, xs: [f"- `{PLACED}/{x}`" for x in xs],
                      paths=True)
    else:
        q1 = ANSWERS[task]["questions"]["Q1"]["answer"]
        rest = "".join(f"{q}:\n" + "\n".join(f"- `{x}`" for x in s["answer"]) + "\n"
                       for q, s in sorted(ANSWERS[task]["questions"].items()) if q != "Q1")
        (c.root / "answers" / f"{task}.txt").write_text(
            "Q1: " + ", ".join("{" + x + "}" for x in q1) + "\n" + rest)
    rc, rep = _check(task, c)
    assert rc == 0, rep
    # a missing item and an extra item each fail their question, with Jaccard < 1
    _write_answer(c, task, paths=paths, tweak=lambda q, xs: xs[1:] if q == "Q1" else xs)
    rc, rep = _check(task, c)
    assert rc == 1 and _failed(rep) == {"q1_correct"}
    assert rep["criteria"]["q1_correct"]["detail"]["jaccard"] < 1
    _write_answer(c, task, paths=paths,
                  tweak=lambda q, xs: xs + (["gdd/pillars.md"] if paths else
                                            ["loops.delve_turn"]) if q == "Q1" else xs)
    rc, rep = _check(task, c)
    assert rc == 1 and _failed(rep) == {"q1_correct"}
    # any other change fails
    _write_answer(c, task, paths=paths)
    (c.root / PLACED / "gdd/glossary.md").write_text("changed\n")
    rc, rep = _check(task, c)
    assert rc == 1 and "no_other_changes" in _failed(rep)


def test_maintenance_checker(tmp_path):
    c = _copy("s2_maintenance", tmp_path)
    rc, rep = _check("s2_maintenance", c)
    assert rc == 1 and {"touched_exactly_affected_sections", "lint_clean"} <= _failed(rep)
    for sub in ("gdd/systems/loot.md", "gdd/systems/distributions.md"):
        assert _gdmd(c, "touch", f"{PLACED}/{sub}").returncode == 0
    rc, rep = _check("s2_maintenance", c)
    assert rc == 0 and not _failed(rep), rep
    # touching a third subfile, or editing the implementation, fails
    assert _gdmd(c, "touch", f"{PLACED}/gdd/loops.md").returncode == 0
    rc, rep = _check("s2_maintenance", c)
    assert "touched_exactly_affected_sections" in _failed(rep)
    c2 = _copy("s2_maintenance", tmp_path / "b")
    for sub in ("gdd/systems/loot.md", "gdd/systems/distributions.md"):
        _gdmd(c2, "touch", f"{PLACED}/{sub}")
    impl = c2.root / ANSWERS["s2_maintenance"]["patched"]
    impl.write_text(impl.read_text() + "\n")
    rc, rep = _check("s2_maintenance", c2)
    assert "implementation_untouched" in _failed(rep)


def test_negative_control_checker(tmp_path):
    c = _copy("s2_negative_control", tmp_path)
    rc, rep = _check("s2_negative_control", c)
    assert rc == 0 and not _failed(rep), rep
    _gdmd(c, "touch", f"{PLACED}/gdd/systems/loot.md")
    rc, rep = _check("s2_negative_control", c)
    assert rc == 1 and "repository_unchanged" in _failed(rep)


def test_study_flag_selects_tasks_and_caps(tmp_path, capsys):
    assert dogfood_run.STUDY_CAPS[2] == {"turn_cap": 80, "timeout_s": 1800.0,
                                         "budget_usd": 5.0}       # D-026, as locked
    assert dogfood_run.STUDY_CAPS[1] == {"turn_cap": 60, "timeout_s": 1200.0,
                                         "budget_usd": 3.0}       # D-025
    with pytest.raises(SystemExit):
        dogfood_run.main(["--dry-run", "--task", "s2_lookup_forward"])     # study 1 default
    with pytest.raises(SystemExit):
        dogfood_run.main(["--dry-run", "--study", "2", "--task", "lookup_refs"])
