"""Diff: balance-target regression + status regression.

Each test writes the baseline into a *fresh* subdir of tmp_path to avoid the
'copy a dir into itself' trap.
"""
from __future__ import annotations

from pathlib import Path

from game_design_md import diff_cmd
from game_design_md.tree import Tree
from tests.conftest import BASELINE_FILES


def _write(dst: Path, files: dict[str, str]) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return dst


def test_no_change(tmp_path):
    a = _write(tmp_path / "a", BASELINE_FILES)
    b = _write(tmp_path / "b", BASELINE_FILES)
    out = diff_cmd.diff_trees(Tree.load(a), Tree.load(b))
    assert out["balance_regressions"] == []
    assert out["status_regressions"] == []
    assert out["changed"] == []


def test_balance_regression(tmp_path):
    """Move a balance target's value outside its previous tolerance band → regression."""
    old = _write(tmp_path / "old", BASELINE_FILES)
    new_files = dict(BASELINE_FILES)
    new_files["gdd/economy-balance.md"] = BASELINE_FILES["gdd/economy-balance.md"].replace(
        "target: 1\n    tolerance: [1, 1]",
        "target: 5\n    tolerance: [1, 1]",
    )
    new = _write(tmp_path / "new", new_files)
    out = diff_cmd.diff_trees(Tree.load(old), Tree.load(new))
    assert out["balance_regressions"], out
    assert out["balance_regressions"][0]["path"] == "balance_targets.energy_target.target"


def test_status_regression(tmp_path):
    """A token regresses from balanced (in old) to implemented (in new)."""
    old_bal = BASELINE_FILES["gdd/economy-balance.md"].replace(
        '    measure: "fixed"\n    status: prototyped',
        '    measure: "fixed"\n    status: balanced',
    )
    new_bal = BASELINE_FILES["gdd/economy-balance.md"].replace(
        '    measure: "fixed"\n    status: prototyped',
        '    measure: "fixed"\n    status: implemented',
    )
    old = _write(tmp_path / "old",
                 {**BASELINE_FILES, "gdd/economy-balance.md": old_bal})
    new = _write(tmp_path / "new",
                 {**BASELINE_FILES, "gdd/economy-balance.md": new_bal})
    out = diff_cmd.diff_trees(Tree.load(old), Tree.load(new))
    assert any(r["path"].endswith(".status") for r in out["status_regressions"]), \
        out["status_regressions"]


def test_added_removed(tmp_path):
    """Adding a token in new shows up in `added`."""
    old = _write(tmp_path / "old", BASELINE_FILES)
    extra = BASELINE_FILES["gdd/economy-balance.md"].replace(
        "balance_targets:\n  energy_target:",
        "balance_targets:\n  new_target:\n    target: 0\n    tolerance: [0, 0]\n"
        "    measure: \"new\"\n    status: prototyped\n  energy_target:",
    )
    new = _write(tmp_path / "new",
                 {**BASELINE_FILES, "gdd/economy-balance.md": extra})
    out = diff_cmd.diff_trees(Tree.load(old), Tree.load(new))
    assert "balance_targets.new_target" in out["added"]
