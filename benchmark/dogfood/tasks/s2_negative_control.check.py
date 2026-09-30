#!/usr/bin/env python3
"""Checker for s2_negative_control (D-026, study 2; guarded; same prompt as
s2_maintenance).

Fixture: a teammate commit edits a docstring in
impl/lanternfall/tests/test_drop_tables.py. No implemented_in glob or
implementation_pointer covers that file, so `gdmd hook check` is silent and
lint stays 0/0.

Success: the copy is left exactly as it was. Lint 0/0 is a sanity check.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402

if __name__ == "__main__":
    cl.check_study2_negative_control("s2_negative_control")
