"""`gdmd export` — emit JSON Schema or flattened token JSON."""
from __future__ import annotations

import json
from importlib import resources as ir
from pathlib import Path
from typing import Any

from .tree import SUBFILE_NAMESPACES, Tree


def _read_packaged_schema() -> str | None:
    """Read the JSON Schema from packaged data (wheel installs)."""
    try:
        res = ir.files("game_design_md").joinpath("_data/game-design.schema.json")
        if res.is_file():
            return res.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    return None


def _read_dev_tree_schema() -> str:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "schema" / "game-design.schema.json",
        here.parents[3] / "schema" / "game-design.schema.json",
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "schema/game-design.schema.json not found in package data or near "
        + str(here.parents[2])
    )


def export_schema() -> str:
    return _read_packaged_schema() or _read_dev_tree_schema()


def export_tokens(tree: Tree) -> str:
    """Walk the tree and emit a flat JSON object: every top-level token keyed by
    its dotted path."""
    out: dict[str, Any] = {}
    for ns in SUBFILE_NAMESPACES:
        for k, (_pf, v) in tree.tokens.get(ns, {}).items():
            out[k] = v
    return json.dumps(out, indent=2, default=str, sort_keys=True)
