"""Loader strictness regressions (D-001 + D-004)."""
from __future__ import annotations

from game_design_md.loader import load_yaml, parse_md


def test_on_stays_string():
    """YAML 1.1 booleans (on/off/yes/no) must NOT be coerced — they stay strings."""
    out = load_yaml("event: on")
    assert out == {"event": "on"}
    assert isinstance(out["event"], str)


def test_off_yes_no_stay_string():
    out = load_yaml("a: off\nb: yes\nc: no")
    assert out == {"a": "off", "b": "yes", "c": "no"}


def test_true_false_still_boolean():
    out = load_yaml("a: true\nb: false")
    assert out == {"a": True, "b": False}


def test_iso_date_stays_string():
    out = load_yaml("last_verified: 2026-05-21")
    assert out == {"last_verified": "2026-05-21"}
    assert isinstance(out["last_verified"], str)


def test_quoted_date_unchanged():
    out = load_yaml('last_verified: "2026-05-21"')
    assert out == {"last_verified": "2026-05-21"}


def test_parse_md_splits():
    fm, body = parse_md("---\na: 1\n---\nhello")
    assert fm == {"a": 1}
    assert body.strip() == "hello"


def test_parse_md_no_frontmatter():
    fm, body = parse_md("just body, no fence")
    assert fm is None
    assert "just body" in body


def test_state_transition_event_key_not_coerced():
    """The whole reason we use `event:` not `on:`: even if someone writes `on:`,
    the loader keeps it as a string under our resolver settings (D-001)."""
    out = load_yaml("- { from: a, on: draw, to: b }")
    # Key is the literal string "on", not Python True.
    assert out[0] == {"from": "a", "on": "draw", "to": "b"}
    assert "on" in out[0]
    assert True not in out[0]
