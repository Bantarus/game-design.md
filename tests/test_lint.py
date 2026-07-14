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


# ---- write-to-template-field (D-019, F-008 v0.3 addressing DSL) --------------

_INSTANCE_CONTAINER_MECHANICS_TEMPLATE = """\
---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: prototyped
last_verified: "2026-05-22"
entities:
  player:
    type: actor
    properties: {{ hp: 10 }}
    status: prototyped
    implemented_in: []
  cards:
    type: content_collection
    data_source: ../../content/cards
    count_target: 25
    status: prototyped
  units:
    type: instance_container
    capacity: 10
    holds_template_from: "{{entities.cards}}"
    per_instance_state:
      hp:        {{ type: integer, minimum: 0 }}
      lifecycle: {{ enum: [alive, dead] }}
    status: prototyped
    implemented_in: []
verbs:
  do_thing:
    actor: "{{entities.player}}"
    cost: 0
    target_schema: {{ type: system }}
    effects:
      - {{ resolve: "{{rules.do_thing_rule}}" }}
    status: prototyped
    implemented_in: []
resources:
  energy:
    scope: per_turn
    min: 0
    max: 1
    velocity_target: "{{balance_targets.energy_target}}"
    visibility: hud
    status: prototyped
    implemented_in: []
states:
  thing_state:
    initial: a
    nodes:
      - {{ id: a }}
      - {{ id: b, terminal: true }}
    transitions:
      - {{ from: a, event: "{{events.go}}", to: b }}
events:
  go:
    status: prototyped
    description: "Baseline test event used by thing_state's a → b transition."
rules:
  do_thing_rule:
    given:
      verb: "{{verbs.do_thing}}"
    do:
      - sample: "{{distributions.test_dist}}"
      - {{ kind: apply_damage, target: target, field: {field_name}, amount: 1 }}
    outputs: []
    status: prototyped
    implemented_in: []
---

## Tokens
"""


def test_write_to_per_instance_state_is_silent(make_tree):
    """A do[] step writing to a per_instance_state field (`hp`) is legal — no finding."""
    mech = _INSTANCE_CONTAINER_MECHANICS_TEMPLATE.format(field_name="hp")
    root = make_tree({"gdd/mechanics.md": mech})
    res = _lint(root)
    findings = [f for f in res.findings if f.rule == "write-to-template-field"]
    assert findings == [], (
        "write-to-template-field should not fire on a field declared in "
        f"per_instance_state. Got: {[f.message for f in findings]}"
    )


def test_write_to_template_field_fires_on_undeclared_field(make_tree):
    """A do[] step writing to `max_hp` (NOT in per_instance_state) fires the
    D-019 error — D-019 restricts writes to per_instance_state only."""
    mech = _INSTANCE_CONTAINER_MECHANICS_TEMPLATE.format(field_name="max_hp")
    root = make_tree({"gdd/mechanics.md": mech})
    res = _lint(root)
    findings = [f for f in res.findings if f.rule == "write-to-template-field"]
    assert findings, "expected write-to-template-field on a non-per_instance_state field"
    assert all(f.severity == "error" for f in findings)
    assert any("max_hp" in f.message for f in findings)
    # Error must affect exit code.
    assert res.exit_code == 1


def test_write_to_template_field_silent_without_instance_containers(make_tree):
    """The baseline has no instance_container. The rule is a no-op even if a
    do[] step happens to declare `field:` (the rule is opt-in on instance
    containers; if none exist, there's no writable set to validate against)."""
    res = _lint(make_tree())  # baseline tree, no instance_container
    findings = [f for f in res.findings if f.rule == "write-to-template-field"]
    assert findings == []


# ---- Task 6 anti-staleness rules (v0.3) --------------------------------------
# `stale-section` extension (configurable threshold + status-aware skip),
# `prototyped-without-pointer` (new), and `shipped-stale-doc` (new).
# All three are config-aware via LintConfig (default thresholds 30/30/180).
# Tests inject `now` to make time deterministic (otherwise threshold edges
# would depend on the wall clock when pytest runs).

from datetime import datetime as _dt


def _lint_with_config(root, **config_kw):
    """Helper: lint a tree with a custom LintConfig."""
    cfg = linter.LintConfig(**config_kw)
    return linter.run_all(Tree.load(root), config=cfg)


# ---- prototyped-without-pointer (NEW) -----------------------------------------

def test_prototyped_without_pointer_silent_on_fresh_baseline(make_tree):
    """Baseline subfiles all have last_verified ~7 days before the injected
    `now`; the default threshold is 30 days, so the new rule emits zero
    findings on a fresh tree. (Also the baseline test_baseline_lints_clean
    test would catch any regression here at exit-code 0; warnings would
    still slip through.) Calibration anchor: baselines pass under defaults.
    `now` is injected rather than wall-clock so the baseline's baked
    last_verified dates stay "fresh" forever — with real today() this test
    became a time-bomb 30 days after the dates were written."""
    now = _dt(2026, 5, 29)  # 7-8 days after last_verified=2026-05-21/22
    res = _lint_with_config(make_tree(), now=now)
    findings = [f for f in res.findings if f.rule == "prototyped-without-pointer"]
    assert findings == [], (
        "prototyped-without-pointer must not fire on fresh baselines:\n"
        + "\n".join(f.message for f in findings)
    )


def test_prototyped_without_pointer_fires_on_stale_file(make_tree):
    """Subfile's last_verified is 60 days before our injected `now`; default
    threshold 30. Tokens at status: prototyped with implemented_in: [] are
    flagged."""
    # Baseline already has subfiles at last_verified="2026-05-21" with tokens
    # at status: prototyped and implemented_in: []. We just need now to be far
    # enough out for the file to be "stale" per the default threshold.
    root = make_tree()
    far_future = _dt(2026, 7, 30)  # 70 days after last_verified=2026-05-21
    res = _lint_with_config(root, now=far_future)
    findings = [f for f in res.findings if f.rule == "prototyped-without-pointer"]
    assert findings, (
        "expected prototyped-without-pointer findings on stale baseline; got: "
        + ", ".join(f"{f.rule}:{f.location}" for f in res.findings)
    )
    assert all(f.severity == "warning" for f in findings)
    # Warning, not error — exit code stays clean.
    assert res.exit_code == 0


def test_prototyped_without_pointer_silent_when_impl_populated(make_tree):
    """A subfile that's stale BUT whose tokens declare implemented_in: paths
    doesn't fire the rule. (The rule is about missing pointers, not
    staleness alone — staleness alone is `stale-section`'s job.)"""
    mech = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
implemented_in: ["nonexistent/**/*.py"]
entities:
  player:
    type: actor
    status: prototyped
    properties:
      hp: 10
    implemented_in: ["src/player.py"]
verbs:
  do_thing:
    actor: "{entities.player}"
    cost: { resource: "{resources.energy}", amount: 1 }
    target_schema: { type: "{entities.player}" }
    effects: [{ kind: noop }]
    status: prototyped
    implemented_in: ["src/do_thing.py"]
resources:
  energy:
    scope: per_turn
    min: 0
    max: 3
    visibility: hud
    status: prototyped
    implemented_in: ["src/energy.py"]
"""
    root = make_tree({"gdd/mechanics.md": mech})
    far_future = _dt(2026, 7, 30)  # 70 days stale, far past threshold
    res = _lint_with_config(root, now=far_future)
    findings = [f for f in res.findings if f.rule == "prototyped-without-pointer"
                and "mechanics.md" in f.file]
    # Tokens with populated implemented_in don't trip the rule.
    assert findings == [], (
        "tokens with implemented_in must not fire prototyped-without-pointer:\n"
        + "\n".join(f"{f.location}: {f.message}" for f in findings)
    )


def test_prototyped_without_pointer_silent_on_draft_tokens(make_tree):
    """A token at status: draft with empty implemented_in does NOT fire the
    rule — `draft` is exempt because code may legitimately not exist yet."""
    mech = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
entities:
  player:
    type: actor
    status: draft
    properties:
      hp: 10
verbs:
  do_thing:
    actor: "{entities.player}"
    cost: { resource: "{resources.energy}", amount: 1 }
    target_schema: { type: "{entities.player}" }
    effects: [{ kind: noop }]
    status: draft
resources:
  energy:
    scope: per_turn
    min: 0
    max: 3
    visibility: hud
    status: draft
"""
    root = make_tree({"gdd/mechanics.md": mech})
    far_future = _dt(2026, 12, 31)  # very stale
    res = _lint_with_config(root, now=far_future)
    findings = [f for f in res.findings if f.rule == "prototyped-without-pointer"
                and "mechanics.md" in f.file]
    assert findings == [], (
        "draft tokens must not fire prototyped-without-pointer:\n"
        + "\n".join(f"{f.location}: {f.message}" for f in findings)
    )


def test_prototyped_without_pointer_threshold_configurable(make_tree):
    """Bumping --prototyped-stale-days above the doc's age silences the rule;
    dropping it below the doc's age makes it fire. Confirms the threshold
    is the lever we expose."""
    root = make_tree()
    now = _dt(2026, 6, 10)  # 20 days after last_verified=2026-05-21
    # 20 days old vs threshold 50 → silent.
    res_silent = _lint_with_config(root, now=now, prototyped_stale_days=50)
    findings_silent = [f for f in res_silent.findings if f.rule == "prototyped-without-pointer"]
    assert findings_silent == []
    # 20 days old vs threshold 10 → fires.
    res_fires = _lint_with_config(root, now=now, prototyped_stale_days=10)
    findings_fires = [f for f in res_fires.findings if f.rule == "prototyped-without-pointer"]
    assert findings_fires


# ---- shipped-stale-doc (NEW) -------------------------------------------------

_SHIPPED_SUBFILE = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: shipped
last_verified: "2025-11-01"
---

## Tokens
"""


def test_shipped_stale_doc_silent_below_threshold(make_tree):
    """Shipped file last_verified=2025-11-01, now=2026-01-01 → 61 days old;
    default threshold 180; rule silent."""
    root = make_tree({"gdd/glossary.md": _SHIPPED_SUBFILE})
    res = _lint_with_config(root, now=_dt(2026, 1, 1))
    findings = [f for f in res.findings if f.rule == "shipped-stale-doc"]
    assert findings == []


def test_shipped_stale_doc_fires_above_threshold(make_tree):
    """Shipped file last_verified=2025-11-01, now=2026-06-01 → 212 days old;
    default threshold 180; rule fires."""
    root = make_tree({"gdd/glossary.md": _SHIPPED_SUBFILE})
    res = _lint_with_config(root, now=_dt(2026, 6, 1))
    findings = [f for f in res.findings if f.rule == "shipped-stale-doc"]
    assert findings, (
        "expected shipped-stale-doc; got rules: "
        + ", ".join(f.rule for f in res.findings)
    )
    assert all(f.severity == "warning" for f in findings)
    assert any("212 days" in f.message for f in findings)
    assert res.exit_code == 0  # warning, not error


def test_shipped_stale_doc_silent_on_non_shipped(make_tree):
    """Same file age but at status: balanced — rule silent (only shipped
    fires this rule). The 90-day stale-section path would fire only if impl
    mtime differed; we don't trip that here."""
    sub = _SHIPPED_SUBFILE.replace("status: shipped", "status: balanced")
    root = make_tree({"gdd/glossary.md": sub})
    res = _lint_with_config(root, now=_dt(2026, 6, 1))
    findings = [f for f in res.findings if f.rule == "shipped-stale-doc"]
    assert findings == []


def test_shipped_stale_doc_threshold_configurable(make_tree):
    """At now=2026-06-01 the doc is 212 days old. Bumping threshold to 365
    silences the rule; dropping to 30 still fires it."""
    root = make_tree({"gdd/glossary.md": _SHIPPED_SUBFILE})
    res_silent = _lint_with_config(root, now=_dt(2026, 6, 1), shipped_stale_days=365)
    findings_silent = [f for f in res_silent.findings if f.rule == "shipped-stale-doc"]
    assert findings_silent == []

    res_fires = _lint_with_config(root, now=_dt(2026, 6, 1), shipped_stale_days=30)
    findings_fires = [f for f in res_fires.findings if f.rule == "shipped-stale-doc"]
    assert findings_fires


# ---- stale-section (extended: configurable threshold + status-aware) ---------

def test_stale_section_skips_draft_status(make_tree, tmp_path):
    """Files at status: draft are exempt from stale-section — at draft the
    impl pointer is often planned-but-unbacked or stub code, so an mtime
    drift isn't a meaningful signal."""
    # Build a draft subfile pointing at a freshly-modified impl file.
    # We need an impl file that exists AND has a recent mtime relative to
    # the doc's last_verified.
    impl_dir = tmp_path / "src"
    impl_dir.mkdir(exist_ok=True)
    impl_path = impl_dir / "stuff.py"
    impl_path.write_text("# stub\n")
    # Set the impl mtime well after last_verified.
    new_mtime = _dt(2027, 1, 1).timestamp()
    import os
    os.utime(impl_path, (new_mtime, new_mtime))
    sub = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: draft
last_verified: "2026-05-21"
implemented_in: ["src/stuff.py"]
---

## Tokens
"""
    # Place the subfile under tmp_path so impl path resolves.
    root = make_tree({"gdd/stuff.md": sub})
    # make_tree builds the tree elsewhere; move impl into the tree root.
    tree_impl_dir = root / "src"
    tree_impl_dir.mkdir(exist_ok=True)
    tree_impl_path = tree_impl_dir / "stuff.py"
    tree_impl_path.write_text("# stub\n")
    os.utime(tree_impl_path, (new_mtime, new_mtime))

    res = _lint(root)
    stale = [f for f in res.findings if f.rule == "stale-section" and "stuff.md" in f.file]
    assert stale == [], (
        "stale-section must skip files at status=draft (v0.3 Task 6 extension); "
        f"got: {[f.message for f in stale]}"
    )


def test_stale_section_fires_at_prototyped_above_threshold(make_tree, tmp_path):
    """At status: prototyped with impl mtime > last_verified + 30 days,
    stale-section fires. Confirms the rule still works post-extension."""
    sub = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
implemented_in: ["src/stuff.py"]
---

## Tokens
"""
    root = make_tree({"gdd/stuff.md": sub})
    impl = root / "src" / "stuff.py"
    impl.parent.mkdir(exist_ok=True)
    impl.write_text("# stub\n")
    import os
    new_mtime = _dt(2027, 1, 1).timestamp()  # 8mo after last_verified
    os.utime(impl, (new_mtime, new_mtime))

    res = _lint(root)
    stale = [f for f in res.findings if f.rule == "stale-section" and "stuff.md" in f.file]
    assert stale, (
        "expected stale-section on prototyped file with newer impl; got: "
        + ", ".join(f"{f.rule}:{f.location}" for f in res.findings)
    )
    assert all(f.severity == "warning" for f in stale)


def test_stale_section_threshold_configurable(make_tree, tmp_path):
    """The --stale-days CLI option threads to LintConfig.stale_days."""
    sub = """\
---
spec: game-design.md
spec_version: 0.1.1
file_type: subfile
status: prototyped
last_verified: "2026-05-21"
implemented_in: ["src/stuff.py"]
---

## Tokens
"""
    root = make_tree({"gdd/stuff.md": sub})
    impl = root / "src" / "stuff.py"
    impl.parent.mkdir(exist_ok=True)
    impl.write_text("# stub\n")
    import os
    # 15 days newer than last_verified
    drift_mtime = _dt(2026, 6, 5).timestamp()
    os.utime(impl, (drift_mtime, drift_mtime))

    # Tight threshold (5d) → fires
    res_fires = _lint_with_config(root, stale_days=5)
    findings_fires = [f for f in res_fires.findings
                      if f.rule == "stale-section" and "stuff.md" in f.file]
    assert findings_fires

    # Lenient threshold (30d, default) → silent
    res_silent = _lint_with_config(root, stale_days=30)
    findings_silent = [f for f in res_silent.findings
                       if f.rule == "stale-section" and "stuff.md" in f.file]
    assert findings_silent == []
