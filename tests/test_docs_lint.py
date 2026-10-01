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


def _versions_findings(tmp_path, spec_text=None, schema_text=None):
    """check_versions() over a copy of the version carriers, optionally with
    the spec or the schema replaced."""
    mod = _docs_lint()
    for rel in ("pyproject.toml", "README.md", "docs/spec.md", "schema/game-design.schema.json"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text((REPO_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    if spec_text is not None:
        (tmp_path / "docs/spec.md").write_text(spec_text, encoding="utf-8")
    if schema_text is not None:
        (tmp_path / "schema/game-design.schema.json").write_text(schema_text, encoding="utf-8")
    mod.ROOT = tmp_path
    mod.check_versions()
    return mod.findings


def test_version_carriers_agree(tmp_path):
    assert _versions_findings(tmp_path) == []


def test_stale_conformance_version_is_found(tmp_path):
    """§11 read "conformant at v0.2.0-alpha" through all of v0.3 (5efbf92)."""
    pre = subprocess.run(["git", "show", "5efbf92:docs/spec.md"], cwd=REPO_ROOT,
                         capture_output=True, text=True)
    if pre.returncode != 0:
        pytest.skip("history not available")
    found = _versions_findings(tmp_path, spec_text=pre.stdout)
    assert len(found) == 1 and "§11" in found[0] and "v0.2.0-alpha" in found[0]


def test_stale_schema_id_is_found(tmp_path):
    schema = (REPO_ROOT / "schema/game-design.schema.json").read_text(encoding="utf-8")
    found = _versions_findings(tmp_path, schema_text=schema.replace(
        '"$id": "https://game-design.md/schema/v', '"$id": "https://game-design.md/schema/vX', 1))
    assert len(found) == 1 and "$id" in found[0]
