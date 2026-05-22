"""`gdmd spec` — print docs/spec.md to stdout with frontmatter stripped."""
from __future__ import annotations

import re
from importlib import resources as ir
from pathlib import Path


_FENCE_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _read_packaged() -> str | None:
    """Read the spec from packaged data (wheel installs) via importlib.resources.

    Returns None when the package data is unavailable (editable dev install
    without a build step). The dev-tree fallback handles that case.
    """
    try:
        res = ir.files("game_design_md").joinpath("_data/spec.md")
        if res.is_file():
            return res.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    return None


def _read_dev_tree() -> str:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "docs" / "spec.md",
        here.parents[3] / "docs" / "spec.md",
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "docs/spec.md not found in package data or near " + str(here.parents[2])
    )


def spec_text() -> str:
    text = _read_packaged() or _read_dev_tree()
    return _FENCE_RE.sub("", text, count=1).lstrip()
