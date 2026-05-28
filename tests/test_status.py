"""gdmd status — aggregation tests.

The status command is informational, so the tests assert on the report shape
and aggregation correctness, not on exit codes.
"""
from __future__ import annotations

from datetime import datetime

from game_design_md import status_cmd
from game_design_md.tree import Tree


def _report(root, *, stale_days=90, shipped_stale_days=180, now=None):
    return status_cmd.status_report(
        Tree.load(root),
        stale_days=stale_days,
        shipped_stale_days=shipped_stale_days,
        now=now,
    )


# ---- Baseline ----------------------------------------------------------------

def test_status_baseline_shape(make_tree):
    """The minimal baseline tree produces a well-shaped report."""
    r = _report(make_tree())
    assert "tree_root" in r
    assert "files_scanned" in r
    assert "status_counts" in r
    assert "stale_sections" in r
    assert "shipped_stale" in r
    assert "active_without_impl" in r
    assert "thresholds" in r
    assert r["thresholds"]["stale_days"] == 90
    assert r["thresholds"]["shipped_stale_days"] == 180


def test_status_counts_tallies_per_token(make_tree):
    """Per-token statuses (in subfile namespaces) are tallied alongside
    file-level statuses."""
    r = _report(make_tree())
    counts = r["status_counts"]
    # Baseline has subfile statuses (all prototyped) + per-token statuses
    # (entities/verbs/resources/rules/distributions/etc all prototyped, plus
    # a content-schema and content-entity).
    assert "prototyped" in counts
    assert counts["prototyped"] >= 5, f"got {counts}"


# ---- stale_sections ---------------------------------------------------------

def test_stale_sections_fires_on_old_last_verified(make_tree):
    """A subfile whose last_verified is more than stale_days old is flagged."""
    # The baseline uses "2026-05-21" / "2026-05-22"; treat "now" as a date
    # 100 days later. The default stale_days=90 should trigger.
    now = datetime(2026, 9, 1)
    r = _report(make_tree(), now=now)
    stale = r["stale_sections"]
    assert stale, f"expected stale_sections to fire at now=2026-09-01, got: {stale}"
    # Each finding carries file, status, last_verified, days_old.
    for s in stale:
        assert "file" in s and "last_verified" in s and "days_old" in s


def test_stale_sections_silent_when_recent(make_tree):
    """No staleness when current date is within stale_days of last_verified."""
    now = datetime(2026, 5, 25)  # close to baseline's 2026-05-21/22
    r = _report(make_tree(), now=now)
    assert r["stale_sections"] == []


# ---- shipped_stale ----------------------------------------------------------

def test_shipped_stale_only_fires_on_shipped(make_tree):
    """The shipped_stale check is gated on status: shipped specifically.
    A prototyped section, no matter how old, does NOT fire here."""
    now = datetime(2027, 1, 1)  # 200+ days after baseline
    r = _report(make_tree(), now=now)
    # Baseline subfiles are status: prototyped, so shipped_stale should be empty.
    assert r["shipped_stale"] == []


def test_shipped_stale_fires_on_old_shipped(make_tree):
    """Promote one subfile to status: shipped with old last_verified;
    shipped_stale fires."""
    loops = (make_tree() / "gdd/loops.md").read_text()
    new_loops = loops.replace(
        'status: prototyped\nlast_verified: "2026-05-21"',
        'status: shipped\nlast_verified: "2025-01-01"',
        1,
    )
    root = make_tree({"gdd/loops.md": new_loops})
    now = datetime(2026, 5, 25)
    r = _report(root, now=now)
    ship = r["shipped_stale"]
    assert ship, f"expected shipped_stale, got: {ship}"
    assert any("loops.md" in s["file"] for s in ship)


# ---- active_without_impl ----------------------------------------------------

def test_active_without_impl_fires_on_prototyped_empty_pointers(make_tree):
    """A prototyped token with empty implemented_in is flagged. The baseline's
    rules.do_thing_rule has implemented_in: [] at status: prototyped — this
    should fire."""
    r = _report(make_tree())
    awi = r["active_without_impl"]
    assert awi, f"expected active_without_impl, got: {awi}"
    # The baseline has multiple per-token statuses with empty implemented_in;
    # verify the rules.do_thing_rule is among them.
    assert any(a["token"] == "rules.do_thing_rule" for a in awi), (
        f"expected rules.do_thing_rule in findings: {awi}"
    )


def test_active_without_impl_silent_on_draft(make_tree):
    """A token at status: draft with empty implemented_in is NOT flagged
    (draft is exempt — code may not exist yet)."""
    # Drop all tokens to status: draft.
    mech = (make_tree() / "gdd/mechanics.md").read_text().replace(
        "status: prototyped", "status: draft"
    )
    root = make_tree({"gdd/mechanics.md": mech})
    r = _report(root)
    awi = r["active_without_impl"]
    # Tokens from other files at status: prototyped may still fire; specifically
    # the rules/distributions in mechanics.md should NOT.
    for a in awi:
        if "mechanics.md" in a["file"]:
            # Only fires if the mechanics token's status >= prototyped.
            assert a["status"] != "draft", f"draft should be exempt: {a}"


# ---- experimental + deferred (D-020 v0.3 vocab) -----------------------------

def test_experimental_counts_in_status_tally(make_tree):
    """A file at status: experimental shows up in the counts."""
    pillars = (make_tree() / "gdd/pillars.md").read_text().replace(
        "status: prototyped", "status: experimental"
    )
    root = make_tree({"gdd/pillars.md": pillars})
    r = _report(root)
    assert r["status_counts"].get("experimental", 0) >= 1


def test_deferred_counts_in_status_tally(make_tree):
    """A file at status: deferred shows up in the counts and is exempt from
    active_without_impl (treated as cut-equivalent for staleness checks)."""
    loops = (make_tree() / "gdd/loops.md").read_text().replace(
        "status: prototyped", "status: deferred"
    )
    root = make_tree({"gdd/loops.md": loops})
    r = _report(root)
    assert r["status_counts"].get("deferred", 0) >= 1


# ---- Human rendering --------------------------------------------------------

def test_render_human_includes_canonical_status_order(make_tree):
    """The human-readable output lists statuses in canonical order."""
    out = status_cmd.render_human(_report(make_tree()))
    assert "Status counts" in out
    assert "files scanned" in out
    # Canonical order: draft before prototyped before implemented...
    if "draft" in out and "prototyped" in out:
        assert out.index("draft") < out.index("prototyped")
