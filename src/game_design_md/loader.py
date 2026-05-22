"""Shared YAML/frontmatter loader used by every CLI verb.

`GdmdLoader` is a SafeLoader subclass with two strictness changes vs. PyYAML
defaults:

  - YAML 1.1 implicit booleans (`on`/`off`/`yes`/`no`) are removed and replaced
    with YAML 1.2-style booleans (only `true`/`false`, case-insensitive).
    This means `event: on` parses as the string `"on"`, not `True`.

  - YAML 1.1 implicit timestamps are removed. `last_verified: 2026-05-21`
    parses as the string `"2026-05-21"`, matching the schema's `ISODate`
    pattern.

See DECISIONS.md D-001 and D-004.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class GdmdLoader(yaml.SafeLoader):
    """SafeLoader without YAML 1.1 boolean/timestamp coercion."""


# Strip YAML 1.1 implicit resolvers for bool + timestamp from every char bucket.
_DROP = {"tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp"}
GdmdLoader.yaml_implicit_resolvers = {
    ch: [(tag, regex) for tag, regex in resolvers if tag not in _DROP]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
# Re-add a YAML 1.2-shaped boolean resolver (true|false only).
GdmdLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=GdmdLoader)


_FENCE_RE = re.compile(r"^---\s*\n(.*?\n)---\s*(?:\n|$)", re.DOTALL)


def parse_md(text: str) -> tuple[dict | None, str]:
    """Split a Markdown file into (frontmatter dict | None, body)."""
    m = _FENCE_RE.match(text)
    if not m:
        return None, text
    fm = load_yaml(m.group(1))
    body = text[m.end():]
    if fm is None:
        return {}, body
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter is not a mapping: {type(fm).__name__}")
    return fm, body


def parse_yaml(text: str) -> Any:
    return load_yaml(text)


def read(path: Path) -> tuple[dict | None, str]:
    """Read a .md or .yaml file. Returns (frontmatter|root-doc, body).

    For .yaml files, frontmatter is the whole document and body is "".
    For .md files, frontmatter is the fenced YAML (or None if absent).
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        return parse_md(text)
    if path.suffix in (".yaml", ".yml"):
        doc = parse_yaml(text)
        if doc is None:
            return {}, ""
        if not isinstance(doc, dict):
            return None, ""
        return doc, ""
    raise ValueError(f"unsupported file type: {path.suffix}")
