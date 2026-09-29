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
