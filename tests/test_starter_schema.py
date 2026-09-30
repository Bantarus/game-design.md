"""Every starter's frontmatter validates against the normative JSON Schema
(spec §10; OI-006). `gdmd init` copies a starter into every new tree, so a
starter defect is inherited by every tree scaffolded from it (D-031).

Class A (OI-006: whole-namespace `applies_to` refs such as `"{resources}"`,
which `$defs.TokenRef` rejects while spec §4.11's own example uses them) is
a spec/schema decision held until after dogfood study 2 (D-026 amendment 3).
Those files are strict xfails: the day one validates, the xfail fails and
must be removed. A second test pins that class A is *all* that is wrong with
them, so the xfail cannot hide another defect.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from game_design_md import loader
from tests.conftest import REPO_ROOT

SCHEMA = json.loads((REPO_ROOT / "schema/game-design.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
STARTERS = REPO_ROOT / "templates/starters"
CLASS_A = "gdd/architecture-invariants.md"
BRANCH = {"core": "CoreFile", "subfile": "Subfile", "content-schema": "ContentSchemaFile",
          "content-entity": "ContentEntityFile"}
WHOLE_NAMESPACE_REF = re.compile(r"^\{[a-z_][a-z0-9_]*\}$")


def _frontmatter_files() -> list[tuple[str, str]]:
    """(starter, relpath) for every file with frontmatter: `*.md` under the
    tree and `*.yaml` outside an `impl/` tree (the correction note's pass)."""
    out = []
    for tree in sorted(p for p in STARTERS.iterdir() if p.is_dir()):
        for p in sorted(tree.rglob("*")):
            rel = p.relative_to(tree)
            if p.suffix == ".md" or (p.suffix in (".yaml", ".yml") and "impl" not in rel.parts):
                if loader.read(p)[0] is not None:
                    out.append((tree.name, rel.as_posix()))
    return out


FILES = _frontmatter_files()


def _frontmatter(starter: str, rel: str) -> dict:
    return loader.read(STARTERS / starter / rel)[0]


def test_every_starter_is_covered():
    assert {s for s, _ in FILES} == {"deckbuilder", "party-rpg", "platformer", "survival",
                                     "tcg", "tick-combat"}
    assert sum(1 for _, rel in FILES if rel == CLASS_A) == 6


@pytest.mark.parametrize("starter,rel", [
    pytest.param(s, r, id=f"{s}/{r}", marks=pytest.mark.xfail(
        strict=True, reason="OI-006 class A: whole-namespace applies_to refs; the "
                            "spec/schema decision waits until after study 2"))
    if r == CLASS_A else pytest.param(s, r, id=f"{s}/{r}")
    for s, r in FILES])
def test_starter_frontmatter_validates_against_the_schema(starter, rel):
    errors = [f"{list(e.absolute_path)}: {e.message}"
              for e in VALIDATOR.iter_errors(_frontmatter(starter, rel))]
    assert errors == []


@pytest.mark.parametrize("starter", sorted({s for s, r in FILES if r == CLASS_A}))
def test_class_a_files_fail_only_on_whole_namespace_applies_to(starter):
    """Validated against their own file_type branch, the class-A files'
    only errors are `applies_to` items of the form `{namespace}`."""
    fm = _frontmatter(starter, CLASS_A)
    branch = {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"],
              "$ref": f"#/$defs/{BRANCH[fm['file_type']]}"}
    errors = list(jsonschema.Draft202012Validator(branch).iter_errors(fm))
    assert errors, "validates now: remove the xfail and update OI-006"
    for e in errors:
        path = list(e.absolute_path)
        assert path[0] == "invariants" and path[2] == "applies_to", (path, e.message)
        assert e.validator == "pattern" and WHOLE_NAMESPACE_REF.match(e.instance), e.instance
