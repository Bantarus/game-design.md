#!/usr/bin/env python3
"""Docs-consistency lint: drift-lints the drift linter's own documentation.

Grep-level checks that the repo's front-door documents agree with each other
and with the code. Every check here exists because the corresponding drift
actually happened once (README two minor versions stale; AGENTS.md teaching a
three-field stability guarantee and a `{loop.*}` ref that would not resolve;
spec §9 listing four CLI verbs while nine were shipped).

Run: python scripts/docs_lint.py   (exit 0 clean, exit 1 on any finding)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The four stability-guarantee fields per spec §5.1 / §8.2.
STABILITY_FIELDS = ["pillars", "non_goals", "player_experience_goals", "core_loop_ref"]

# Valid reference namespaces per spec §3: the twelve referenceable namespaces
# (not the reserved owned keys, D-039: `{pillars.x}` does not resolve), plus
# the context-local prefixes (D-012) and the doc-placeholder spellings used
# when teaching the syntax rather than referencing a real token.
VALID_NAMESPACES = {
    "entities", "verbs", "resources", "states", "events", "rules", "loops",
    "clocks", "distributions", "feel", "balance_targets", "invariants",
    # context-local (bound at rule-evaluation time, not globally resolvable)
    "actor", "target",
    # documentation placeholders
    "ns", "namespace", "token", "foo", "bar",
}

findings: list[str] = []


def fail(msg: str) -> None:
    findings.append(msg)


def base_version(pyproject_version: str) -> str:
    """0.3.0a1 -> 0.3.0 (strip pre-release suffix)."""
    m = re.match(r"^(\d+\.\d+\.\d+)", pyproject_version)
    return m.group(1) if m else pyproject_version


def check_versions() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    if not m:
        fail("pyproject.toml: could not find project version")
        return
    version = base_version(m.group(1))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"v{version}" not in readme:
        fail(f"README.md: does not mention v{version} (pyproject says {m.group(1)})")

    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    status_line = next((ln for ln in spec.splitlines() if "**Status:" in ln), "")
    if f"v{version}" not in status_line:
        fail(
            f"docs/spec.md: status line does not mention v{version} "
            f"(pyproject says {m.group(1)}): {status_line.strip()!r}"
        )

    # The other carriers the release procedure bumps (AGENTS.md). §11 read
    # "conformant at v0.2.0-alpha" through all of v0.3.
    fm = re.search(r"^spec_version:\s*(\S+)", spec, re.M)
    if not fm or fm.group(1) != version:
        fail(f"docs/spec.md: frontmatter spec_version is "
             f"{fm.group(1) if fm else 'missing'}, not {version}")
    conformance = re.search(r"\*\*conformant at (v[^*]+)\*\*", spec)
    if not conformance or conformance.group(1) != f"v{version}":
        fail(f"docs/spec.md §11: conformance sentence names "
             f"{conformance.group(1) if conformance else 'no version'}, not v{version}")
    init = (ROOT / "src" / "game_design_md" / "__init__.py").read_text(encoding="utf-8")
    for name, want in (("__version__", m.group(1)), ("__spec_version__", version)):
        im = re.search(rf'^{name}\s*=\s*"([^"]*)"', init, re.M)
        if not im or im.group(1) != want:
            fail(f"src/game_design_md/__init__.py: {name} is "
                 f"{im.group(1) if im else 'missing'}, not {want} "
                 f"(`gdmd --version` printed 0.1.0 through all of v0.3)")
    schema = (ROOT / "schema" / "game-design.schema.json").read_text(encoding="utf-8")
    for key in ("$id", "title"):
        sm = re.search(rf'^\s*"{re.escape(key)}":\s*"([^"]*)"', schema, re.M)
        if not sm or f"v{version}" not in sm.group(1):
            fail(f"schema/game-design.schema.json: {key} does not mention v{version}")


def check_cli_verbs() -> None:
    """Spec §9's opening verb list and the README's verb list must equal the
    registered click commands."""
    try:
        from game_design_md.cli import main  # noqa: PLC0415
    except ImportError:
        fail("could not import game_design_md.cli — run `pip install -e .` first")
        return
    registered = set(main.commands)

    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    m = re.search(r"^Verbs: `([^`]+)`", spec, re.M)
    if not m:
        fail("docs/spec.md: could not find the §9 'Verbs: `...`' line")
    else:
        listed = {v.strip() for v in m.group(1).split("|")}
        if listed != registered:
            fail(
                f"docs/spec.md §9 verb list {sorted(listed)} != "
                f"registered CLI commands {sorted(registered)}"
            )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"CLI \(`([^`]+)`\)", readme)
    if m:
        listed = {v.strip() for v in m.group(1).split("|")}
        if listed != registered:
            fail(
                f"README.md CLI verb list {sorted(listed)} != "
                f"registered CLI commands {sorted(registered)}"
            )


def check_stability_guarantee() -> None:
    """AGENTS.md and spec §8.2 must both name all four stability fields in
    their stability-guarantee sentence."""
    for rel, pattern in [
        ("AGENTS.md", r"Only .* stable for the life of a project"),
        ("docs/spec.md", r"\*\*Stability guarantee\.\*\*[^\n]*"),
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        sentences = re.findall(pattern, text)
        if not sentences:
            fail(f"{rel}: could not find the stability-guarantee sentence")
            continue
        for sentence in sentences:
            missing = [f for f in STABILITY_FIELDS if f"`{f}`" not in sentence]
            if missing:
                fail(f"{rel}: stability-guarantee sentence missing {missing}: {sentence.strip()!r}")


def check_agents_namespaces() -> None:
    """Every `{ns.` reference AGENTS.md teaches must use a valid namespace —
    an agent taught `{loop.x}` will author refs the linter rejects."""
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for ns in re.findall(r"\{([a-z_]+)\.", text):
        if ns not in VALID_NAMESPACES:
            fail(f"AGENTS.md: reference uses unknown namespace {{{ns}.…}}")


# A version-dated promise about future behavior ("ratchets to error in v0.3",
# "a v0.4+ concern", "deferred to v0.4+"). The spec and the schema state
# current behavior only; planned changes live in DECISIONS.md's Ratchet
# Register as trigger -> action (D-044). Seventeen spec lines and one schema
# description had gone stale by v0.4, several promising behavior never shipped.
DATED_PROMISE_RE = re.compile("|".join(f"(?:{p})" for p in (
    r"\bratchets?\b[^.;()]{0,60}?\bin\s+v\d",                     # ratchets (to X) in v0.3
    r"\bv\d+(?:\.\d+)*\+?\s+(?:spec-)?(?:concern|ratchet|follow-on|[\w-]+\s+question)",
    r"\b(?:info|warning|error)\s+in\s+v\d",                         # warning in v0.3
    r"\bdeferred\s+to\s+v\d",
    r"\bcandidates?\s+for\s+v\d",
)), re.I)


def dated_promises(text: str) -> list[tuple[int, str]]:
    """(line number, matched text) for every version-dated promise in `text`."""
    return [(i, m.group(0)) for i, line in enumerate(text.splitlines(), 1)
            for m in DATED_PROMISE_RE.finditer(line)]


def check_spec_states_current_behavior() -> None:
    for rel in ("docs/spec.md", "schema/game-design.schema.json"):
        for line, hit in dated_promises((ROOT / rel).read_text(encoding="utf-8")):
            fail(f"{rel}:{line}: version-dated promise {hit!r}; state current behavior and "
                 f"put the plan in DECISIONS.md's Ratchet Register (D-044)")


def main() -> int:
    check_versions()
    check_cli_verbs()
    check_stability_guarantee()
    check_agents_namespaces()
    check_spec_states_current_behavior()
    if findings:
        print(f"docs-lint: {len(findings)} finding(s)")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("docs-lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
