"""Linter rules — happy path + one failure per rule.

The baseline tree from conftest.py lints clean (no errors). Each test below
mutates the baseline to trigger exactly one rule, then asserts the finding.
"""
from __future__ import annotations

from game_design_md import linter
from game_design_md.tree import Tree


def _lint(root):
    return linter.run_all(Tree.load(root))


# ---- Baseline -----------------------------------------------------------------

def test_baseline_lints_clean(make_tree):
    res = _lint(make_tree())
    assert res.exit_code == 0, [f.message for f in res.findings if f.severity == "error"]
    assert res.errors == 0


# ---- broken-ref ---------------------------------------------------------------

def test_broken_ref(fixture_overlay):
    res = _lint(fixture_overlay("broken_ref"))
    assert any(f.rule == "broken-ref" and "does_not_exist" in f.message
               for f in res.findings)
    assert res.exit_code == 1


def test_broken_ref_inline(make_tree):
    """A typo in a verb's resolve ref."""
    root = make_tree({
        "gdd/loops.md": make_tree.__wrapped__ if False else None,
    }) if False else None  # placeholder; using inline patch below
    # Use a simpler patch:
    root = make_tree({
        "gdd/test_extra.md": """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
---
{verbs.nonexistent_verb}
""",
    })
    res = _lint(root)
    assert any(f.rule == "broken-ref" for f in res.findings)


# ---- missing-pillars / missing-core-loop / missing-balance-targets ------------

def test_missing_pillars(make_tree):
    bad_core = (make_tree() / "game-design.md").read_text().replace(
        'pillars: ["P1", "P2", "P3"]', 'pillars: ["P1"]'
    )
    root = make_tree({"game-design.md": bad_core})
    res = _lint(root)
    assert any(f.rule == "missing-pillars" for f in res.findings)


def test_missing_core_loop(make_tree):
    bad_core = (make_tree() / "game-design.md").read_text().replace(
        'core_loop_ref: "{loops.main}"', 'core_loop_ref: "{loops.does_not_exist}"'
    )
    root = make_tree({"game-design.md": bad_core})
    res = _lint(root)
    assert any(f.rule == "missing-core-loop" for f in res.findings)


def test_missing_balance_targets(make_tree):
    # Strip the balance_targets block entirely.
    bal = (make_tree() / "gdd/economy-balance.md").read_text()
    no_targets = bal.split("balance_targets:", 1)[0] + "---\n\n## Tokens\n"
    root = make_tree({"gdd/economy-balance.md": no_targets})
    res = _lint(root)
    assert any(f.rule == "missing-balance-targets" for f in res.findings)


# ---- undefined-distribution ---------------------------------------------------

def test_undefined_distribution(make_tree):
    """A rule with a sample step that doesn't reference {distributions.X}."""
    bad_mech = (make_tree() / "gdd/mechanics.md").read_text().replace(
        'sample: "{distributions.test_dist}"',
        'sample: just_a_string',
    )
    root = make_tree({"gdd/mechanics.md": bad_mech})
    res = _lint(root)
    assert any(f.rule == "undefined-distribution" for f in res.findings)


# ---- state-machine-coverage ---------------------------------------------------

def test_dead_end_machine(fixture_overlay):
    res = _lint(fixture_overlay("dead_end_machine"))
    findings = [f for f in res.findings if f.rule == "state-machine-coverage"]
    assert any("dead-end" in f.message for f in findings)
    assert res.exit_code == 1


def test_missing_initial(make_tree):
    bad = (make_tree() / "gdd/mechanics.md").read_text().replace(
        "initial: a", "initial: not_a_node"
    )
    root = make_tree({"gdd/mechanics.md": bad})
    res = _lint(root)
    assert any(f.rule == "state-machine-coverage" and "missing-initial" in f.message
               for f in res.findings)


def test_undeclared_destination(make_tree):
    bad = (make_tree() / "gdd/mechanics.md").read_text().replace(
        'event: "{events.go}", to: b',
        'event: "{events.go}", to: not_a_node',
    )
    root = make_tree({"gdd/mechanics.md": bad})
    res = _lint(root)
    assert any(f.rule == "state-machine-coverage" and "undeclared-destination" in f.message
               for f in res.findings)


# ---- section-order ------------------------------------------------------------

def test_duplicate_heading(make_tree):
    root = make_tree({
        "gdd/loops.md": (make_tree() / "gdd/loops.md").read_text() + "\n## Tokens\n",
    })
    res = _lint(root)
    assert any(f.rule == "section-order" and "duplicate" in f.message
               for f in res.findings)


# ---- inline-content-over-threshold --------------------------------------------

def test_inline_content_over_threshold(make_tree):
    """Drop data_dir while keeping count_target >= 20 → error."""
    cards_md = (make_tree() / "gdd/content/cards.md").read_text()
    bad = cards_md.replace("data_dir: ../../content/cards\n", "")
    root = make_tree({"gdd/content/cards.md": bad})
    res = _lint(root)
    assert any(f.rule == "inline-content-over-threshold" for f in res.findings)


# ---- invariant-violation ------------------------------------------------------

def test_invariant_violation_numeric(fixture_overlay):
    res = _lint(fixture_overlay("invariant_violation_numeric"))
    findings = [f for f in res.findings if f.rule == "invariant-violation"]
    assert any("not an integer" in f.message for f in findings)
    assert res.exit_code == 1


def test_invariant_violation_numeric_resource_bound(make_tree):
    """D-009: numeric_domain invariant lists {resources.energy}; if energy.max
    becomes a float, the linter must flag it (the broadened scope).
    """
    mech = (make_tree() / "gdd/mechanics.md").read_text().replace(
        "max: 1", "max: 1.5"
    )
    root = make_tree({"gdd/mechanics.md": mech})
    res = _lint(root)
    findings = [f for f in res.findings if f.rule == "invariant-violation"]
    assert any("resources.energy.max" in f.location and "not an integer" in f.message
               for f in findings), (
        "expected invariant-violation on resources.energy.max=1.5; got: "
        + ", ".join(f"{f.location}:{f.message[:40]}" for f in findings)
    )
    assert res.exit_code == 1


def test_invariant_violation_numeric_entity_property(make_tree):
    """D-009: numeric_domain invariant scope-broadened to {entities.<kind>};
    a float in a content-entity's integer-typed field must fire.
    """
    # Extend the baseline invariant to also cover {entities.cards}.
    inv = (make_tree() / "gdd/architecture-invariants.md").read_text().replace(
        'applies_to: ["{resources.energy}"]',
        'applies_to: ["{resources.energy}", "{entities.cards}"]',
    )
    # Author a content-entity with a float cost (schema declares cost: integer).
    bad_card = """\
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: bad_card
status: prototyped
implemented_in: []
name: "Bad Card"
cost: 1.5
"""
    root = make_tree({
        "gdd/architecture-invariants.md": inv,
        "content/cards/bad_card.yaml": bad_card,
    })
    res = _lint(root)
    findings = [f for f in res.findings if f.rule == "invariant-violation"]
    assert any("cost" in f.location and "1.5" in f.message for f in findings), (
        "expected invariant-violation on bad_card.cost=1.5; got: "
        + ", ".join(f"{f.location}:{f.message[:40]}" for f in findings)
    )
    assert res.exit_code == 1


def test_invariant_violation_numeric_resource_int_passes(make_tree):
    """Sanity: integer min/max bounds don't trigger the broadened check."""
    res = _lint(make_tree())  # baseline declares energy.min=0, max=1
    findings = [f for f in res.findings if f.rule == "invariant-violation"
                and "not an integer" in f.message]
    assert findings == []


# ---- balance-target-untyped (D-003) ------------------------------------------

def test_balance_target_untyped_warning(make_tree):
    """A legacy v0.1.1 balance target without target_kind fires the migration warning."""
    bal = (make_tree() / "gdd/economy-balance.md").read_text().replace(
        "target_kind: scalar\n    target: 1",
        "target: 1",
    )
    root = make_tree({"gdd/economy-balance.md": bal})
    res = _lint(root)
    findings = [f for f in res.findings if f.rule == "balance-target-untyped"]
    assert findings, "expected balance-target-untyped on the legacy target"
    assert all(f.severity == "warning" for f in findings)
    # Warnings don't affect exit code.
    assert res.errors == 0


def test_balance_target_typed_is_silent(make_tree):
    """A target with target_kind: scalar does NOT fire balance-target-untyped."""
    res = _lint(make_tree())  # baseline already declares target_kind
    findings = [f for f in res.findings if f.rule == "balance-target-untyped"]
    assert findings == []


# ---- undefined-event (D-005) -------------------------------------------------

def test_undefined_event_on_bare_string(fixture_overlay):
    """The deliberately-broken undefined_event fixture has event: go (bare).
    state-machine-coverage should fire undefined-event at warning severity."""
    res = _lint(fixture_overlay("undefined_event"))
    sm_findings = [f for f in res.findings if f.rule == "state-machine-coverage"]
    ue_findings = [f for f in sm_findings if "undefined-event" in f.message]
    assert ue_findings, (
        "expected undefined-event sub-finding on bare-string transition event; got: "
        + ", ".join(f.message for f in sm_findings)
    )
    assert all(f.severity == "warning" for f in ue_findings)


def test_token_event_is_silent(make_tree):
    """The baseline uses event: \"{events.go}\" — no undefined-event finding."""
    res = _lint(make_tree())
    findings = [f for f in res.findings
                if f.rule == "state-machine-coverage" and "undefined-event" in f.message]
    assert findings == []


def test_broken_event_ref_is_error(make_tree):
    """{events.missing} where events.missing isn't declared → broken-ref error."""
    bad = (make_tree() / "gdd/mechanics.md").read_text().replace(
        '"{events.go}"', '"{events.missing}"'
    )
    root = make_tree({"gdd/mechanics.md": bad})
    res = _lint(root)
    assert any(f.rule == "broken-ref" and "events.missing" in f.message
               for f in res.findings)
    assert res.exit_code == 1


def test_orphaned_event_is_warning(make_tree):
    """An event declared but referenced by no transition → orphaned-entity warning."""
    bad = (make_tree() / "gdd/mechanics.md").read_text().replace(
        'events:\n  go:\n    status: prototyped\n'
        '    description: "Baseline test event used by thing_state\'s a → b transition."',
        'events:\n  go:\n    status: prototyped\n'
        '    description: "Used by the a → b transition."\n'
        '  unused_event:\n    status: prototyped\n'
        '    description: "Declared but never referenced."',
    )
    root = make_tree({"gdd/mechanics.md": bad})
    res = _lint(root)
    assert any(f.rule == "orphaned-entity"
               and f.location == "events.unused_event"
               for f in res.findings), (
        "expected orphaned-entity at events.unused_event; got: "
        + ", ".join(f"{f.rule}:{f.location}" for f in res.findings)
    )


# ---- broken-implementation-pointer (D-002, error at v0.2+) --------------------

def test_broken_implementation_pointer_silent_at_draft(make_tree):
    """A design-stage tree (status: draft everywhere) emits zero impl-pointer findings,
    even with completely fake implemented_in globs. This is what keeps the
    D-002 ratchet (warning → error at v0.2) from blocking design-stage trees."""
    mech = (make_tree() / "gdd/mechanics.md").read_text()
    # Add a broken impl glob AND demote everything to draft.
    bad = (mech
           .replace("file_type: subfile\nstatus: prototyped",
                    "file_type: subfile\nstatus: draft\n"
                    'implemented_in: ["nope/**.py"]')
           .replace("status: prototyped", "status: draft"))
    root = make_tree({"gdd/mechanics.md": bad})
    res = _lint(root)
    impl_findings = [f for f in res.findings if f.rule == "broken-implementation-pointer"]
    assert impl_findings == [], (
        "draft status must silence broken-impl-pointer (the design-stage exit gate):\n"
        + "\n".join(f.message for f in impl_findings)
    )


def test_broken_implementation_pointer_is_error_at_prototyped(make_tree):
    """D-002 ratcheted at v0.2.0-alpha Phase 3+: a prototyped+ entity with a
    broken implemented_in: glob fires at severity `error` (was `warning` in
    v0.1.1). The ratchet trigger was tick-combat shipping real source and a
    verify adapter."""
    mech_text = (make_tree() / "gdd/mechanics.md").read_text()
    bad = mech_text.replace(
        "file_type: subfile\nstatus: prototyped",
        "file_type: subfile\nstatus: prototyped\nimplemented_in: [\"nope/**.py\"]\n# anchor",
    )
    root = make_tree({"gdd/mechanics.md": bad})
    res = _lint(root)
    impl_findings = [f for f in res.findings if f.rule == "broken-implementation-pointer"]
    assert impl_findings, "expected broken-implementation-pointer to fire on broken glob"
    # D-002 ratchet: severity is error at v0.2+.
    assert all(f.severity == "error" for f in impl_findings), (
        "D-002 ratcheted to error at v0.2.0-alpha Phase 3+; found severities: "
        + ", ".join(sorted({f.severity for f in impl_findings}))
    )
    # Errors must affect exit code.
    assert res.exit_code == 1
