#!/usr/bin/env python3
"""Checker for tasks/operating_energy_budget.md.

Success: the token-level diff of examples/deckbuilder is exactly the expected
propagation set below (lint can't find the second one; it's a value coupling
reached through `velocity_target`), with no other token, content-schema or
content-entity change, only allowed ritual metadata edits, and a 0/0 lint.
Prose bodies may change (the economy-balance rationale states the old number).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402

TREE = "examples/deckbuilder"
# token -> {field: (old, new)}; every other field of these tokens must not change.
EXPECTED = {
    "resources.energy": {"max": (3, 4)},
    "balance_targets.energy_per_turn": {"target": (3, 4), "tolerance": ([3, 3], [4, 4])},
}


def main() -> None:
    a = cl.parse_args()
    r = cl.Report("operating_energy_budget")
    changes = cl.changed_paths(a.root, a.base)
    handled = cl.check_ritual_metadata(r, a.root, TREE, a.base, changes,
                                       run_date=a.run_date, check_date=a.check_date)
    stray = sorted(p for p in changes if not (p.startswith(TREE + "/") and p.endswith(".md")
                                             and changes[p] == "M"))
    r.check("only_existing_tree_markdown_modified", not stray, stray)

    token_diffs, file_problems = {}, []
    for rel in sorted(p for p in changes if p not in handled and p not in stray):
        b_fm, _ = cl.doc_at(a.root, rel, a.base)
        n_fm, _ = cl.doc_at(a.root, rel)
        if (b_fm or {}).get("file_type") != "subfile":
            file_problems.append(f"{rel}: non-subfile frontmatter changed")
            continue
        rest = [*cl.SUBFILE_NAMESPACES, "last_verified"]
        if cl.without(b_fm, *rest) != cl.without(n_fm, *rest):
            file_problems.append(f"{rel}: non-token frontmatter changed")
        lv = (n_fm or {}).get("last_verified")
        if (b_fm or {}).get("last_verified") != lv and not (a.run_date <= str(lv) <= a.check_date):
            file_problems.append(f"{rel}: last_verified {lv!r} outside session window")
        bt, nt = cl.subfile_tokens(b_fm), cl.subfile_tokens(n_fm)
        for tok in sorted(set(bt) | set(nt)):
            if bt.get(tok) != nt.get(tok):
                token_diffs[tok] = (bt.get(tok), nt.get(tok))
    r.check("subfile_frontmatter_valid", not file_problems, file_problems)

    unexpected = sorted(set(token_diffs) - set(EXPECTED))
    r.check("no_unexpected_token_changes", not unexpected, unexpected)
    for tok, fields in EXPECTED.items():
        old, new = token_diffs.get(tok, (None, None))
        if old is None:
            r.check(f"{tok}_updated", False, "unchanged")
            continue
        changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
        ok = changed == set(fields) and all(
            old.get(k) == o and new.get(k) == n for k, (o, n) in fields.items())
        r.check(f"{tok}_updated", ok, {k: [old.get(k), new.get(k)] for k in sorted(changed)})
    r.lint_clean(a.root, TREE)
    r.finish()


if __name__ == "__main__":
    main()
