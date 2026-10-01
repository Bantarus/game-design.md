"""Token reference syntax: `{namespace.id...}`, plus the whole-namespace
`{namespace}` form an invariant's `applies_to:` items may use (spec §3, D-033).

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


# D-033: a whole-namespace reference is an `applies_to:` item whose entire
# string is `{namespace}`. Nowhere else is a single-segment `{word}` a reference.
NAMESPACE_REF_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
NAMESPACE_REF_FIELD = "applies_to"


def namespace_ref(value: object, path: tuple[str, ...]) -> str | None:
    """The namespace named by a whole-namespace reference at `path`, else None."""
    if (isinstance(value, str) and len(path) >= 2 and path[-2] == NAMESPACE_REF_FIELD
            and path[-1].startswith("[")):
        m = NAMESPACE_REF_RE.fullmatch(value)
        if m:
            return m.group(1)
    return None


def string_refs(value: str, path: tuple[str, ...]) -> list[str]:
    """The reference bodies in one string value at `path`, in order."""
    ns = namespace_ref(value, path)
    if ns is not None:
        return [ns]
    return [m.group(1) for m in TOKEN_REF_RE.finditer(value)]


def walk_refs(o, path: tuple[str, ...] = ()) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Yield (ref-body, path-into-object) for every reference in a nested structure.

    `ref-body` is the inner string of `{...}` (e.g. `"verbs.play_card"`), or a
    bare namespace (`"resources"`) for a whole-namespace reference (D-033).
    """
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk_refs(v, path + (str(k),))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_refs(v, path + (f"[{i}]",))
    elif isinstance(o, str):
        for ref in string_refs(o, path):
            yield ref, path


def is_namespace_ref(ref: str) -> bool:
    """A reference body with one segment can only be a whole-namespace reference."""
    return "." not in ref
