#!/usr/bin/env python3
"""Checker for tasks/negative_control_no_drift.md (same prompt as
maintenance_drift; different fixture).

Fixture: a teammate commit edits a comment in impl/xtreme/tests/
golden_trajectory.rs. No implemented_in glob or implementation_pointer covers
that file, so no spec section references it, `gdmd hook check` is silent, and
lint stays 0/0.

Success: the copy is left exactly as it was (no tracked or untracked change);
this catches agents that "maintain" by churning. Lint 0/0 is a sanity check.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402

TREE = "examples/tick-combat"


def main() -> None:
    a = cl.parse_args()
    r = cl.Report("negative_control_no_drift")
    changes = cl.changed_paths(a.root, a.base)
    r.check("repository_unchanged", not changes, changes)
    r.lint_clean(a.root, TREE)
    r.finish()


if __name__ == "__main__":
    main()
