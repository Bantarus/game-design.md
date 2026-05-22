"""Tree loading + token indexing + ref resolution."""
from __future__ import annotations

from game_design_md.tree import Tree


def test_baseline_loads(make_tree):
    root = make_tree()
    tree = Tree.load(root)
    assert tree.core is not None
    assert tree.core.frontmatter["file_type"] == "core"
    assert "verbs.do_thing" in tree.tokens["verbs"]
    assert "loops.main" in tree.tokens["loops"]
    assert "states.thing_state" in tree.tokens["states"]


def test_has_token_direct(make_tree):
    tree = Tree.load(make_tree())
    assert tree.has_token("verbs.do_thing")
    assert tree.has_token("loops.main")


def test_has_token_state_node(make_tree):
    """States machine sub-nodes resolve by id."""
    tree = Tree.load(make_tree())
    assert tree.has_token("states.thing_state.a")
    assert tree.has_token("states.thing_state.b")
    assert not tree.has_token("states.thing_state.nonexistent")


def test_has_token_content_entity(make_tree):
    """`entities.cards.<id>` resolves through the content-entity files."""
    tree = Tree.load(make_tree())
    assert tree.has_token("entities.cards.test_card")
    assert not tree.has_token("entities.cards.no_such_card")


def test_no_token_for_unknown_namespace(make_tree):
    tree = Tree.load(make_tree())
    assert not tree.has_token("widgets.foo")
