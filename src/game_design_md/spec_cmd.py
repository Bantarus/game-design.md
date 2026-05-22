"""`gdmd spec` — print docs/spec.md to stdout with frontmatter stripped."""
from __future__ import annotations

import re
from pathlib import Path


def _find_spec() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "docs" / "spec.md",
        here.parents[3] / "docs" / "spec.md",
    ]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError("docs/spec.md not found near " + str(here.parents[2]))


_FENCE_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def spec_text() -> str:
    text = _find_spec().read_text(encoding="utf-8")
    return _FENCE_RE.sub("", text, count=1).lstrip()
