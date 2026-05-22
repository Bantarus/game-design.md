"""Ref extraction walks nested structures and the body."""
from __future__ import annotations

from game_design_md.refs import TOKEN_REF_RE, walk_refs


def test_extract_simple():
    obj = {"a": "{loops.combat_turn}"}
    refs = list(walk_refs(obj))
    assert refs == [("loops.combat_turn", ("a",))]


def test_extract_nested_list():
    obj = {"seq": ["{verbs.a}", "{verbs.b}"]}
    refs = sorted(r for r, _ in walk_refs(obj))
    assert refs == ["verbs.a", "verbs.b"]


def test_extract_deep():
    obj = {"x": [{"y": [{"z": "{entities.cards.ember_strike}"}]}]}
    refs = list(walk_refs(obj))
    assert refs[0][0] == "entities.cards.ember_strike"
    assert refs[0][1] == ("x", "[0]", "y", "[0]", "z")


def test_no_refs_in_plain_text():
    assert list(walk_refs("no curly braces here")) == []
    # bare braces aren't captured
    assert list(walk_refs("{not a ref!}")) == []


def test_body_regex_matches_canonical_form():
    text = "see {distributions.card_draw} and {verbs.play_card}"
    found = [m.group(1) for m in TOKEN_REF_RE.finditer(text)]
    assert found == ["distributions.card_draw", "verbs.play_card"]


def test_body_regex_rejects_invalid_chars():
    """Wildcards like {distributions.*} must not match — they would yield
    bogus broken-refs in prose."""
    assert TOKEN_REF_RE.search("{distributions.*}") is None
