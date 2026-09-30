"""Shared helpers for dogfood checkers (`tasks/<task_id>.check.py`).

A checker is a deterministic script, with no LLM judge:

    python tasks/<task_id>.check.py <copy_root> [--base TAG] [--run-date YYYY-MM-DD]

It prints one JSON report to stdout and exits 0 on success, 1 otherwise.
Checkers compare the copy's working tree against `--base` (the pre-session
tag written by `fixture.prepare_copy`). Parsing uses the format's own strict
loader; expected answers are frozen data, never computed at check time from
the ref-extraction code that `gdmd view` is built on.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from game_design_md import loader

BASE_TAG = "dogfood-base"
SUBFILE_NAMESPACES = (
    "entities", "verbs", "resources", "states", "rules", "loops",
    "distributions", "feel", "balance_targets", "invariants", "events",
    "clocks",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="root of the isolated copy")
    ap.add_argument("--base", default=BASE_TAG)
    ap.add_argument("--run-date", default=None,
                    help="date the session started (YYYY-MM-DD); defaults to today")
    ns = ap.parse_args(argv)
    ns.root = ns.root.resolve()
    ns.run_date = ns.run_date or date.today().isoformat()
    ns.check_date = date.today().isoformat()
    return ns


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True).stdout


def changed_paths(root: Path, base: str = BASE_TAG) -> dict[str, str]:
    """{repo-relative path: status} for every difference between `base` and
    the working tree, including commits the subject made and untracked files
    ("?")."""
    out: dict[str, str] = {}
    for line in git(root, "diff", "--name-status", "--no-renames", base).splitlines():
        status, _, path = line.partition("\t")
        out[path] = status
    for path in git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        out[path] = "?"
    return out


def read_text(root: Path, rel: str, ref: str | None = None) -> str | None:
    if ref is None:
        p = root / rel
        return p.read_text(encoding="utf-8") if p.is_file() else None
    proc = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{rel}"],
                          capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def parse_doc(rel: str, text: str | None) -> tuple[dict | None, str]:
    """(frontmatter-or-yaml-document, body) with the format's strict loader."""
    if text is None:
        return None, ""
    if rel.endswith(".md"):
        fm, body = loader.parse_md(text)
        return fm, body
    doc = loader.parse_yaml(text)
    return (doc if isinstance(doc, dict) else None), ""


def doc_at(root: Path, rel: str, ref: str | None = None) -> tuple[dict | None, str]:
    return parse_doc(rel, read_text(root, rel, ref))


def subfile_tokens(fm: dict | None) -> dict[str, Any]:
    """{"<ns>.<id>": value} for the namespace blocks of one subfile."""
    out: dict[str, Any] = {}
    for ns in SUBFILE_NAMESPACES:
        block = (fm or {}).get(ns)
        if isinstance(block, dict):
            for k, v in block.items():
                out[f"{ns}.{k}"] = v
    return out


def without(d: dict | None, *keys: str) -> dict:
    return {k: v for k, v in (d or {}).items() if k not in keys}


def semver_tuple(v: Any) -> tuple:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(v))
    return tuple(int(x) for x in m.groups()) if m else (-1,)


def gdmd_cmd() -> list[str]:
    """The CLI under test: `gdmd` on PATH (the copy's shim when run by run.py),
    or the command in $DOGFOOD_GDMD."""
    override = os.environ.get("DOGFOOD_GDMD")
    return shlex.split(override) if override else ["gdmd"]


def lint(root: Path, tree: str) -> dict:
    proc = subprocess.run([*gdmd_cmd(), "lint", str(root / tree)],
                          capture_output=True, text=True)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"summary": {"errors": -1, "warnings": -1},
                "findings": [], "raw": (proc.stdout + proc.stderr)[-2000:]}


class Report:
    """Collects named criteria; `finish()` prints the JSON report and exits."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.criteria: dict[str, dict] = {}

    def check(self, name: str, ok: bool, detail: Any = None) -> bool:
        self.criteria[name] = {"pass": bool(ok), "detail": detail}
        return bool(ok)

    def lint_clean(self, root: Path, tree: str) -> bool:
        res = lint(root, tree)
        s = res.get("summary", {})
        bad = [f"{f['rule']}:{f['file']}:{f.get('location', '')}"
               for f in res.get("findings", []) if f.get("severity") in ("error", "warning")]
        return self.check("lint_clean", s.get("errors") == 0 and s.get("warnings") == 0,
                          {"summary": s, "findings": bad[:20]})

    @property
    def success(self) -> bool:
        return bool(self.criteria) and all(c["pass"] for c in self.criteria.values())

    def finish(self) -> None:
        print(json.dumps({"task": self.task_id, "success": self.success,
                          "criteria": self.criteria}, indent=2, default=str))
        sys.exit(0 if self.success else 1)


def check_ritual_metadata(report: Report, root: Path, tree: str, base: str,
                          changes: dict[str, str], *, run_date: str, check_date: str,
                          allow_subfile_body: bool = True) -> set[str]:
    """Shared rule for "ritual metadata" edits the workflow allows but no
    task requires:

    - core `game-design.md`: only `version` (which must increase) and
      `last_updated` (which must fall in the session's date window) may
      differ in frontmatter; the body must not change.
    - any other `.md` under the tree: only `last_verified` may differ in
      frontmatter; prose-body edits are allowed when `allow_subfile_body`.

    Returns the set of changed paths that this rule accounted for; the caller
    decides what the remaining changes mean.
    """
    handled: set[str] = set()
    core_rel = f"{tree}/game-design.md"
    problems: list[str] = []
    for rel, status in changes.items():
        if not rel.startswith(tree + "/") or not rel.endswith(".md") or status != "M":
            continue
        base_fm, base_body = doc_at(root, rel, base)
        new_fm, new_body = doc_at(root, rel)
        if rel == core_rel:
            meta = ("version", "last_updated")
            if without(base_fm, *meta) != without(new_fm, *meta):
                problems.append(f"{rel}: frontmatter changed beyond version/last_updated")
            if base_body != new_body:
                problems.append(f"{rel}: body changed")
            old_v, new_v = (base_fm or {}).get("version"), (new_fm or {}).get("version")
            if old_v != new_v and semver_tuple(new_v) <= semver_tuple(old_v):
                problems.append(f"{rel}: version changed but did not increase")
            lu = (new_fm or {}).get("last_updated")
            in_window = run_date <= str(lu) <= check_date
            if (base_fm or {}).get("last_updated") != lu and not in_window:
                problems.append(f"{rel}: last_updated {lu!r} outside session window")
            handled.add(rel)
            continue
        if without(base_fm, "last_verified") != without(new_fm, "last_verified"):
            continue  # a real content change: the task's own rule decides
        lv = (new_fm or {}).get("last_verified")
        if (base_fm or {}).get("last_verified") != lv and not (run_date <= str(lv) <= check_date):
            problems.append(f"{rel}: last_verified {lv!r} outside session window")
        if base_body != new_body and not allow_subfile_body:
            problems.append(f"{rel}: body changed")
        handled.add(rel)
    report.check("ritual_metadata_valid", not problems, problems)
    return handled


# ---- study 2 (D-026): answer files --------------------------------------------------

STUDY2_ANSWERS = Path(__file__).resolve().parent / "fixtures" / "study2" / "answers"
STUDY2_TREE = "examples/lanternfall"
_HEADER = re.compile(r"^\s*(Q\d+)\s*:\s*(.*)$")


def _items(text: str) -> list[str]:
    out = []
    for part in text.split(","):
        item = part.strip()
        item = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", item).strip().strip("`").strip()
        if item:
            out.append(item)
    return out


def parse_answer_file(text: str) -> dict[str, list[str]]:
    """{"Q1": [item, ...], ...} from the study-2 answer format: a `Q<n>:` header
    line, then one item per line. Items after the header on the same line,
    comma-separated items, list bullets and backticks are tolerated."""
    out: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        m = _HEADER.match(line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, []).extend(_items(m.group(2)))
        elif cur and line.strip():
            out[cur].extend(_items(line))
    return out


def norm_id(item: str) -> str:
    item = item.strip()
    if item.startswith("{") and item.endswith("}"):
        item = item[1:-1]
    return item.strip()


def norm_path(item: str) -> str:
    item = item.strip()
    for prefix in ("./", STUDY2_TREE + "/"):
        if item.startswith(prefix):
            item = item[len(prefix):]
    return item


def jaccard(a: set, b: set) -> float:
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def check_study2_answers(task: str, paths: bool = False,
                         argv: list[str] | None = None) -> None:
    """Checker body for the four study-2 answer tasks (D-026): the answer file
    is the only change, and every question's set equals the frozen answer
    exactly. Per-question Jaccard is reported, descriptive only."""
    a = parse_args(argv)
    r = Report(task)
    answer = f"answers/{task}.txt"
    expected = json.loads((STUDY2_ANSWERS / f"{task}.json").read_text(encoding="utf-8"))
    changes = changed_paths(a.root, a.base)
    r.check("answer_file_written", changes.get(answer) in ("A", "?"), changes.get(answer))
    r.check("no_other_changes", set(changes) <= {answer}, sorted(set(changes) - {answer}))
    got = parse_answer_file(read_text(a.root, answer) or "")
    norm = norm_path if paths else norm_id
    for q, spec in sorted(expected["questions"].items()):
        want = set(spec["answer"])
        have = {norm(x) for x in got.get(q, [])} if q in got else None
        detail = None if have is None else {
            "missing": sorted(want - have), "extra": sorted(have - want),
            "jaccard": round(jaccard(want, have), 4)}
        r.check(f"{q.lower()}_correct", have == want, detail)
    r.finish()


def check_study2_maintenance(task: str, argv: list[str] | None = None) -> None:
    """Checker body for s2_maintenance (D-026): last_verified bumped on exactly
    the subfiles whose implemented_in covers the patched file; no token or
    file change beyond allowed ritual metadata; the implementation and
    everything outside the tree untouched; lint 0/0."""
    a = parse_args(argv)
    r = Report(task)
    tree = STUDY2_TREE
    expected = set(json.loads((STUDY2_ANSWERS / f"{task}.json").read_text())["touched"])
    changes = changed_paths(a.root, a.base)
    r.check("nothing_outside_tree_changed",
            not [p for p in changes if not p.startswith(tree + "/")],
            sorted(p for p in changes if not p.startswith(tree + "/")))
    impl = sorted(p for p in changes if p.startswith(f"{tree}/impl/"))
    r.check("implementation_untouched", not impl, impl)
    handled = check_ritual_metadata(r, a.root, tree, a.base, changes,
                                    run_date=a.run_date, check_date=a.check_date)
    other = sorted(p for p in changes if p.startswith(tree + "/") and p not in handled
                   and p not in impl)
    r.check("no_token_or_file_changes", not other, other)
    touched = set()
    for rel in changes:
        if rel.endswith(".md"):
            b, _ = doc_at(a.root, rel, a.base)
            n, _ = doc_at(a.root, rel)
            if (b or {}).get("last_verified") != (n or {}).get("last_verified"):
                touched.add(rel)
    r.check("touched_exactly_affected_sections", touched == expected, sorted(touched))
    r.lint_clean(a.root, tree)
    r.finish()


def check_study2_negative_control(task: str, argv: list[str] | None = None) -> None:
    """Checker body for s2_negative_control (D-026): the copy is unchanged."""
    a = parse_args(argv)
    r = Report(task)
    changes = changed_paths(a.root, a.base)
    r.check("repository_unchanged", not changes, changes)
    r.lint_clean(a.root, STUDY2_TREE)
    r.finish()
