"""Golden outputs and the budget for `gdmd view` / `gdmd graph` (D-027 Tests).

Goldens: every view and graph mode, text and JSON, on the hand-written
fixture tree `tests/fixtures/views/tree/` (not on `examples/`). They pin
the output format; the properties behind it are tested in test_ir.py,
test_view.py and test_graph.py. After an intended format change, regenerate
with `GDMD_UPDATE_GOLDENS=1 pytest tests/test_views_golden.py` and review the
diff before committing.

Budget (D-027 decision 14): compile + emit ≤ 150 ms in-process per in-repo
tree. Measured in-process only; there is no wall-clock gate.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from game_design_md.cli import main
from game_design_md.graph_cmd import run_graph
from game_design_md.ir import compile_tree
from game_design_md.view_cmd import run_view
from tests.conftest import FIXTURES_DIR, IN_REPO_TREES, REPO_ROOT

TREE = FIXTURES_DIR / "views" / "tree"
GOLDEN = FIXTURES_DIR / "views" / "golden"
UPDATE = os.environ.get("GDMD_UPDATE_GOLDENS") == "1"

VIEW_CASES = {
    "overview": {},
    "full": {"full": True},
    "grep": {"grep": "focus"},
    "grep-ignore-case": {"grep": "LAMP", "ignore_case": True},
    "ref-hops1": {"ref": "{resources.focus}"},
    "ref-hops2": {"ref": "{resources.focus}", "hops": 2},
    "ref-subpath": {"ref": "{rules.study_rule.do}"},
    "flat": {"flat": True},
    "flat-grep": {"grep": "draft", "flat": True},
    "flat-ref": {"ref": "{verbs.study}", "hops": 2, "flat": True},
    "role-full-invariant": {"full": True, "roles": ("invariant",)},
    "role-overview-rationale": {"roles": ("rationale",)},
    "role-grep-impl": {"grep": "src/sim", "roles": ("impl",)},
    "flat-content-entities": {"flat": True, "roles": ("content-entity",)},
}

GRAPH_CASES = {
    "graph-all": {},
    "graph-impact": {"impact_arg": "{resources.focus}"},
    "graph-paths": {"from_arg": "{loops.day}", "to_arg": "{entities.player}"},
    "graph-paths-max1": {"from_arg": "{loops.day}", "to_arg": "{entities.player}",
                         "max_paths": 1},
    "graph-cycles": {"want_cycles": True},
}


@pytest.fixture(scope="module")
def model():
    return compile_tree(TREE)


def _check(name: str, got: str) -> None:
    path = GOLDEN / name
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(got + "\n", encoding="utf-8")
        return
    assert path.exists(), f"missing golden {path}; run with GDMD_UPDATE_GOLDENS=1"
    assert got + "\n" == path.read_text(encoding="utf-8"), name


@pytest.mark.parametrize("name", list(VIEW_CASES))
@pytest.mark.parametrize("fmt", ["txt", "json"])
def test_view_golden(model, name, fmt):
    kw = VIEW_CASES[name]
    _check(f"view-{name}.{fmt}", run_view(model, "tree", as_json=fmt == "json", **kw))


@pytest.mark.parametrize("name", list(GRAPH_CASES))
@pytest.mark.parametrize("fmt", ["text", "json", "dot"])
def test_graph_golden(model, name, fmt):
    ext = {"text": "txt", "json": "json", "dot": "dot"}[fmt]
    _check(f"{name}.{ext}", run_graph(model, "tree", fmt=fmt, **GRAPH_CASES[name]))


def test_fixture_exercises_what_the_goldens_claim(model):
    """Guards the fixture itself: each edge case the goldens rely on exists."""
    outcomes = {o.outcome for o in model.occurrences}
    assert outcomes == {"resolved", "unresolved", "context-local"}
    assert any(o.source is None for o in model.occurrences)           # a gap-line ref
    assert any(b.role == "impl" and b.parent is not None for b in model.blocks)
    assert any(b.explains == "invariants.focus_is_integer" for b in model.blocks)
    assert sum(b.role == "content-entity" for b in model.blocks) == 2
    two = run_graph(model, "tree", from_arg="{loops.day}", to_arg="{entities.player}",
                    max_paths=1)
    assert two.split("\n")[-1] == "… 1 of 2 shortest paths"


# ---- determinism and no writes for graph (views: test_view.py) -------------------

def test_graph_is_deterministic_and_writes_nothing(tmp_path: Path):
    t = tmp_path / "t"
    shutil.copytree(TREE, t)
    before = {p: p.stat().st_mtime_ns for p in t.rglob("*")}
    r = CliRunner()
    for args in ([], ["--impact", "{resources.focus}"], ["--cycles", "--format", "dot"],
                 ["--from", "{loops.day}", "--to", "{resources.focus}", "--format", "json"]):
        a = r.invoke(main, ["graph", str(t), *args])
        b = r.invoke(main, ["graph", str(t), *args])
        assert a.exit_code == 0 and a.output == b.output
    assert {p: p.stat().st_mtime_ns for p in t.rglob("*")} == before


# ---- budget ------------------------------------------------------------------------

BUDGET_MS = 150


@pytest.mark.parametrize("tree", IN_REPO_TREES)
def test_budget_compile_and_emit_in_process(tree):
    """Compile + the largest emit (`--full --json`) + the whole graph, best of 3."""
    root = REPO_ROOT / tree
    best = float("inf")
    for _ in range(3):
        start = time.perf_counter()
        m = compile_tree(root)
        run_view(m, tree, full=True, as_json=True)
        run_graph(m, tree)
        best = min(best, (time.perf_counter() - start) * 1000)
    assert best <= BUDGET_MS, f"{tree}: {best:.0f} ms > {BUDGET_MS} ms"
