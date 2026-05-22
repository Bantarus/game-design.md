"""Token reference syntax: `{namespace.id...}`.

Extraction + resolution. Extraction is purely textual; resolution lives on
`Tree`.
"""
from __future__ import annotations

import re
from typing import Iterator

# 1 namespace segment + 1..5 dotted sub-segments. Bounds the parser depth at 6.
TOKEN_REF_RE = re.compile(
    r"\{([a-z_][a-z0-9_]*(?:\.[a-z0-9_][a-z0-9_-]*){1,5})\}"
)


def walk_refs(o, path: tuple[str, ...] = ()) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Yield (ref-body, path-into-object) for every reference in a nested structure.

    `ref-body` is the inner string of `{...}` (e.g. `"verbs.play_card"`).
    """
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk_refs(v, path + (str(k),))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_refs(v, path + (f"[{i}]",))
    elif isinstance(o, str):
        for m in TOKEN_REF_RE.finditer(o):
            yield m.group(1), path
