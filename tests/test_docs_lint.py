"""`scripts/docs_lint.py` checks that are not covered by its own CLI run."""
from __future__ import annotations

import importlib.util
import subprocess

import pytest

from tests.conftest import REPO_ROOT


def _docs_lint():
    spec = importlib.util.spec_from_file_location("docs_lint", REPO_ROOT / "scripts/docs_lint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("text", [
    "they ratchet to error in v0.3 once the migration window closes",
    "A `trajectory-schema-validation` lint rule ratchets in v0.3.",
    "and ratchets to JSON Schema validation in v0.3;",
    "a normative closed-set ratchet is a v0.4+ concern.",
    "that's a v0.4 spec-ratchet event",
    "info (advisory) at v0.2.0-alpha; warning in v0.3; error in v0.4",
    "**Spec → code direction deferred to v0.4+.**",
    "are candidates for v0.4 based on observed use.",
    "that gap is a v0.4+ vocabulary-extension question to surface",
])
def test_dated_promises_are_found(text):
    assert _docs_lint().dated_promises(text)


@pytest.mark.parametrize("text", [
    "| `schema-violation` | error (v0.4+) | A file's frontmatter …",      # since-version
    "(added v0.3 per D-020) Postponed to a future milestone.",
    "**Events as first-class tokens (D-005 ratchet at v0.2).**",           # history
    "ratcheted from `warning` at v0.1.1 once the reference implementation shipped",
    "It never became the error D-003 scheduled for v0.3, and at v0.4 it is retired",
])
def test_current_behavior_and_history_are_not_promises(text):
    assert _docs_lint().dated_promises(text) == []


def test_the_spec_and_schema_state_current_behavior_only():
    """D-044: the pre-D-044 spec carried 17 such lines; the spec must carry none."""
    mod = _docs_lint()
    for rel in ("docs/spec.md", "schema/game-design.schema.json"):
        assert mod.dated_promises((REPO_ROOT / rel).read_text(encoding="utf-8")) == [], rel
    pre = subprocess.run(["git", "show", "4d95ec4:docs/spec.md"], cwd=REPO_ROOT,
                         capture_output=True, text=True)
    if pre.returncode == 0:   # proof of fire, where the history is available
        assert len({line for line, _ in mod.dated_promises(pre.stdout)}) == 17
