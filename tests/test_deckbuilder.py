"""End-to-end: gdmd lint examples/deckbuilder exits clean (the §11.1 exit gate)."""
from __future__ import annotations

from pathlib import Path

from game_design_md import linter
from game_design_md.tree import Tree

REPO_ROOT = Path(__file__).resolve().parents[1]
DECKBUILDER = REPO_ROOT / "examples" / "deckbuilder"


def test_deckbuilder_exists():
    assert DECKBUILDER.is_dir(), f"deckbuilder example not found at {DECKBUILDER}"


def test_deckbuilder_lints_clean():
    tree = Tree.load(DECKBUILDER)
    result = linter.run_all(tree)
    errors = [f for f in result.findings if f.severity == "error"]
    assert errors == [], (
        "Deckbuilder must lint clean (the Step 4 exit gate):\n"
        + "\n".join(f"  {f.rule} :: {f.file} :: {f.message}" for f in errors)
    )
    assert result.exit_code == 0


def test_deckbuilder_all_grafts_present():
    """Sanity: the deckbuilder still exercises all three grafts."""
    tree = Tree.load(DECKBUILDER)
    # Graft A: invariants present, covering numeric_domain + determinism kinds.
    inv_kinds = {
        v["kind"]
        for v in (
            tree.tokens.get("invariants", {}).values()
            and (val for _pf, val in tree.tokens["invariants"].values())
        )
    }
    assert "numeric_domain" in inv_kinds
    assert "determinism" in inv_kinds
    # Graft B: at least one state machine with a terminal node.
    machines = [v for _pf, v in tree.tokens["states"].values()]
    assert any(
        any(n.get("terminal") for n in m["nodes"]) for m in machines
    )
    # Graft C: verify_targets wired to win_rate_ascension_0.
    verify_pf = tree.by_rel.get("gdd/verification.md")
    assert verify_pf is not None
    targets = verify_pf.frontmatter.get("verify_targets") or []
    assert any("win_rate_ascension_0" in (t.get("target") or "") for t in targets)
