#!/usr/bin/env python3
"""Checker for tasks/lookup_refs.md.

Success: `answers/lookup.txt` is the only change in the copy, and its Q1 and Q2
id sets equal the frozen, hand-verified answers in lookup_refs.expected.json.
Order, braces, backticks and surrounding whitespace are normalized; the id sets
must match exactly.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402

ANSWER = "answers/lookup.txt"
EXPECTED = json.loads(Path(__file__).with_name("lookup_refs.expected.json").read_text())


def _norm(item: str) -> str:
    item = item.strip().strip("`").strip()
    if item.startswith("{") and item.endswith("}"):
        item = item[1:-1]
    return item.strip()


def parse_answer(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(Q[12])\s*:\s*(.*)$", line)
        if m:
            out[m.group(1)] = {_norm(x) for x in m.group(2).split(",") if _norm(x)}
    return out


def main() -> None:
    a = cl.parse_args()
    r = cl.Report("lookup_refs")
    changes = cl.changed_paths(a.root, a.base)
    r.check("answer_file_written", changes.get(ANSWER) in ("A", "?"), changes.get(ANSWER))
    r.check("no_other_changes", set(changes) <= {ANSWER}, sorted(set(changes) - {ANSWER}))
    text = cl.read_text(a.root, ANSWER) or ""
    got = parse_answer(text)
    for q in ("Q1", "Q2"):
        want = set(EXPECTED[q])
        have = got.get(q)
        r.check(f"{q.lower()}_correct", have == want,
                None if have is None else {"missing": sorted(want - have),
                                           "extra": sorted(have - want)})
    r.finish()


if __name__ == "__main__":
    main()
