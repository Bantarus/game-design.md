#!/usr/bin/env python3
"""Checker for tasks/maintenance_drift.md.

Fixture: a teammate commit makes a behavior-preserving refactor to
impl/xtreme/src/rules.rs (it names the gold-drop count 6, which the spec's
rules.combat_resolution also says). The affected section is
gdd/mechanics.md: its file-level implemented_in covers rules.rs, so
stale-section fires on it. The root's implementation_pointers also cover the
file, but the root has no last_verified.

Success: last_verified bumped on exactly gdd/mechanics.md; no token or
frontmatter change anywhere else except allowed ritual metadata; the
implementation and everything outside the tree untouched; lint 0/0.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402

TREE = "examples/tick-combat"
EXPECTED_TOUCHED = {f"{TREE}/gdd/mechanics.md"}


def main() -> None:
    a = cl.parse_args()
    r = cl.Report("maintenance_drift")
    changes = cl.changed_paths(a.root, a.base)
    r.check("nothing_outside_tree_changed",
            not [p for p in changes if not p.startswith(TREE + "/")],
            sorted(p for p in changes if not p.startswith(TREE + "/")))
    impl = sorted(p for p in changes if p.startswith(f"{TREE}/impl/"))
    r.check("implementation_untouched", not impl, impl)
    handled = cl.check_ritual_metadata(r, a.root, TREE, a.base, changes,
                                       run_date=a.run_date, check_date=a.check_date)
    other = sorted(p for p in changes if p.startswith(TREE + "/") and p not in handled
                   and p not in impl)
    r.check("no_token_or_file_changes", not other, other)
    touched = set()
    for rel in changes:
        if rel.endswith(".md"):
            b, _ = cl.doc_at(a.root, rel, a.base)
            n, _ = cl.doc_at(a.root, rel)
            if (b or {}).get("last_verified") != (n or {}).get("last_verified"):
                touched.add(rel)
    r.check("touched_exactly_affected_sections", touched == EXPECTED_TOUCHED, sorted(touched))
    r.lint_clean(a.root, TREE)
    r.finish()


if __name__ == "__main__":
    main()
