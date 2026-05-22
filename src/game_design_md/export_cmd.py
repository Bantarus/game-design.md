"""`gdmd export` — emit JSON Schema or flattened token JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .tree import SUBFILE_NAMESPACES, Tree

# Possible locations of schema/game-design.schema.json: editable install,
# wheel install via shared-data, or co-located dev tree.
def _find_schema() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "schema" / "game-design.schema.json",   # editable/dev
        here.parents[3] / "schema" / "game-design.schema.json",   # parent dir
    ]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(
        "schema/game-design.schema.json not found near "
        + str(here.parents[2])
    )


def export_schema() -> str:
    return _find_schema().read_text(encoding="utf-8")


def export_tokens(tree: Tree) -> str:
    """Walk the tree and emit a flat JSON object: every top-level token keyed by
    its dotted path."""
    out: dict[str, Any] = {}
    for ns in SUBFILE_NAMESPACES:
        for k, (_pf, v) in tree.tokens.get(ns, {}).items():
            out[k] = v
    return json.dumps(out, indent=2, default=str, sort_keys=True)
