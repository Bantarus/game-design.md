"""`gdmd hook check --show-tokens` (WS3, spec §9.7, D-028).

Proof of fire on a real tree (tick-combat's own engine paths), plus the three
reference kinds on the hand-written views fixture tree.
"""
from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from click.testing import CliRunner

from game_design_md.cli import main
from game_design_md.ir import compile_tree
from tests.conftest import FIXTURES_DIR, REPO_ROOT

HEADER_RE = re.compile(r"^\[(token|invariant|content-entity|impl|meta|rationale)\] \S+ "
                       r"(\S+):(\d+)-(\d+)")


def _check_verbatim(root: Path, out: str) -> list[str]:
    """Every source line printed under a block header is the file's line at
    its number. A nested header (a child block) sits at the current position
    and does not end the enclosing block. Returns the headers seen."""
    headers, cur = [], None          # cur = [path, next line, last line]
    for line in out.split("\n"):
        m = HEADER_RE.match(line)
        if m:
            headers.append(line)
            path, a, z = m.group(2), int(m.group(3)), int(m.group(4))
            if cur and cur[1] <= cur[2]:
                assert (path, a) == (cur[0], cur[1]), (line, cur)   # nested, in place
            else:
                cur = [path, a, z]
            continue
        if cur and cur[1] <= cur[2]:
            src = (root / cur[0]).read_text(encoding="utf-8").split("\n")
            assert line == src[cur[1] - 1], (cur, line)
            cur[1] += 1
            continue
        cur = None
    return headers


def _strip_blocks(out: str) -> str:
    """The report with every printed block (headers and source lines) removed."""
    kept, remaining = [], 0
    for ln in out.split("\n"):
        m = HEADER_RE.match(ln)
        if m:
            if remaining == 0:
                remaining = int(m.group(4)) - int(m.group(3)) + 1
            continue
        if remaining:
            remaining -= 1
            continue
        kept.append(ln)
    return "\n".join(kept)


def test_real_tree_proof_of_fire():
    root = REPO_ROOT / "examples/tick-combat"
    r = CliRunner().invoke(main, ["hook", "check", str(root),
                                  str(root / "impl/xtreme/src/rules.rs"), "--show-tokens"])
    assert r.exit_code == 0
    headers = _check_verbatim(root, r.output)
    assert "[impl] game-design.md#implementation_pointers game-design.md:37-39" in headers
    assert any(h.startswith("[impl] gdd/mechanics.md#implemented_in ") for h in headers)
    assert any(h.startswith("[token] {rules.tick_resolution} ") for h in headers)
    assert any(h.startswith("[token] {rules.combat_resolution} ") for h in headers)
    # the existing report is still there, unchanged in shape
    assert "locations:    (file-level), rules.combat_resolution, rules.tick_resolution" \
        in r.output


def test_default_output_is_unchanged():
    root = REPO_ROOT / "examples/tick-combat"
    staged = str(root / "impl/xtreme/src/rules.rs")
    plain = CliRunner().invoke(main, ["hook", "check", str(root), staged]).output
    shown = CliRunner().invoke(main, ["hook", "check", str(root), staged,
                                      "--show-tokens"]).output
    assert not any(HEADER_RE.match(ln) for ln in plain.split("\n"))
    # --show-tokens only inserts blocks; removing them gives the plain report
    assert _strip_blocks(shown) == plain


def test_reference_kinds_on_the_fixture_tree(tmp_path: Path):
    t = tmp_path / "t"
    shutil.copytree(FIXTURES_DIR / "views/tree", t)
    for rel in ("src/sim/focus.py", "src/sim/relics/lamp.py"):
        (t / rel).parent.mkdir(parents=True, exist_ok=True)
        (t / rel).write_text("# code\n")
    r = CliRunner().invoke(main, ["hook", "check", str(t), str(t / "src/sim/focus.py"),
                                  str(t / "src/sim/relics/lamp.py"), "--show-tokens"])
    assert r.exit_code == 0
    headers = _check_verbatim(t, r.output)
    m = compile_tree(t)
    focus = m.blocks[m.by_id["resources.focus"]]
    assert focus.header() in headers                                    # token-level
    assert any(h.startswith("[impl] gdd/mechanics.md#implemented_in ") for h in headers)
    lamp = m.blocks[m.by_id["entities.relics.lamp"]]
    assert lamp.header() in headers                                     # entity file-level
    assert "[impl] game-design.md#implementation_pointers game-design.md:23-24" in headers


def test_no_match_is_silent_and_exit_0(tmp_path: Path):
    t = tmp_path / "t"
    shutil.copytree(FIXTURES_DIR / "views/tree", t)
    r = CliRunner().invoke(main, ["hook", "check", str(t), "README.md", "--show-tokens"])
    assert r.exit_code == 0 and r.output == ""


def test_under_one_second_on_every_in_repo_tree():
    from tests.conftest import IN_REPO_TREES
    for tree in IN_REPO_TREES:
        root = REPO_ROOT / tree
        staged = [str(p) for p in list(root.rglob("*.py"))[:20] + list(root.rglob("*.rs"))[:20]]
        start = time.perf_counter()
        r = CliRunner().invoke(main, ["hook", "check", str(root), *staged, "--show-tokens"])
        assert r.exit_code == 0
        assert time.perf_counter() - start < 1.0, tree
