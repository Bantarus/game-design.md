#!/usr/bin/env python3
"""Checker for s2_maintenance (D-026, study 2; guarded).

Fixture: a teammate commit makes a behavior-preserving refactor to
impl/lanternfall/loot/drop_tables.py (it names the keep-odds 3, which
rules.roll_drops also says). The file is covered, file- and token-level, by
exactly gdd/systems/loot.md and gdd/systems/distributions.md, so
stale-section fires on both (fixtures/study2/answers/s2_maintenance.json).

Success: last_verified bumped on exactly those two subfiles; no token or
frontmatter change anywhere else except allowed ritual metadata; the
implementation and everything outside the tree untouched; lint 0/0.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402

if __name__ == "__main__":
    cl.check_study2_maintenance("s2_maintenance")
