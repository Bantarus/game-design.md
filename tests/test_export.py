"""Export: schema dump + flattened tokens."""
from __future__ import annotations

import json

from game_design_md import export_cmd
from game_design_md.tree import Tree


def test_export_schema_is_valid_json():
    text = export_cmd.export_schema()
    schema = json.loads(text)
    assert schema["$schema"].endswith("draft/2020-12/schema")
    assert "CoreFile" in schema["$defs"]
    assert "Invariant" in schema["$defs"]
    assert "StateMachine" in schema["$defs"]


def test_export_tokens_flat(make_tree):
    tree = Tree.load(make_tree())
    out = json.loads(export_cmd.export_tokens(tree))
    assert "verbs.do_thing" in out
    assert "loops.main" in out
    assert "distributions.test_dist" in out
    assert "balance_targets.energy_target" in out
    # No nesting — paths are dotted keys.
    assert all("." in k for k in out)
