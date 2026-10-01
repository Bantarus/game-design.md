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


def _s3_table_keys(start: str, stop: str) -> list[str]:
    """The backticked keys in the first column of the §3 table that follows
    the paragraph starting `start`, up to the paragraph starting `stop`."""
    import re
    from game_design_md import spec_cmd
    text = spec_cmd.spec_text()
    s3 = next(s for s in spec_cmd.sections(text) if s.id == "3")
    body = "\n".join(text.split("\n")[s3.start - 1:s3.end])
    part = body[body.index(start):body.index(stop)]
    return [k for row in re.findall(r"^\| (`[a-z_]+`(?: / `[a-z_]+`)*) \|", part, re.M)
            for k in re.findall(r"`([a-z_]+)`", row)]


RESERVED_OWNED_KEYS = ("pillars", "player_experience_goals", "verify_targets", "adapters")


def test_spec_s3_namespace_table_is_what_tree_indexes():
    """D-039 (OI-004): §3's referenceable table lists exactly SUBFILE_NAMESPACES;
    the reserved owned keys are in their own table, and Tree indexes none."""
    from game_design_md.tree import SUBFILE_NAMESPACES
    names = _s3_table_keys("**Namespace ownership.**", "**Reserved owned keys")
    assert sorted(names) == sorted(SUBFILE_NAMESPACES)
    reserved = _s3_table_keys("**Reserved owned keys", "**Resolution.**")
    assert sorted(reserved) == sorted(RESERVED_OWNED_KEYS)
    assert not set(reserved) & set(SUBFILE_NAMESPACES)


def test_docs_lint_teaches_only_referenceable_namespaces():
    """D-039: docs_lint's valid namespaces follow §3's referenceable table, so
    AGENTS.md cannot teach `{pillars.x}`, which fires broken-ref."""
    import importlib.util
    from game_design_md.tree import SUBFILE_NAMESPACES
    from tests.conftest import REPO_ROOT
    spec = importlib.util.spec_from_file_location("docs_lint", REPO_ROOT / "scripts/docs_lint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(SUBFILE_NAMESPACES) <= mod.VALID_NAMESPACES
    assert not mod.VALID_NAMESPACES & {*RESERVED_OWNED_KEYS, "content_schema"}


def test_spec_s3_context_local_prefixes_are_the_closed_code_set():
    """D-047 (R7): §3 states the context-local set is closed, and lists
    exactly linter.CONTEXT_LOCAL_PREFIXES."""
    import re
    from game_design_md import spec_cmd
    from game_design_md.linter import CONTEXT_LOCAL_PREFIXES
    text = spec_cmd.spec_text()
    para = text[text.index("**Context-local prefixes"):]
    para = para[:para.index("\n\n", para.index("\n- ")) ]
    assert "The set is closed" in para
    assert set(re.findall(r"^- `\{([a-z_]+)\.<field>\}`", para, re.M)) == set(CONTEXT_LOCAL_PREFIXES)
