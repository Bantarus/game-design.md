"""Every starter's frontmatter validates against the normative JSON Schema
(spec §10; OI-006). `gdmd init` copies a starter into every new tree, so a
starter defect is inherited by every tree scaffolded from it (D-031).

Class A (OI-006: whole-namespace `applies_to` refs such as `"{resources}"`)
was decided in the schema's favour by D-033: `applies_to` items may be
`$defs.NamespaceRef`. The six class-A starter files, strict xfails until
then, now validate like every other starter.
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


@pytest.mark.parametrize("starter,rel", [pytest.param(s, r, id=f"{s}/{r}") for s, r in FILES])
def test_starter_frontmatter_validates_against_the_schema(starter, rel):
    errors = [f"{list(e.absolute_path)}: {e.message}"
              for e in VALIDATOR.iter_errors(_frontmatter(starter, rel))]
    assert errors == []


def test_class_a_files_use_whole_namespace_refs():
    """The files D-033 was decided on still exercise NamespaceRef."""
    for starter in sorted({s for s, r in FILES if r == CLASS_A}):
        items = [ref for inv in _frontmatter(starter, CLASS_A)["invariants"].values()
                 for ref in inv.get("applies_to") or []]
        assert any(WHOLE_NAMESPACE_REF.match(r) for r in items), starter


def _branch_validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})


def test_whole_namespace_refs_are_valid_only_in_applies_to():
    """D-033 scopes NamespaceRef to an invariant's applies_to; every other
    TokenRef field still rejects `{namespace}`."""
    inv = {"kind": "numeric_domain", "rule": "integers", "enforcement": "lint",
           "severity": "error", "applies_to": ["{resources}", "{rules.x}"]}
    assert not list(_branch_validator("Invariant").iter_errors(inv))
    bad = dict(inv, applies_to=["{resources.}"])
    assert list(_branch_validator("Invariant").iter_errors(bad))
    rule = {"given": {"verb": "{verbs}"}, "do": [{"x": 1}], "outputs": [], "status": "draft",
            "implemented_in": []}
    assert list(_branch_validator("Rule").iter_errors(rule))
    loop = {"timescale": "moment", "duration": "1s", "sequence": ["{verbs.a}"],
            "intended_dynamics": ["x"], "intended_aesthetics": ["challenge"], "status": "draft",
            "implemented_in": [], "balance_targets": ["{balance_targets}"]}
    assert list(_branch_validator("Loop").iter_errors(loop))
