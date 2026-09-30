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


# ---- D-026 amendment 6: no copy file outside the tree names a question ------------------

def _question_ids() -> set[str]:
    """Every tree token a question starts from, answers with, or (impact) closes over."""
    ids: set[str] = set()
    for task in ANSWERS.values():
        for q in (task.get("questions") or {}).values():
            ids |= {q["start"], *q["answer"], *q.get("closure", [])}
    return ids & set(EDGES["nodes"])


def _naming_files(base: Path, skip: tuple[str, ...] = ()) -> dict[str, set[str]]:
    """Files under `base` naming a question id: the full id, or its bare id when
    compound (the §7 leak-check convention). `.git` and `skip` are not read."""
    ids = _question_ids()
    bare = {n.split(".")[-1]: n for n in ids if "_" in n.split(".")[-1]}
    pat = re.compile("|".join([re.escape(n) for n in sorted(ids, key=len, reverse=True)]
                              + [rf"\b{re.escape(b)}\b" for b in sorted(bare)]))
    hits: dict[str, set[str]] = {}
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base).as_posix()
        if not p.is_file() or rel.split("/")[0] == ".git" or rel.startswith(skip):
            continue
        for m in pat.findall(p.read_bytes().decode("utf-8", "ignore")):
            hits.setdefault(rel, set()).add(bare.get(m, m))
    return hits


def test_the_scan_fires_on_the_repos_decisions_file():
    """Proof of fire: the freeze amendment's question table and hand traces."""
    named = set().union(*(_naming_files(REPO_ROOT, skip=("benchmark/", "examples/",
                                                         "templates/", "tests/", "src/",
                                                         "docs/", "schema/")).values()))
    assert len(named) >= 30
    assert "entities.encounters.lich_hollow" in named


# Other trees' own tokens that share a name with a Lanternfall question id. Both
# predate the generator (dc12419 and 0562909, May 2026) and say nothing about it.
COINCIDENT = {"benchmark/games/platformer/game-design.md": {"loops.expedition"},
              "benchmark/games/platformer/gdd/loops.md": {"loops.expedition"},
              "examples/party-rpg/gdd/mechanics.md": {"rules.spawn_encounter"}}


@pytest.mark.skipif(not _has_v03_tag(), reason="needs the v0.3.0 tag")
def test_no_copy_file_outside_the_tree_names_a_question(tmp_path):
    """Every study-2 cell type (baseline in the v0.3 world; views and
    import-full in the matrix world; import-card with its card): no file of the
    copy outside `examples/lanternfall/` names a question's start, answer or
    closure, except the pinned coincidences. DECISIONS.md did, so copies no
    longer carry it (amendment 6)."""
    cells = {"baseline": ("v0.3", False), "views/import-full": ("matrix", False),
             "import-card": ("matrix", True)}
    for name, (world, card) in cells.items():
        c = fixture.prepare_copy(TASKS["s2_lookup_forward"], tmp_path / name.replace("/", "-"),
                                 world=world, card=card)
        for rel in ("DECISIONS.md", "tests/test_dogfood_study2.py", "tests/test_dogfood.py",
                    "benchmark/dogfood"):
            assert not (c.root / rel).exists(), (name, rel)
        assert _naming_files(c.root, skip=(PLACED + "/",)) == COINCIDENT, name


def test_reading_the_real_decisions_file_is_contamination():
    import analyze
    for path in ("/home/u/game-design/DECISIONS.md",
                 "/home/u/game-design/tests/test_dogfood_study2.py"):
        assert analyze.contaminated({}, {"out_of_copy_access": [
            {"tool": "Read", "file_path": path}]}) == [path]


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


# ---- Rules V2 and C2 (D-026), committed before any study-2 data ---------------------------

import analyze  # noqa: E402


def _s2_lines(arms: tuple[str, str], metric: str, by_arm: dict, fail=(), repeats=(1, 2, 3)):
    out = []
    for t in S2:
        for arm in arms:
            for r in repeats:
                out.append({"run_id": "s2", "cell_id": f"{t}__{arm}__r{r}", "task_id": t,
                            "study": 2, "arm": arm, "repeat": r,
                            "outcome": "fail" if (t, arm, r) in fail else "success",
                            metric: by_arm[arm], "est_cost_usd": 1.0,
                            "gdmd_view_calls": 3 if arm == "views" else 0,
                            "gdmd_graph_calls": 0, "gdmd_spec_section_calls": 0})
    return out


def _v2(by_arm, **kw):
    return analyze.rule_v2(_s2_lines(("baseline", "views"), "consultation_bytes", by_arm, **kw),
                           metrics_loader=lambda ln: None)


def _c2(by_arm, delta=50_000, **kw):
    return analyze.rule_c2(_s2_lines(("import-full", "import-card"), "median_turn_occupancy",
                                     by_arm, **kw), delta, metrics_loader=lambda ln: None)


def test_rule_v2_thresholds_and_non_inferiority_at_18_runs_per_arm():
    assert _v2({"baseline": 1000, "views": 600})["verdict"] == "PASS"
    assert _v2({"baseline": 1000, "views": 800})["verdict"] == "NULL"
    assert _v2({"baseline": 1000, "views": 1000})["verdict"] == "FAIL"
    one = {("s2_lookup_forward", "views", 1)}
    res = _v2({"baseline": 1000, "views": 600}, fail=one)
    assert res["non_inferiority"]["runs"]["views"] == 18
    assert res["verdict"] == "PASS"                          # 1/18 fewer: within 10 points
    two = one | {("s2_impact_files", "views", 2)}
    assert _v2({"baseline": 1000, "views": 600}, fail=two)["verdict"] == "FAIL"   # 2/18


def test_rule_v2_guards_study2_tasks():
    res = _v2({"baseline": 1000, "views": 600}, fail={("s2_maintenance", "views", 1)})
    assert set(res["non_inferiority"]["guarded"]) == set(analyze.GUARDED_S2)
    assert res["verdict"].startswith("PENDING")              # e_t = 1: the extension
    res = _v2({"baseline": 1000, "views": 600},
              fail={("s2_negative_control", "views", 1), ("s2_negative_control", "views", 2)})
    assert res["verdict"] == "FAIL"                          # e_t >= 2


def test_rule_c2():
    assert _c2({"import-full": 90_000, "import-card": 60_000})["verdict"] == "PASS"
    assert _c2({"import-full": 90_000, "import-card": 70_000})["verdict"] == "NULL"
    res = _c2({"import-full": 90_000, "import-card": 60_000},
              fail={("s2_maintenance", "import-card", 3)})
    assert res["verdict"].startswith("PENDING")


# ---- D-026 amendment 7: another session's scratchpad is contamination --------------------

SID = "94068110-ec56-4230-a5c4-a1ea9c660af2"
LINE = {"run_id": "s2", "cell_id": "s2_lookup_forward__views__r1", "session_id": SID}
OWN = "/tmp/claude-1000/-tmp-gdmd-dogfood-s2-s2-lookup-forward--views--r1-repo"


@pytest.mark.parametrize("path,kind", [
    (f"{OWN}/{SID}/scratchpad/g.py", "own"),
    (f"{OWN}/51022e8c-0dfb-4fa8-bdb0-07b4c8ca1a29/scratchpad", "own"),   # the CLI's own sibling
    (OWN, "own"),
    ("/tmp/claude-1000/-tmp-gdmd-dogfood-s2-s2-lookup-forward--views--r2-repo/x/scratchpad/g.py",
     "other"),                                                            # the next repeat
    ("/tmp/claude-1000/-tmp-gdmd-dogfood-s1-s2-lookup-forward--views--r1-repo/x/out.txt",
     "other"),                                                            # another run's cell
    ("/tmp/claude-1000/-home-u-game-design/9f18/scratchpad/notes.txt", "other"),  # the operator
    ("/tmp/claude-1000", "other"),
    ("/tmp/claude-1000/", "other"),
    ("/tmp/claude-1000/*/scratchpad", "other"),
    ("/tmp/claude-*/", "other"),
    # amendment 8: a copy-key glob followed by the run's own session id is own use
    (f"/tmp/claude-1000/*/{SID[:8]}*/scratchpad/g.py", "own"),     # study 2's V2 case
    (f"/tmp/claude-*/*/{SID}/scratchpad/g.py", "own"),
    (f"/tmp/claude-1000/*/{SID[:7]}*/scratchpad/g.py", "other"),   # too short to name it
    ("/tmp/claude-1000/*/51022e8c*/scratchpad", "other"),          # another session's id
    ("/tmp/claude-1000/*/*/scratchpad/g.py", "other"),
    (f"/tmp/claude-1000/-tmp-gdmd-dogfood-s1-x-repo/{SID}/g.py", "other"),  # literal other key
    ("../../claude-1000/-tmp-gdmd-dogfood-s1-x-repo/y", "other"),
    ("/tmp/gdmd-dogfood/s2/judge/src", None),
    ("/home/u/.claude/projects/x.jsonl", None),
])
def test_scratchpad_access_is_own_or_other(path, kind):
    assert analyze.scratchpad_access(LINE, path) == kind
    assert analyze.contaminated(LINE, {"out_of_copy_access": [
        {"tool": "Bash", "path": path}]}) == ([path] if kind == "other" else [])


def test_other_session_scratchpad_is_not_success_and_listed():
    lines = _s2_lines(("baseline", "views"), "consultation_bytes",
                      {"baseline": 1000, "views": 600})
    hit = "s2_lookup_forward__views__r1"
    leak = {"out_of_copy_access": [
        {"tool": "Read", "file_path": "/tmp/claude-1000/-tmp-gdmd-dogfood-s2-"
                                      "s2-lookup-forward--views--r2-repo/x/scratchpad/out.txt"},
        {"tool": "Bash", "path": f"{OWN}/{SID}/scratchpad/g.py"}]}
    res = analyze.rule_v2(lines, metrics_loader=lambda ln: leak if ln["cell_id"] == hit else None)
    assert list(res["apparatus"]["contaminated"]) == ["s2_lookup_forward/views/r1"]
    assert res["apparatus"]["contaminated"]["s2_lookup_forward/views/r1"] == [
        leak["out_of_copy_access"][0]["file_path"]]                 # own use is not listed there
    assert res["non_inferiority"]["successes"]["views"] == 17


def test_amendment_8_recomputes_v2_with_no_contamination_and_the_same_verdict():
    """V2's recorded result (1 contaminated, baseline 17/18 counted) stands as
    committed; the refined detector, recomputed on the same lines, counts 0."""
    res = analyze.rule_v2(analyze.load([analyze.RESULTS_DIR / "rulev2-20260930.jsonl"]))
    assert res["apparatus"]["contaminated"] == {}
    assert res["non_inferiority"]["successes"] == {"baseline": 18, "views": 18}
    assert res["verdict"] == "PASS" and round(res["R"], 4) == 0.3332


def test_the_pilots_scratchpad_use_was_all_own_session():
    """On the committed pilot metrics: 18 scratchpad accesses in 3 runs, every one
    inside the run's own session directory. Re-keyed to another cell, the same
    accesses are contamination (proof of fire on real paths)."""
    lines = analyze.load([analyze.RESULTS_DIR / "pilot-s2-20260930.jsonl"])
    own, fired = 0, 0
    for ln in lines:
        paths = [str(e.get("path") or e.get("file_path"))
                 for e in analyze.metrics_for(ln)["out_of_copy_access"]]
        for p in paths:
            kind = analyze.scratchpad_access(ln, p)
            assert kind != "other", (ln["cell_id"], p)
            if kind == "own":
                own += 1
                assert f"/{ln['session_id']}/" in p
        other = dict(ln, cell_id=ln["cell_id"].replace("__r1", "__r2"))
        fired += len(analyze.contaminated(other, analyze.metrics_for(ln)))
        assert analyze.contaminated(ln, analyze.metrics_for(ln)) == []
    assert (own, fired) == (18, 18)


def test_each_rule_refuses_the_other_studys_lines():
    s2 = _s2_lines(("baseline", "views"), "consultation_bytes", {"baseline": 1, "views": 1})
    s1 = [dict(ln, study=1) for ln in s2]
    with pytest.raises(SystemExit):
        analyze.rule_v2(s1, metrics_loader=lambda ln: None)
    no_field = [{k: v for k, v in ln.items() if k != "study"} for ln in s2]
    with pytest.raises(SystemExit):
        analyze.rule_v2(no_field, metrics_loader=lambda ln: None)   # pre-study-2 lines
    with pytest.raises(SystemExit):
        analyze.only_study(s2, 1)


# ---- the freeze (D-026 amendment 5) --------------------------------------------------------

FROZEN_SHA256 = {
    "answers/s2_impact_files.json": "b631b17472115fcaf590207b15d205358c3892e202349f66258abddd8421fc61",
    "answers/s2_impact_tokens.json": "2f69fe27fb18e8585d511e89ccfe64a65a2a4488cead8404eb7433edebf1cf63",
    "answers/s2_lookup_backward.json": "66c4bea72e4b64400c61f94865cc01c4143edc96e1480dd8c4a3c0b9e7365942",
    "answers/s2_lookup_forward.json": "1691637f0de8f979087f5335a8d60a6c70f7396b163f444d755533dd543d399d",
    "answers/s2_maintenance.json": "3dfc8b51987646ebcfc44e81a851b33ce887d7a6013d31071fdd429cb34403b9",
    "answers/s2_negative_control.json": "b1cb282ada17090b544f329668027454cf4751b9e9ee077b4bf9e7b1d44883aa",
    "prompts/s2_impact_files.md": "9b9d6805f2a39a389de72b6ef0ccc731f19a4ea98894cd7cf0443a64da25487f",
    "prompts/s2_impact_tokens.md": "ae710b40dd32c80f2e1371b77935ebc5ba8da648feeda7c70e8de827cd137112",
    "prompts/s2_lookup_backward.md": "2f2a8298e1f9b9df1c5876f47f2c6308a51f77bfae8fc0acfb3d0a69b2b8359a",
    "prompts/s2_lookup_forward.md": "5c416d6166062732caba7c35a1c3c37876bea694d453379597d77076ca13b436",
    "prompts/s2_maintenance.md": "57edae8e80924c9df4d4ed71ef03a7024a668ed7798809c939a63dccf998591d",
    "prompts/s2_negative_control.md": "57edae8e80924c9df4d4ed71ef03a7024a668ed7798809c939a63dccf998591d",
    "patches/s2_maintenance.patch": "c8b9e6f9f4399b342dd2d05ca4abfe0018f437184573c438a0fbab059f2f60e9",
    "patches/s2_negative_control.patch": "9f782c497a115528db3817166f04f873a9a61b2766b78bfded4d577ac734abfb",
    "edges.json": "e46319f0824bbdb5efdd921dcb094a36de11a39485679a6149fb1c112fcb2f9b",
}


def test_frozen_files_match_the_freeze_amendment():
    import hashlib
    for rel, want in FROZEN_SHA256.items():
        assert hashlib.sha256((STUDY2 / rel).read_bytes()).hexdigest() == want, rel
    assert fixture.tree_manifest_sha256(TREE) == fixture.FIXTURE_TREE_SHA256["study2"]


def test_a_changed_tree_is_refused(tmp_path, monkeypatch):
    monkeypatch.setitem(fixture.FIXTURE_TREE_SHA256, "study2", "0" * 64)
    with pytest.raises(fixture.FixtureError, match="pinned manifest"):
        _copy("s2_lookup_forward", tmp_path)
