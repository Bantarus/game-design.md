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


class Positioned:
    """One file read with positions kept (spec §9.9.1, D-027 decision 3).

    `frontmatter` and `body` are exactly what `read` returns for the same
    file. `node` is the composed YAML node the frontmatter was constructed
    from (None when there is no YAML document). `fm_text` is the YAML source
    the node's marks index into; its line `L` (0-based) is file line
    `fm_line_offset + L + 1`. `body_line_offset` is the number of file lines
    before the body's first line.
    """

    __slots__ = ("frontmatter", "body", "text", "node", "fm_text",
                 "fm_line_offset", "body_line_offset")

    def __init__(self, frontmatter, body, text, node, fm_text,
                 fm_line_offset, body_line_offset):
        self.frontmatter = frontmatter
        self.body = body
        self.text = text
        self.node = node
        self.fm_text = fm_text
        self.fm_line_offset = fm_line_offset
        self.body_line_offset = body_line_offset


def _compose_construct(text: str):
    """Compose once, construct from the node graph: `(node, data)`.

    Same result as `load_yaml(text)`, which is `get_single_node` followed by
    `construct_document`.
    """
    ldr = GdmdLoader(text)
    try:
        node = ldr.get_single_node()
        data = ldr.construct_document(node) if node is not None else None
    finally:
        ldr.dispose()
    return node, data


def read_positioned(path: Path) -> Positioned:
    """`read`, keeping the composed YAML node and the line offsets.

    Returns the same `(frontmatter, body)` values as `read`, and raises the
    same errors, so a `Tree` built with this reader is the `Tree` built
    with `read`.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        m = _FENCE_RE.match(text)
        if not m:
            return Positioned(None, text, text, None, "", 0, 0)
        fm_text = m.group(1)
        node, fm = _compose_construct(fm_text)
        body = text[m.end():]
        fm_off = text[:m.start(1)].count("\n")
        body_off = text[:m.end()].count("\n")
        if fm is None:
            return Positioned({}, body, text, node, fm_text, fm_off, body_off)
        if not isinstance(fm, dict):
            raise ValueError(f"frontmatter is not a mapping: {type(fm).__name__}")
        return Positioned(fm, body, text, node, fm_text, fm_off, body_off)
    if path.suffix in (".yaml", ".yml"):
        node, doc = _compose_construct(text)
        if doc is None:
            return Positioned({}, "", text, node, text, 0, 0)
        if not isinstance(doc, dict):
            return Positioned(None, "", text, node, text, 0, 0)
        return Positioned(doc, "", text, node, text, 0, 0)
    raise ValueError(f"unsupported file type: {path.suffix}")


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
