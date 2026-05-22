"""Distribution-type coverage: linter accepts all six v0.1 distribution shapes.

The on-disk fixtures `pity_floor/` and `deterministic/` exercise those two
specifically (per Step 4 brief). `uniform`, `weighted`, `shuffle_bag`,
`gaussian` are exercised in test_lint.test_baseline_lints_clean +
test_deckbuilder.
"""
from __future__ import annotations

from game_design_md import linter
from game_design_md.tree import Tree


def _lint(root):
    return linter.run_all(Tree.load(root))


def test_pity_floor_loads_and_lints(fixture_overlay):
    res = _lint(fixture_overlay("pity_floor"))
    # pity_floor specifically must not break the loader or any rule.
    assert res.errors == 0, [f.message for f in res.findings if f.severity == "error"]


def test_deterministic_loads_and_lints(fixture_overlay):
    res = _lint(fixture_overlay("deterministic"))
    assert res.errors == 0, [f.message for f in res.findings if f.severity == "error"]


def test_pity_floor_token_registered(fixture_overlay):
    tree = Tree.load(fixture_overlay("pity_floor"))
    _pf, value = tree.tokens["distributions"]["distributions.test_dist"]
    assert value["type"] == "pity_floor"
    assert value["pity"]["rare_within"] == 12


def test_deterministic_token_registered(fixture_overlay):
    tree = Tree.load(fixture_overlay("deterministic"))
    _pf, value = tree.tokens["distributions"]["distributions.test_dist"]
    assert value["type"] == "deterministic"
    assert value["sequence"] == ["a", "b", "c", "a", "b", "c"]
