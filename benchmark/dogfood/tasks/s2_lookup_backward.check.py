#!/usr/bin/env python3
"""Checker for s2_lookup_backward (D-026, study 2; prompt in fixtures/study2/prompts/).

Success: `answers/s2_lookup_backward.txt` is the only change in the copy, and every
question's set equals the frozen answer in fixtures/study2/answers/s2_lookup_backward.json
exactly (computed from the generator's planted edges, never by gdmd code).
Per-question Jaccard is reported, descriptive only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402

if __name__ == "__main__":
    cl.check_study2_answers("s2_lookup_backward", paths=False)
